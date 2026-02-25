"""Pre-flight checks logic.

This module defines the framework for pre-flight validation checks
that run before an engagement starts. These checks ensure the system
is healthy, safe, and ready for operation.

Architecture:
    CheckStatus (Enum): PASS, WARN, FAIL
    CheckPriority (Enum): P0 (Blocking), P1 (Warning)
    CheckResult (Dataclass): Result of a single check
    PreFlightCheck (ABC): Base class for all checks

Dependency Injection:
    All check classes accept optional factory functions for external
    dependencies (Redis clients, HTTP clients, etc.) to enable testing
    without mocking imports.
"""

import asyncio
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Optional

import httpx
import psutil
import redis
import redis.sentinel
import yaml
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from cyberred.core.exceptions import PreFlightCheckError, PreFlightWarningError
from cyberred.llm.env import resolve_llm_api_base, resolve_llm_api_key
from cyberred.llm.nim import NIMProvider


# Minimum hours remaining for certificate validity
CERT_MIN_HOURS_REMAINING = 24

# Resource admission defaults (engagement/host budgeting).
DEFAULT_RESOURCE_POLICY: dict[str, float] = {
    "memory_reserve_mb": 4096.0,
    "director_memory_mb": 512.0,
    "worker_memory_mb": 256.0,
    "headroom_mb": 1024.0,
    # Defaults align with architecture sizing: 10K agents ≈ 10GB => ~1MB per agent.
    "agent_memory_kb": 1024.0,
    "max_mem_utilization_pct": 92.0,
    "max_cpu_utilization_pct": 95.0,
    "max_iowait_pct": 45.0,
    "max_load_per_cpu": 4.0,
    "agents_per_cpu_core": 100.0,
    "agents_per_worker": 80.0,
    "tools_per_worker_ratio": 1.0,
    "worker_min_available_ratio": 0.2,
    "worker_min_available": 1.0,
    "min_worker_reserve": 1.0,
    "global_memory_utilization_cap_pct": 90.0,
    "director_cycle_timeout_s": 1200.0,
    "director_trigger_timeout_s": 1320.0,
}


def _safe_float(value: Any, default: float) -> float:
    """Best-effort float parsing with default fallback."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    """Best-effort int parsing with default fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_resource_policy(config: dict[str, Any]) -> dict[str, float]:
    """Resolve resource policy from engagement config with defaults."""
    policy = dict(DEFAULT_RESOURCE_POLICY)
    configured = config.get("resource_policy", {})
    if isinstance(configured, dict):
        for key in policy:
            if key in configured:
                policy[key] = _safe_float(configured.get(key), policy[key])
    return policy


def _resolve_expected_workers(config: dict[str, Any]) -> int:
    """Resolve expected worker pool size from config."""
    infrastructure = config.get("infrastructure", {})
    expected_workers = (
        config.get("worker_pool_size")
        or (infrastructure.get("worker_pool_size") if isinstance(infrastructure, dict) else None)
        or os.getenv("CYBERRED_WORKER_POOL_SIZE")
        or 15
    )
    return max(1, _safe_int(expected_workers, 15))


def _resolve_target_agents(config: dict[str, Any]) -> int:
    """Resolve target agent count for admission checks."""
    policy = config.get("resource_policy", {})
    explicit = None
    if isinstance(policy, dict):
        explicit = policy.get("target_agents")
    if explicit is None:
        explicit = config.get("target_agents")
    if explicit is None:
        explicit = config.get("max_agents")
    if explicit is not None:
        return max(1, _safe_int(explicit, 100))

    # Heuristic fallback from scope/target size.
    scope = config.get("scope", {}) if isinstance(config.get("scope"), dict) else {}
    targets = config.get("targets", {}) if isinstance(config.get("targets"), dict) else {}
    networks = scope.get("allowed_ips", [])
    network_count = len(networks) if isinstance(networks, list) else 0
    target_count = len(targets)
    inferred = max(10, (network_count * 10) + (target_count * 5))
    return inferred


class CheckStatus(StrEnum):
    """Status of a pre-flight check."""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class CheckPriority(StrEnum):
    """Priority of a pre-flight check."""
    P0 = "P0"  # Blocking: Engagement cannot start
    P1 = "P1"  # Warning: Requires acknowledgment


@dataclass
class CheckResult:
    """Result of a pre-flight check execution.
    
    Attributes:
        name: Name of the check (e.g., "REDIS_CHECK").
        status: PASS, WARN, or FAIL.
        priority: P0 or P1.
        message: Human-readable result message.
        details: Dictionary of technical details (for debug/logs).
    """
    name: str
    status: CheckStatus
    priority: CheckPriority
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class PreFlightCheck(ABC):
    """Abstract base class for all pre-flight checks."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the check."""
        pass

    @property
    @abstractmethod
    def priority(self) -> CheckPriority:
        """Priority of the check."""
        pass

    @abstractmethod
    async def execute(self, config: dict[str, Any]) -> CheckResult:
        """Execute the check."""
        pass


