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


# Minimum hours remaining for certificate validity
CERT_MIN_HOURS_REMAINING = 24


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


class LLMCheck(PreFlightCheck):
    """Check LLM provider availability with actual API ping.
    
    Args:
        http_client_factory: Factory function to create async HTTP client.
    """
    
    def __init__(
        self,
        http_client_factory: Optional[Callable[[], httpx.AsyncClient]] = None
    ) -> None:
        self._http_client_factory = http_client_factory or (lambda: httpx.AsyncClient(timeout=10.0))

    @property
    def name(self) -> str:
        return "LLM_CHECK"

    @property
    def priority(self) -> CheckPriority:
        return CheckPriority.P0

    async def execute(self, config: dict[str, Any]) -> CheckResult:
        api_key = config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            return CheckResult(self.name, CheckStatus.FAIL, self.priority, "LLM API Key missing (OPENAI_API_KEY)")
        
        # Try to ping the LLM API
        api_base = config.get("openai_api_base", "https://api.openai.com/v1")
        return await self._ping_api(api_key, api_base)

    async def _ping_api(self, api_key: str, api_base: str) -> CheckResult:
        """Attempt to verify LLM API is reachable with a lightweight models list call."""
        try:
            async with self._http_client_factory() as client:
                response = await client.get(
                    f"{api_base}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                
                if response.status_code == 200:
                    return CheckResult(self.name, CheckStatus.PASS, self.priority, "LLM API reachable and responding")
                elif response.status_code == 401:
                    return CheckResult(self.name, CheckStatus.FAIL, self.priority, "LLM API key invalid (401 Unauthorized)")
                else:
                    return CheckResult(
                        self.name, CheckStatus.FAIL, self.priority,
                        f"LLM API returned status {response.status_code}",
                        {"status_code": response.status_code}
                    )
        except Exception as e:
            return CheckResult(self.name, CheckStatus.FAIL, self.priority, f"LLM API ping failed: {e}")


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
        self.checks: list[PreFlightCheck] = checks or [
            RedisCheck(),
            LLMCheck(),
            ScopeCheck(),
            DiskCheck(),
            MemoryCheck(),
            CertCheck(),
        ]

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