class DiskCheck(PreFlightCheck):
    """Check for sufficient disk space.
    
    Args:
        disk_usage_fn: Optional function to get disk usage (for testing).
                       Defaults to shutil.disk_usage.
    """
    
    def __init__(self, disk_usage_fn: Optional[Callable[[str], Any]] = None) -> None:
        self._disk_usage = disk_usage_fn or shutil.disk_usage
    
    @property
    def name(self) -> str:
        return "DISK_CHECK"

    @property
    def priority(self) -> CheckPriority:
        return CheckPriority.P1

    async def execute(self, config: dict[str, Any]) -> CheckResult:
        try:
            # Check root partition or configured storage path
            path = config.get("storage_path", "/")
            if not os.path.exists(path):
                # Fallback to root if specific path doesn't exist yet
                path = "/"

            usage = await asyncio.to_thread(self._disk_usage, path)
            percent_free = (usage.free / usage.total) * 100
            
            # Requirement: > 10% free
            if percent_free > 10.0:
                return CheckResult(
                    self.name, 
                    CheckStatus.PASS, 
                    self.priority, 
                    f"Disk space OK: {percent_free:.1f}% free",
                    {"path": path, "free_percent": percent_free}
                )
            else:
                # P1 checks use WARN status for threshold violations
                return CheckResult(
                    self.name, 
                    CheckStatus.WARN, 
                    self.priority, 
                    f"Low disk space: {percent_free:.1f}% free (min 10%)",
                    {"path": path, "free_percent": percent_free}
                )
        except Exception as e:
            return CheckResult(
                self.name, 
                CheckStatus.FAIL, 
                self.priority, 
                f"Disk check failed: {e}"
            )


class MemoryCheck(PreFlightCheck):
    """Check for sufficient available RAM.
    
    Args:
        memory_fn: Optional function to get memory info (for testing).
                   Defaults to psutil.virtual_memory.
    """
    
    def __init__(self, memory_fn: Optional[Callable[[], Any]] = None) -> None:
        self._virtual_memory = memory_fn or psutil.virtual_memory
    
    @property
    def name(self) -> str:
        return "MEMORY_CHECK"

    @property
    def priority(self) -> CheckPriority:
        return CheckPriority.P1

    async def execute(self, config: dict[str, Any]) -> CheckResult:
        try:
            mem = await asyncio.to_thread(self._virtual_memory)
            available_gb = mem.available / (1024**3)
            
            # Requirement: > 1GB available
            if available_gb > 1.0:
                return CheckResult(
                    self.name,
                    CheckStatus.PASS,
                    self.priority,
                    f"Memory OK: {available_gb:.2f}GB available",
                    {"available_gb": available_gb}
                )
            else:
                # P1 checks use WARN status for threshold violations
                return CheckResult(
                    self.name,
                    CheckStatus.WARN,
                    self.priority,
                    f"Low memory: {available_gb:.2f}GB available (min 1GB)",
                    {"available_gb": available_gb}
                )
        except Exception as e:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                f"Memory check failed: {e}"
            )


class ScopeCheck(PreFlightCheck):
    """Validate scope file existence and syntax.
    
    Args:
        file_exists_fn: Optional function to check file existence.
        yaml_loader_fn: Optional function to load YAML.
    """
    
    def __init__(
        self, 
        file_exists_fn: Optional[Callable[[str], bool]] = None,
        yaml_loader_fn: Optional[Callable[[str], Any]] = None
    ) -> None:
        self._file_exists = file_exists_fn or os.path.exists
        self._yaml_loader = yaml_loader_fn or self._default_yaml_loader
    
    def _default_yaml_loader(self, path: str) -> Any:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @property
    def name(self) -> str:
        return "SCOPE_CHECK"

    @property
    def priority(self) -> CheckPriority:
        return CheckPriority.P0

    async def execute(self, config: dict[str, Any]) -> CheckResult:
        # Check for embedded scope first
        embedded_scope = config.get("scope")
        if embedded_scope:
            if not isinstance(embedded_scope, dict):
                return CheckResult(self.name, CheckStatus.FAIL, self.priority,
                    "Embedded 'scope' must be a dictionary")
            if not embedded_scope.get("allowed_ips") and not embedded_scope.get("allowed_ports"):
                return CheckResult(self.name, CheckStatus.FAIL, self.priority,
                    "Scope must define 'allowed_ips' or 'allowed_ports'")
            return CheckResult(self.name, CheckStatus.PASS, self.priority,
                "Embedded scope valid", {"source": "embedded"})

        # Fall back to external scope file
        path = config.get("scope_path")
        if not path:
             return CheckResult(self.name, CheckStatus.FAIL, self.priority, "Scope configuration missing 'scope_path'")

        exists = await asyncio.to_thread(self._file_exists, path)
        if not exists:
             return CheckResult(self.name, CheckStatus.FAIL, self.priority, f"Scope file not found: {path}")

        try:
            data = await asyncio.to_thread(self._yaml_loader, path)

            if not data:
                return CheckResult(self.name, CheckStatus.FAIL, self.priority, "Scope file is empty or invalid")

            if not isinstance(data, dict):
                 return CheckResult(self.name, CheckStatus.FAIL, self.priority, "Scope file must be a YAML dictionary")

            return CheckResult(self.name, CheckStatus.PASS, self.priority, "Scope file valid")

        except Exception as e:
            return CheckResult(self.name, CheckStatus.FAIL, self.priority, f"Scope parse error: {e}")


class RedisCheck(PreFlightCheck):
    """Check Redis connectivity and Sentinel master election (if configured).
    
    Args:
        redis_client_factory: Factory function to create Redis client from URL.
        sentinel_factory: Factory function to create Sentinel client.
    """
    
    def __init__(
        self,
        redis_client_factory: Optional[Callable[..., Any]] = None,
        sentinel_factory: Optional[Callable[..., Any]] = None
    ) -> None:
        self._redis_from_url = redis_client_factory or redis.from_url
        self._sentinel_class = sentinel_factory or redis.sentinel.Sentinel

    @property
    def name(self) -> str:
        return "REDIS_CHECK"

    @property
    def priority(self) -> CheckPriority:
        return CheckPriority.P0

    async def execute(self, config: dict[str, Any]) -> CheckResult:
        sentinel_hosts = config.get("sentinel_hosts")
        sentinel_service = config.get("sentinel_service", "mymaster")
        
        if sentinel_hosts:
            # Sentinel mode: verify master election
            return await self._check_sentinel(sentinel_hosts, sentinel_service)
        else:
            # Standard Redis mode
            url = config.get("redis_url", "redis://localhost:6379")
            return await self._check_standard(url)

    async def _check_standard(self, url: str) -> CheckResult:
        """Check standard Redis connectivity."""
        try:
            def ping_redis() -> bool:
                r = self._redis_from_url(url, socket_timeout=2.0)
                return r.ping()
            
            await asyncio.to_thread(ping_redis)
            return CheckResult(self.name, CheckStatus.PASS, self.priority, "Redis reachable")
        except Exception as e:
            return CheckResult(self.name, CheckStatus.FAIL, self.priority, f"Redis connection failed: {e}")

    async def _check_sentinel(self, hosts: list[tuple[str, int]], service_name: str) -> CheckResult:
        """Check Redis Sentinel and master election."""
        try:
            def check_sentinel() -> str:
                sentinel = self._sentinel_class(hosts, socket_timeout=2.0)
                master = sentinel.discover_master(service_name)
                # Verify we can ping the master
                master_client = sentinel.master_for(service_name, socket_timeout=2.0)
                master_client.ping()
                return f"{master[0]}:{master[1]}"
            
            master_addr = await asyncio.to_thread(check_sentinel)
            return CheckResult(
                self.name, CheckStatus.PASS, self.priority,
                f"Redis Sentinel OK, master at {master_addr}",
                {"master_address": master_addr}
            )
        except redis.sentinel.MasterNotFoundError:
            return CheckResult(self.name, CheckStatus.FAIL, self.priority, "Redis Sentinel: no master elected")
        except Exception as e:
            return CheckResult(self.name, CheckStatus.FAIL, self.priority, f"Redis Sentinel check failed: {e}")


class WorkerPoolCheck(PreFlightCheck):
    """Check Docker worker pool availability for engagement execution."""

    @property
    def name(self) -> str:
        return "WORKER_POOL_CHECK"

    @property
    def priority(self) -> CheckPriority:
        return CheckPriority.P0

    async def execute(self, config: dict[str, Any]) -> CheckResult:
        infrastructure = config.get("infrastructure", {})
        policy = _resolve_resource_policy(config)
        worker_prefix = (
            config.get("worker_container_prefix")
            or infrastructure.get("worker_container_prefix")
            or "red-kali-worker"
        )
        expected_workers = (
            config.get("worker_pool_size")
            or infrastructure.get("worker_pool_size")
            or 15
        )
        try:
            expected_workers = max(1, int(expected_workers))
        except (TypeError, ValueError):
            expected_workers = 15

        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/docker",
                "ps",
                "--format",
                "{{.Names}}\t{{.Image}}\t{{.Status}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
        except FileNotFoundError:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                "Docker CLI not found at /usr/bin/docker",
            )
        except Exception as e:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                f"Docker worker check failed: {e}",
            )

        if proc.returncode != 0:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                f"Docker worker check failed: {stderr.decode().strip() or 'docker ps returned non-zero'}",
            )

        prefix_workers: list[str] = []
        image_workers: list[str] = []
        for line in stdout.decode().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            container_name, container_image, status = parts[0], parts[1], parts[2]
            if not status.lower().startswith("up"):
                continue
            if container_name.startswith(f"{worker_prefix}-"):
                prefix_workers.append(container_name)
            if "red-kali-worker" in container_image:
                image_workers.append(container_name)

        discovered_workers = sorted(set(prefix_workers) | set(image_workers))
        if not discovered_workers:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                f"No running worker containers found (prefix={worker_prefix})",
                {
                    "expected_workers": expected_workers,
                    "discovered_workers": 0,
                },
            )

        responsive_workers: list[str] = []
        unreachable_workers: list[str] = []
        probe_targets = discovered_workers[: max(expected_workers, 3)]
        for container_name in probe_targets:
            probe = await asyncio.create_subprocess_exec(
                "/usr/bin/docker",
                "exec",
                container_name,
                "true",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, probe_err = await probe.communicate()
            if probe.returncode == 0:
                responsive_workers.append(container_name)
            else:
                error_text = probe_err.decode().strip()
                if error_text:
                    unreachable_workers.append(f"{container_name}: {error_text}")
                else:
                    unreachable_workers.append(container_name)

        if not responsive_workers:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                "Worker containers discovered but none are responsive to docker exec",
                {
                    "discovered_workers": discovered_workers,
                    "probed_workers": probe_targets,
                    "unreachable_workers": unreachable_workers,
                },
            )

        available_workers = len(responsive_workers)
        available_ratio = available_workers / max(1, expected_workers)
        min_available = max(
            1,
            _safe_int(
                policy.get("worker_min_available"),
                min(3, expected_workers),
            ),
        )
        min_ratio = max(
            0.0,
            min(
                1.0,
                _safe_float(
                    policy.get("worker_min_available_ratio"),
                    0.2,
                ),
            ),
        )
        if available_workers < min_available or available_ratio < min_ratio:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                (
                    "Worker pool below minimum availability "
                    f"({available_workers}/{expected_workers}, ratio={available_ratio:.2f}; "
                    f"required min={min_available}, min_ratio={min_ratio:.2f})"
                ),
                {
                    "expected_workers": expected_workers,
                    "available_workers": available_workers,
                    "available_ratio": available_ratio,
                    "min_available": min_available,
                    "min_ratio": min_ratio,
                    "discovered_workers": discovered_workers,
                    "probed_workers": probe_targets,
                    "responsive_workers": responsive_workers,
                    "unreachable_workers": unreachable_workers,
                },
            )

        return CheckResult(
            self.name,
            CheckStatus.PASS,
            self.priority,
            (
                "Worker pool ready: "
                f"{len(responsive_workers)} responsive container(s), "
                f"availability ratio={available_ratio:.2f}"
            ),
            {
                "expected_workers": expected_workers,
                "available_workers": available_workers,
                "available_ratio": available_ratio,
                "discovered_workers": discovered_workers,
                "probed_workers": probe_targets,
                "responsive_workers": responsive_workers,
                "unreachable_workers": unreachable_workers,
            },
        )


class ResourceAdmissionCheck(PreFlightCheck):
    """Capacity-aware engagement admission check.

    Hard-gates engagement start when host resources cannot safely support the
    requested engagement scope/agent count.
    """

    def __init__(
        self,
        memory_fn: Optional[Callable[[], Any]] = None,
        cpu_percent_fn: Optional[Callable[..., float]] = None,
        cpu_times_percent_fn: Optional[Callable[..., Any]] = None,
        cpu_count_fn: Optional[Callable[[], int]] = None,
        loadavg_fn: Optional[Callable[[], tuple[float, float, float]]] = None,
    ) -> None:
        self._virtual_memory = memory_fn or psutil.virtual_memory
        self._cpu_percent = cpu_percent_fn or psutil.cpu_percent
        self._cpu_times_percent = cpu_times_percent_fn or psutil.cpu_times_percent
        self._cpu_count = cpu_count_fn or psutil.cpu_count
        self._loadavg = loadavg_fn or os.getloadavg

    @property
    def name(self) -> str:
        return "RESOURCE_ADMISSION_CHECK"

    @property
    def priority(self) -> CheckPriority:
        return CheckPriority.P0

    async def execute(self, config: dict[str, Any]) -> CheckResult:
        policy = _resolve_resource_policy(config)
        expected_workers = _resolve_expected_workers(config)
        target_agents = _resolve_target_agents(config)
        requested_parallel_tools = max(
            1,
            _safe_int(config.get("roe", {}).get("max_concurrent_tools"), 8),
        )

        reserve_mb = max(0.0, _safe_float(policy.get("memory_reserve_mb"), 4096.0))
        director_overhead_mb = max(0.0, _safe_float(policy.get("director_memory_mb"), 512.0))
        headroom_mb = max(0.0, _safe_float(policy.get("headroom_mb"), 1024.0))
        agent_memory_mb = max(0.001, _safe_float(policy.get("agent_memory_kb"), 1.0) / 1024.0)

        try:
            memory = await asyncio.to_thread(self._virtual_memory)
            available_mb = memory.available / (1024 * 1024)
            total_mb = memory.total / (1024 * 1024)
            mem_used_pct = float(getattr(memory, "percent", 0.0))

            def _cpu_percent_call() -> float:
                try:
                    return float(self._cpu_percent(interval=0.2))
                except TypeError:
                    return float(self._cpu_percent())

            def _cpu_times_call() -> Any:
                try:
                    return self._cpu_times_percent(interval=0.2)
                except TypeError:
                    return self._cpu_times_percent()

            cpu_utilization_pct = await asyncio.to_thread(_cpu_percent_call)
            cpu_times = await asyncio.to_thread(_cpu_times_call)
            io_wait_pct = float(getattr(cpu_times, "iowait", 0.0))
            cpu_count = max(1, _safe_int(await asyncio.to_thread(self._cpu_count), 1))
            try:
                load1, _, _ = await asyncio.to_thread(self._loadavg)
            except (AttributeError, OSError):
                load1 = 0.0
            load_per_cpu = float(load1) / cpu_count
        except Exception as e:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                f"Resource admission probe failed: {e}",
            )

        max_mem_pct = _safe_float(policy.get("max_mem_utilization_pct"), 92.0)
        max_cpu_pct = _safe_float(policy.get("max_cpu_utilization_pct"), 95.0)
        max_iowait_pct = _safe_float(policy.get("max_iowait_pct"), 45.0)
        max_load_per_cpu = _safe_float(policy.get("max_load_per_cpu"), 4.0)

        usable_for_agents_mb = max(
            0.0,
            available_mb - reserve_mb - director_overhead_mb - headroom_mb,
        )
        memory_agent_cap = max(1, int(usable_for_agents_mb / agent_memory_mb))
        cpu_agent_cap = max(
            1,
            int(cpu_count * _safe_float(policy.get("agents_per_cpu_core"), 100.0)),
        )
        worker_agent_cap = max(
            1,
            int(expected_workers * _safe_float(policy.get("agents_per_worker"), 80.0)),
        )
        hardware_agent_cap = max(1, min(memory_agent_cap, cpu_agent_cap, worker_agent_cap))
        max_agents_allowed_now = max(1, min(target_agents, hardware_agent_cap))

        reserved_memory_mb = (
            director_overhead_mb
            + headroom_mb
            + (agent_memory_mb * max_agents_allowed_now)
        )
        required_memory_mb = reserve_mb + reserved_memory_mb

        critical_mem_pct = max(max_mem_pct + 3.0, 95.0)
        critical_cpu_pct = max(max_cpu_pct + 2.0, 98.0)
        critical_iowait_pct = max(max_iowait_pct + 20.0, 70.0)
        critical_load_per_cpu = max(max_load_per_cpu * 1.5, 6.0)

        failures: list[str] = []
        warnings: list[str] = []

        if available_mb < required_memory_mb:
            failures.append(
                f"available_mb={available_mb:.1f}<required_mb={required_memory_mb:.1f}"
            )
        if mem_used_pct >= critical_mem_pct:
            failures.append(
                f"mem_used_pct={mem_used_pct:.1f}>=critical_mem_pct={critical_mem_pct:.1f}"
            )
        elif mem_used_pct >= max_mem_pct:
            warnings.append(
                f"mem_used_pct={mem_used_pct:.1f}>=max_mem_pct={max_mem_pct:.1f}"
            )

        if cpu_utilization_pct >= critical_cpu_pct:
            failures.append(
                f"cpu_pct={cpu_utilization_pct:.1f}>=critical_cpu_pct={critical_cpu_pct:.1f}"
            )
        elif cpu_utilization_pct >= max_cpu_pct:
            warnings.append(
                f"cpu_pct={cpu_utilization_pct:.1f}>=max_cpu_pct={max_cpu_pct:.1f}"
            )

        if io_wait_pct >= critical_iowait_pct:
            failures.append(
                f"iowait_pct={io_wait_pct:.1f}>=critical_iowait_pct={critical_iowait_pct:.1f}"
            )
        elif io_wait_pct >= max_iowait_pct:
            warnings.append(
                f"iowait_pct={io_wait_pct:.1f}>=max_iowait_pct={max_iowait_pct:.1f}"
            )

        if load_per_cpu >= critical_load_per_cpu:
            failures.append(
                f"load_per_cpu={load_per_cpu:.2f}>=critical_load_per_cpu={critical_load_per_cpu:.2f}"
            )
        elif load_per_cpu >= max_load_per_cpu:
            warnings.append(
                f"load_per_cpu={load_per_cpu:.2f}>=max_load_per_cpu={max_load_per_cpu:.2f}"
            )

        tools_per_worker_ratio = max(
            0.1,
            _safe_float(policy.get("tools_per_worker_ratio"), 1.0),
        )
        max_parallel_tools_now = max(
            1,
            min(
                requested_parallel_tools,
                int(max(1, expected_workers * tools_per_worker_ratio)),
            ),
        )
        min_worker_reserve = max(
            0,
            _safe_int(policy.get("min_worker_reserve"), 1),
        )
        min_worker_reserve = min(min_worker_reserve, max(0, expected_workers - 1))

        director_policy = config.get("director_policy", {})
        if not isinstance(director_policy, dict):
            director_policy = {}
        director_cycle_timeout_s = max(
            120.0,
            _safe_float(
                director_policy.get("cycle_timeout_s"),
                _safe_float(policy.get("director_cycle_timeout_s"), 1200.0),
            ),
        )
        director_trigger_timeout_s = max(
            director_cycle_timeout_s + 60.0,
            _safe_float(
                director_policy.get("trigger_timeout_s"),
                _safe_float(policy.get("director_trigger_timeout_s"), 1320.0),
            ),
        )

        resource_contract = {
            "target_agents": target_agents,
            "expected_workers": expected_workers,
            "requested_parallel_tools": requested_parallel_tools,
            "max_agents_allowed_now": max_agents_allowed_now,
            "max_parallel_tools_now": max_parallel_tools_now,
            "min_worker_reserve": min_worker_reserve,
            "hardware_agent_cap": hardware_agent_cap,
            "required_memory_mb": required_memory_mb,
            "required_free_memory_mb": reserve_mb,
            "reserved_memory_mb": reserved_memory_mb,
            "global_memory_utilization_cap_pct": _safe_float(
                policy.get("global_memory_utilization_cap_pct"),
                90.0,
            ),
            "policy": policy,
            "director_budget_profile": {
                "cycle_timeout_s": director_cycle_timeout_s,
                "trigger_timeout_s": director_trigger_timeout_s,
            },
        }

        details = {
            "resource_contract": resource_contract,
            "available_memory_mb": available_mb,
            "total_memory_mb": total_mb,
            "memory_used_pct": mem_used_pct,
            "required_memory_mb": required_memory_mb,
            "reserved_memory_mb": reserved_memory_mb,
            "required_free_memory_mb": reserve_mb,
            "cpu_utilization_pct": cpu_utilization_pct,
            "iowait_pct": io_wait_pct,
            "load_per_cpu": load_per_cpu,
            "cpu_count": cpu_count,
            "policy": policy,
            "failures": failures,
            "warnings": warnings,
        }

        if failures:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                "Resource admission blocked: " + "; ".join(failures),
                details,
            )

        return CheckResult(
            self.name,
            CheckStatus.WARN if warnings else CheckStatus.PASS,
            self.priority,
            (
                f"{'Resource admission warning: ' if warnings else 'Resource admission pass: '}"
                f"agents_cap={max_agents_allowed_now}/{target_agents}, "
                f"tools_cap={max_parallel_tools_now}/{requested_parallel_tools}"
            ),
            details,
        )


class LLMCheck(PreFlightCheck):
    """Check LLM provider availability with actual API ping.
    
    Args:
        http_client_factory: Factory function to create async HTTP client.
    """
    
    def __init__(
        self,
        http_client_factory: Optional[Callable[[], httpx.AsyncClient]] = None,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self._http_client_factory = http_client_factory or (lambda: httpx.AsyncClient(timeout=20.0))
        self._max_attempts = max(1, max_attempts)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    @property
    def name(self) -> str:
        return "LLM_CHECK"

    @property
    def priority(self) -> CheckPriority:
        return CheckPriority.P0

    async def execute(self, config: dict[str, Any]) -> CheckResult:
        api_key = resolve_llm_api_key(config)
        if not api_key:
            return CheckResult(self.name, CheckStatus.FAIL, self.priority, "LLM API Key missing (NVIDIA_API_KEY or OPENAI_API_KEY)")

        api_base = resolve_llm_api_base(config)
        return await self._ping_api(api_key, api_base)

    async def _ping_api(self, api_key: str, api_base: str) -> CheckResult:
        """Verify LLM API with models list and a minimal completion probe."""
        last_failure: CheckResult | None = None

        for attempt in range(1, self._max_attempts + 1):
            result = await self._ping_api_once(api_key, api_base)
            if result.status == CheckStatus.PASS:
                return result

            last_failure = result
            if not self._is_retryable_failure(result) or attempt >= self._max_attempts:
                return result

            await asyncio.sleep(self._retry_backoff_seconds * attempt)

        return last_failure or CheckResult(
            self.name,
            CheckStatus.FAIL,
            self.priority,
            "LLM API ping failed without additional details",
        )

    async def _ping_api_once(self, api_key: str, api_base: str) -> CheckResult:
        """Single LLM API probe attempt."""
        try:
            async with self._http_client_factory() as client:
                models_response = await client.get(
                    f"{api_base}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )

                if models_response.status_code == 401:
                    return CheckResult(self.name, CheckStatus.FAIL, self.priority, "LLM API key invalid (401 Unauthorized)")
                if models_response.status_code != 200:
                    return CheckResult(
                        self.name, CheckStatus.FAIL, self.priority,
                        f"LLM API returned status {models_response.status_code}",
                        {"status_code": models_response.status_code}
                    )

                try:
                    models_payload = models_response.json()
                except ValueError:
                    return CheckResult(
                        self.name,
                        CheckStatus.FAIL,
                        self.priority,
                        "LLM API /models returned invalid JSON",
                    )

                probe_models = self._select_probe_models(models_payload)
                if not probe_models:
                    return CheckResult(
                        self.name,
                        CheckStatus.FAIL,
                        self.priority,
                        "LLM API reachable but no probeable model was returned",
                    )

                probe_failures: list[dict[str, Any]] = []
                for model_id in probe_models[:3]:
                    completion_response = await client.post(
                        f"{api_base}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": model_id,
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 1,
                            "temperature": 0,
                        },
                    )

                    if completion_response.status_code == 200:
                        return CheckResult(
                            self.name,
                            CheckStatus.PASS,
                            self.priority,
                            f"LLM API reachable and completion probe passed ({model_id})",
                        )

                    if completion_response.status_code == 401:
                        return CheckResult(
                            self.name,
                            CheckStatus.FAIL,
                            self.priority,
                            "LLM API key invalid during completion probe (401 Unauthorized)",
                        )

                    probe_failures.append(
                        {"model": model_id, "status_code": completion_response.status_code}
                    )

                failure_summary = ", ".join(
                    f"{entry['model']}:{entry['status_code']}" for entry in probe_failures
                )
                return CheckResult(
                    self.name,
                    CheckStatus.FAIL,
                    self.priority,
                    f"LLM completion probe failed for models [{failure_summary}]",
                    {"probe_failures": probe_failures},
                )
        except httpx.TimeoutException as e:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                f"LLM API ping timed out ({type(e).__name__})",
                {"error_type": type(e).__name__, "error": str(e)},
            )
        except httpx.HTTPError as e:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                f"LLM API HTTP error ({type(e).__name__})",
                {"error_type": type(e).__name__, "error": str(e)},
            )
        except Exception as e:
            return CheckResult(
                self.name,
                CheckStatus.FAIL,
                self.priority,
                f"LLM API ping failed ({type(e).__name__})",
                {"error_type": type(e).__name__, "error": str(e)},
            )

    def _is_retryable_failure(self, result: CheckResult) -> bool:
        """Return True if check failure is likely transient and can be retried."""
        if result.status != CheckStatus.FAIL:
            return False

        status_code = result.details.get("status_code")
        if isinstance(status_code, int) and (status_code in (408, 429) or status_code >= 500):
            return True

        for failure in result.details.get("probe_failures", []):
            code = failure.get("status_code")
            if isinstance(code, int) and (code in (408, 429) or code >= 500):
                return True

        error_type = result.details.get("error_type", "")
        return error_type in {"ReadTimeout", "ConnectTimeout", "PoolTimeout", "TimeoutException", "ConnectError", "NetworkError"}

    def _select_probe_models(self, models_payload: Any) -> list[str]:
        """Select ordered probe model list, preferring active tier models."""
        model_ids: list[str] = []
        if isinstance(models_payload, dict):
            data = models_payload.get("data")
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        model_id = item.get("id")
                        if isinstance(model_id, str) and model_id.strip():
                            model_ids.append(model_id.strip())
        elif isinstance(models_payload, list):
            for item in models_payload:
                if isinstance(item, dict):
                    model_id = item.get("id")
                    if isinstance(model_id, str) and model_id.strip():
                        model_ids.append(model_id.strip())
                elif isinstance(item, str) and item.strip():
                    model_ids.append(item.strip())

        if not model_ids:
            return []

        preferred = [
            NIMProvider.MODELS["FAST"],
            NIMProvider.MODELS["STANDARD"],
            NIMProvider.MODELS["COMPLEX"],
        ]
        ordered: list[str] = []
        for model_id in preferred:
            if model_id in model_ids and model_id not in ordered:
                ordered.append(model_id)
        for model_id in model_ids:
            if model_id not in ordered:
                ordered.append(model_id)
        return ordered


class CertCheck(PreFlightCheck):
    """Check C2 Certificate validity including 24h expiry requirement.
    
    Args:
        cert_loader: Function to load and parse a certificate, returning (not_after, hours_remaining).
    """
    
    def __init__(
        self,
        cert_loader: Optional[Callable[[str], tuple[datetime, float]]] = None
    ) -> None:
        self._cert_loader = cert_loader or self._default_cert_loader
    
    def _default_cert_loader(self, cert_path: str) -> tuple[datetime, float]:
        """Load certificate and calculate hours remaining."""
        with open(cert_path, "rb") as f:
            cert_data = f.read()
        
        cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        not_after = cert.not_valid_after_utc
        now = datetime.now(timezone.utc)
        hours_remaining = (not_after - now).total_seconds() / 3600
        return not_after, hours_remaining

    @property
    def name(self) -> str:
        return "CERT_CHECK"

    @property
    def priority(self) -> CheckPriority:
        return CheckPriority.P0

    async def execute(self, config: dict[str, Any]) -> CheckResult:
        if not config.get("c2_enabled", False):
            return CheckResult(self.name, CheckStatus.PASS, self.priority, "C2 disabled - skipping cert check")

        cert_path = config.get("c2_cert_path")
        if not cert_path or not os.path.exists(cert_path):
             return CheckResult(self.name, CheckStatus.FAIL, self.priority, "C2 Cert missing")

        try:
            size = os.path.getsize(cert_path)
            if size == 0:
                return CheckResult(self.name, CheckStatus.FAIL, self.priority, "C2 Cert empty")
            
            # Check certificate expiry
            return await self._check_cert_expiry(cert_path)
            
        except Exception as e:
            return CheckResult(self.name, CheckStatus.FAIL, self.priority, f"Cert check failed: {e}")

    async def _check_cert_expiry(self, cert_path: str) -> CheckResult:
        """Verify certificate has >24h remaining validity."""
        try:
            not_after, hours_remaining = await asyncio.to_thread(self._cert_loader, cert_path)
            
            if hours_remaining < 0:
                return CheckResult(
                    self.name, CheckStatus.FAIL, self.priority,
                    f"C2 Cert expired at {not_after.isoformat()}",
                    {"expires_at": not_after.isoformat(), "hours_remaining": hours_remaining}
                )
            elif hours_remaining < CERT_MIN_HOURS_REMAINING:
                return CheckResult(
                    self.name, CheckStatus.FAIL, self.priority,
                    f"C2 Cert expires in {hours_remaining:.1f}h (min {CERT_MIN_HOURS_REMAINING}h required)",
                    {"expires_at": not_after.isoformat(), "hours_remaining": hours_remaining}
                )
            else:
                return CheckResult(
                    self.name, CheckStatus.PASS, self.priority,
                    f"C2 Cert valid ({hours_remaining:.1f}h remaining)",
                    {"expires_at": not_after.isoformat(), "hours_remaining": hours_remaining}
                )
                
        except Exception as e:
            return CheckResult(self.name, CheckStatus.FAIL, self.priority, f"Cert expiry check failed: {e}")


class PreFlightRunner:
    """Orchestrates execution of pre-flight checks.
    
    Args:
        checks: Optional list of check instances (for testing with injected checks).
    """
    
    def __init__(self, checks: Optional[list[PreFlightCheck]] = None) -> None:
        if checks is None:
            # Import here to avoid circular dependency
            from cyberred.daemon.preflight_waiver import WaiverPreFlightCheck
            
            checks = [
                RedisCheck(),
                WorkerPoolCheck(),
                ResourceAdmissionCheck(),
                LLMCheck(),
                ScopeCheck(),
                DiskCheck(),
                MemoryCheck(),
                CertCheck(),
                WaiverPreFlightCheck(),
            ]
        
        self.checks: list[PreFlightCheck] = checks

    async def run_all(self, engagement_config: dict[str, Any]) -> list[CheckResult]:
        """Run all configured checks in priority order."""
        # Sort checks: P0 first, then P1
        sorted_checks = sorted(self.checks, key=lambda c: c.priority)
        
        results = []
        for check in sorted_checks:
            result = await check.execute(engagement_config)
            results.append(result)
            
        return results

    def validate_results(self, results: list[CheckResult], ignore_warnings: bool = False) -> None:
        """Validate check results and raise if blocking failures exist.

        Args:
            results: List of results from run_all.
            ignore_warnings: If True, P1 warnings won't raise.

        Raises:
            PreFlightCheckError: If any P0 check fails.
            PreFlightWarningError: If any P1 check fails/warns and ignore_warnings is False.
        """
        # Dev bypass is double-gated to avoid accidental production bypass.
        if (
            os.environ.get("CYBERRED_DEV_MODE") == "1"
            and os.environ.get("CYBERRED_ALLOW_PREFLIGHT_BYPASS") == "1"
        ):
            import structlog
            log = structlog.get_logger()
            log.warning(
                "preflight_checks_bypassed",
                reason="CYBERRED_DEV_MODE=1 + CYBERRED_ALLOW_PREFLIGHT_BYPASS=1",
                skipped_checks=[r.name for r in results if r.status == CheckStatus.FAIL],
            )
            return

        # P0 Failures
        p0_failures = [
            r for r in results 
            if r.priority == CheckPriority.P0 and r.status == CheckStatus.FAIL
        ]
        if p0_failures:
            raise PreFlightCheckError(p0_failures)
            
        # P1 Warnings - Check logic: 
        # CheckStatus.FAIL or WARN on P1 counts as warning
        p1_warnings = [
            r for r in results 
            if r.priority == CheckPriority.P1 and r.status in (CheckStatus.FAIL, CheckStatus.WARN)
        ]
        
        if p1_warnings and not ignore_warnings:
             raise PreFlightWarningError(p1_warnings)
