"""
Orchestrator - Central coordinator for the Cyber-Red system.

The Orchestrator is the main entry point that initializes all components,
manages job queues, and coordinates between agents, tools, and the AI council.

Story 7.26: Wires the stigmergic agent swarm (StigmergicAgent, SwarmRouterWrapper,
DynamicSpawner) into the actual execution flow, replacing the hardcoded GhostAgent
for full engagements while keeping GhostAgent for quick_attack mode.
"""
import asyncio
from collections import deque
import ipaddress
import logging
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import psutil

from cyberred.core.event_bus import EventBus
from cyberred.core.council import CouncilOfExperts
from cyberred.core.worker_pool import WorkerPool
from cyberred.core.tool_orchestrator import ToolOrchestrator
from cyberred.agents.ghost_agent import GhostAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.throttler import SwarmBrain
from cyberred.core.roe_loader import RoELoader
from cyberred.core.models import Scope, Target
from cyberred.orchestration.router import SwarmRouterWrapper
from cyberred.orchestration.spawner import DynamicSpawner
from cyberred.orchestration.crash_monitor import AgentCrashMonitor
from cyberred.llm import (
    initialize_gateway, get_gateway, shutdown_gateway,
    RateLimiter, ModelRouter, LLMPriorityQueue, RetryPolicy,
    NIMProvider, TaskComplexity, resolve_llm_api_key,
)
from cyberred.rag.director_client import DirectorRAGClient
from cyberred.core.sharding import ShardedEventBus, ShardAggregator


# Role-specific execute method mapping
# Method names match actual implementations in agent subclasses
_ROLE_EXECUTE_METHODS: dict[str, str] = {
    "recon": "execute_recon",
    "exploit": "execute_exploit",
    "postex": "execute_postex",
    "webapp": "execute_webapp_scan",
    "wireless": "execute_wireless_scan",
    "ad": "execute_ad_attack",
    "credential": "execute_credential_attack",
    "forensics": "execute_forensics_collection",
}

_DOCKER_SCOPE_PATTERN = re.compile(r"docker-([0-9a-f]{12,64})\.scope")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


class Orchestrator:
    """
    Central coordinator for the Cyber-Red attack platform.

    Responsibilities:
    - Initialize all core components
    - Manage job queue and agent lifecycle
    - Route commands from TUI to agents
    - Coordinate between AI council and tool execution
    - Spawn and manage stigmergic agent swarms (Story 7.26)
    """

    def __init__(self, event_bus: EventBus):
        self.bus = event_bus
        self.logger = logging.getLogger("Orchestrator")
        self._models_config: dict[str, Any] = {}

        # Engagement context (set by SessionManager)
        self._engagement_id: str | None = None
        self._engagement_config: dict | None = None

        # Initialize Core Components
        self.brain = SwarmBrain(limit=30)
        self.roe_loader = RoELoader()
        self.roe = self.roe_loader.load()
        try:
            worker_pool_size = max(1, int(os.getenv("CYBERRED_WORKER_POOL_SIZE", "15")))
        except ValueError:
            worker_pool_size = 15

        # Worker pool for Docker container management
        self.pool = WorkerPool(
            event_bus=self.bus,
            pool_size=worker_pool_size,
            container_prefix="red-kali-worker"
        )

        # Tool orchestrator for parallel tool execution (used by GhostAgent fallback)
        self.tool_orchestrator = ToolOrchestrator(
            worker_pool=self.pool,
            event_bus=self.bus
        )

        # AI Council for strategic decisions (used by GhostAgent + NLP dispatch)
        self.council = CouncilOfExperts(
            self.brain,
            self.roe,
            self.bus,
            self.roe_loader
        )

        # Stigmergic swarm components (Story 7.26)
        self.router = SwarmRouterWrapper(swarm_type="ConcurrentWorkflow")
        self.spawner: DynamicSpawner | None = None  # Created per-engagement
        self._swarm_tasks: list[asyncio.Task] = []

        # Active agents (supports both GhostAgent and StigmergicAgent)
        self.agents: dict[Any, Any] = {}
        self.next_agent_id = 1

        # Director RAG swarm failure tracking
        self._swarm_failure_counts: dict[str, int] = {}  # agent_role -> failure_count
        self._swarm_failure_threshold = 3  # trigger pivot after N total role failures
        self._director_rag_client: DirectorRAGClient | None = None  # set in _deploy_stigmergic_swarm
        self._director_rag_policy: dict[str, Any] = {}

        # Stigmergic sharding (Story 7.13)
        self._sharded_bus: ShardedEventBus | None = None
        self._shard_aggregator: ShardAggregator | None = None
        self._decision_context_tracker: Any = None
        self._emergent_strategy_aggregator: Any = None

        # Director layer (Stories 8.1–8.11)
        self._director_ensemble: Any = None
        self._finding_aggregator: Any = None
        self._strategy_publisher: Any = None
        self._replan_manager: Any = None
        self._current_phase: str = "recon"
        self._director_last_strategy_ts: float | None = None
        self._director_no_quorum_since: float | None = None
        self._director_recovery_tasks: set[asyncio.Task] = set()
        self._last_no_quorum_recovery_trigger_at: float = 0.0
        try:
            self._director_min_quorum = max(1, int(os.getenv("CYBERRED_DIRECTOR_MIN_QUORUM", "1")))
        except ValueError:
            self._director_min_quorum = 1
        try:
            self._director_recovery_delay_s = max(
                5, int(os.getenv("CYBERRED_DIRECTOR_RECOVERY_DELAY_S", "30"))
            )
        except ValueError:
            self._director_recovery_delay_s = 30
        try:
            self._director_recovery_cooldown_s = max(
                10, int(os.getenv("CYBERRED_DIRECTOR_RECOVERY_COOLDOWN_S", "90"))
            )
        except ValueError:
            self._director_recovery_cooldown_s = 90
        self._bus_subscriptions: list[Any] = []

        # Crash recovery / respawn
        self._stopping: bool = False
        self._respawn_counts: dict[str, int] = {}  # role -> respawn count
        self._respawn_target_role_counts: dict[str, int] = {}  # respawned role -> count
        # 0 = unlimited respawns (default). Set positive integer via env var
        # to enforce per-role respawn budget if desired.
        self._max_respawns_per_role: int = int(os.getenv("CYBERRED_MAX_RESPAWNS_PER_ROLE", "0"))
        self._crash_monitor: AgentCrashMonitor | None = None
        self._checkpoint_manager: Any = None
        try:
            self._agent_execution_timeout_s = max(
                60,
                int(os.getenv("CYBERRED_AGENT_EXEC_TIMEOUT_S", "1800")),
            )
        except ValueError:
            self._agent_execution_timeout_s = 1800

        # Stats
        self._jobs_processed = 0
        self._active_jobs = 0
        self._agents_created_total = 0
        self._agents_completed_total = 0
        self._role_completion_counts: dict[str, int] = {}

        # Progress watchdog (stall detection/recovery)
        self._stall_watchdog_task: asyncio.Task | None = None
        self._last_progress_at = time.monotonic()
        self._last_progress_jobs_processed = 0
        self._last_progress_findings_total = 0
        self._last_progress_findings_cycle = 0
        self._last_progress_strategy_ts = 0.0
        self._last_progress_role_completion_total = 0
        self._last_stall_replan_at = 0.0
        try:
            self._stall_timeout_s = max(60, int(os.getenv("CYBERRED_STALL_TIMEOUT_S", "900")))
        except ValueError:
            self._stall_timeout_s = 900
        try:
            self._stall_cooldown_s = max(30, int(os.getenv("CYBERRED_STALL_COOLDOWN_S", "300")))
        except ValueError:
            self._stall_cooldown_s = 300
        try:
            self._stall_hard_timeout_s = max(
                self._stall_timeout_s + 60,
                int(os.getenv("CYBERRED_STALL_HARD_TIMEOUT_S", str(self._stall_timeout_s * 2))),
            )
        except ValueError:
            self._stall_hard_timeout_s = self._stall_timeout_s * 2

        # Resource contract and runtime pressure governor.
        self._resource_contract: dict[str, Any] = {}
        self._resource_policy: dict[str, Any] = {}
        self._pressure_state: str = "NORMAL"
        self._pressure_reasons: list[str] = []
        self._pressure_metrics: dict[str, Any] = {}
        self._pressure_state_since: float = time.monotonic()
        self._scale_block_reason: str | None = None
        self._dispatch_paused: bool = False
        self._resource_monitor_task: asyncio.Task | None = None
        try:
            self._resource_monitor_interval_s = max(
                5,
                int(os.getenv("CYBERRED_RESOURCE_MONITOR_INTERVAL_S", "15")),
            )
        except ValueError:
            self._resource_monitor_interval_s = 15
        self._last_arp_table_fulls: int | None = None
        self._container_quarantine_enabled = _env_bool(
            "CYBERRED_CONTAINER_QUARANTINE_ENABLED",
            True,
        )
        try:
            self._container_quarantine_cpu_pct = max(
                0.0,
                float(os.getenv("CYBERRED_CONTAINER_QUARANTINE_CPU_PCT", "450.0")),
            )
        except ValueError:
            self._container_quarantine_cpu_pct = 450.0
        try:
            self._container_quarantine_zombie_threshold = max(
                0,
                int(os.getenv("CYBERRED_CONTAINER_QUARANTINE_ZOMBIE_THRESHOLD", "1000")),
            )
        except ValueError:
            self._container_quarantine_zombie_threshold = 1000
        try:
            self._container_quarantine_cooldown_s = max(
                30.0,
                float(os.getenv("CYBERRED_CONTAINER_QUARANTINE_COOLDOWN_S", "300")),
            )
        except ValueError:
            self._container_quarantine_cooldown_s = 300.0
        targets_raw = os.getenv("CYBERRED_CONTAINER_QUARANTINE_TARGETS", "cyber-range-")
        parsed_targets = tuple(
            token.strip()
            for token in targets_raw.split(",")
            if token.strip()
        )
        self._container_quarantine_targets: tuple[str, ...] = parsed_targets or ("cyber-range-",)
        self._container_quarantine_last_action: dict[str, float] = {}
        self._container_quarantine_inflight: set[str] = set()
        self._container_quarantine_events_total = 0
        self._container_quarantine_success_total = 0
        self._container_quarantine_failure_total = 0
        self._pressure_elevated_strikes = 0
        self._pressure_critical_strikes = 0
        self._pressure_clear_strikes = 0
        try:
            self._llm_queue_elevated_depth = max(
                1,
                int(os.getenv("CYBERRED_LLM_QUEUE_ELEVATED_DEPTH", "24")),
            )
        except ValueError:
            self._llm_queue_elevated_depth = 24
        try:
            self._llm_queue_critical_depth = max(
                self._llm_queue_elevated_depth + 1,
                int(os.getenv("CYBERRED_LLM_QUEUE_CRITICAL_DEPTH", "48")),
            )
        except ValueError:
            self._llm_queue_critical_depth = max(
                self._llm_queue_elevated_depth + 1,
                48,
            )
        try:
            self._launch_backpressure_sleep_s = max(
                0.05,
                float(os.getenv("CYBERRED_AGENT_LAUNCH_BACKPRESSURE_SLEEP_S", "0.5")),
            )
        except ValueError:
            self._launch_backpressure_sleep_s = 0.5
        try:
            self._agent_launch_base_delay_s = max(
                0.0,
                float(os.getenv("CYBERRED_AGENT_LAUNCH_BASE_DELAY_S", "0.05")),
            )
        except ValueError:
            self._agent_launch_base_delay_s = 0.05
        try:
            self._launch_backpressure_max_wait_s = max(
                5.0,
                float(os.getenv("CYBERRED_AGENT_LAUNCH_BACKPRESSURE_MAX_WAIT_S", "180")),
            )
        except ValueError:
            self._launch_backpressure_max_wait_s = 180.0

        # Director runtime diagnostics.
        self._director_last_failure_type: str | None = None
        self._director_cycle_lock = asyncio.Lock()
        self._last_director_queue_defer_at = 0.0
        try:
            self._director_cycle_timeout_s = max(
                120.0,
                float(os.getenv("CYBERRED_DIRECTOR_CYCLE_TIMEOUT_S", "1200")),
            )
        except ValueError:
            self._director_cycle_timeout_s = 1200.0
        try:
            self._director_trigger_timeout_s = max(
                self._director_cycle_timeout_s + 60.0,
                float(os.getenv("CYBERRED_DIRECTOR_TRIGGER_TIMEOUT_S", "1320")),
            )
        except ValueError:
            self._director_trigger_timeout_s = self._director_cycle_timeout_s + 120.0
        try:
            self._director_queue_defer_cooldown_s = max(
                5.0,
                float(os.getenv("CYBERRED_DIRECTOR_QUEUE_DEFER_COOLDOWN_S", "30")),
            )
        except ValueError:
            self._director_queue_defer_cooldown_s = 30.0

        # Dynamic spawning target state (incremental + recovery aware).
        self._desired_agent_count: int = 0
        self._latest_strategy_payload: dict[str, Any] | None = None
        self._respawn_debt_queue: deque[dict[str, Any]] = deque()
        self._pending_scale_hints: deque[dict[str, Any]] = deque()
        self._scale_hint_seen: dict[str, float] = {}
        self._scale_hint_last_prune_at: float = 0.0
        self._spawn_reconcile_task: asyncio.Task | None = None
        try:
            self._spawn_reconcile_interval_s = max(
                2.0,
                float(os.getenv("CYBERRED_SPAWN_RECONCILE_INTERVAL_S", "8")),
            )
        except ValueError:
            self._spawn_reconcile_interval_s = 8.0
        try:
            self._spawn_reconcile_batch_size = max(
                1,
                min(3, int(os.getenv("CYBERRED_SPAWN_RECONCILE_BATCH_SIZE", "3"))),
            )
        except ValueError:
            self._spawn_reconcile_batch_size = 3
        self._spawn_reconcile_wakeup = asyncio.Event()
        self._last_spawn_reconcile_reason: str | None = None
        try:
            self._scale_hint_ttl_s = max(
                30.0,
                float(os.getenv("CYBERRED_SCALE_HINT_TTL_S", "600")),
            )
        except ValueError:
            self._scale_hint_ttl_s = 600.0
        try:
            self._scale_hint_max_backlog = max(
                16,
                int(os.getenv("CYBERRED_SCALE_HINT_MAX_BACKLOG", "512")),
            )
        except ValueError:
            self._scale_hint_max_backlog = 512
        try:
            self._respawn_debt_max_backlog = max(
                16,
                int(os.getenv("CYBERRED_RESPAWN_DEBT_MAX_BACKLOG", "1024")),
            )
        except ValueError:
            self._respawn_debt_max_backlog = 1024
        try:
            self._scale_hint_max_attempts = max(
                3,
                int(os.getenv("CYBERRED_SCALE_HINT_MAX_ATTEMPTS", "20")),
            )
        except ValueError:
            self._scale_hint_max_attempts = 20
        try:
            self._spawn_llm_latency_elevated_ms = max(
                1_000.0,
                float(os.getenv("CYBERRED_SPAWN_LLM_LATENCY_ELEVATED_MS", "120000")),
            )
        except ValueError:
            self._spawn_llm_latency_elevated_ms = 120000.0
        self._scale_triggers_total = 0
        self._scale_hints_enqueued_total = 0
        self._scale_hints_processed_total = 0
        self._scale_hints_deduped_total = 0
        self._scale_hints_dropped_total = 0
        self._scale_hints_requeued_total = 0
        self._respawn_debt_enqueued_total = 0
        self._respawn_debt_drained_total = 0
        self._respawn_debt_dropped_total = 0
        self._reconcile_topups_total = 0
        self._spawn_hydrated_total = 0
        self._spawn_reconcile_wakeups_total = 0
        self._spawn_blocked_no_slots_total = 0
        self._spawn_blocked_llm_total = 0
        self._spawn_blocked_pressure_total = 0
        self._desired_cap_clamps_total = 0
        self._dynamic_scale_subscription_active = False
        self._worker_status_scale_subscription_active = False

    def _load_models_config(self, config_path: str = "config/models.yaml") -> dict[str, Any]:
        """Load models configuration from YAML (best-effort)."""
        try:
            import yaml

            path = Path(config_path)
            if not path.exists():
                return {}
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            return data if isinstance(data, dict) else {}
        except Exception as e:
            self.logger.warning(f"Could not load models config from {config_path}: {e}")
            return {}

    def _resolve_director_rag_policy(self) -> dict[str, Any]:
        """Resolve Director RAG policy from models config with safe defaults."""
        config = self._models_config or self._load_models_config()
        rag_cfg = config.get("rag", {}) if isinstance(config, dict) else {}
        if not isinstance(rag_cfg, dict):
            rag_cfg = {}
        director_cfg = rag_cfg.get("director", {})
        if not isinstance(director_cfg, dict):
            director_cfg = {}

        def _safe_float(value: Any, default: float, *, minimum: float = 0.0) -> float:
            try:
                return max(minimum, float(value))
            except (TypeError, ValueError):
                return default

        def _safe_int(value: Any, default: int, *, minimum: int = 1) -> int:
            try:
                return max(minimum, int(value))
            except (TypeError, ValueError):
                return default

        def _safe_bool(value: Any, default: bool) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "yes", "on"}:
                    return True
                if normalized in {"0", "false", "no", "off"}:
                    return False
                return default
            if isinstance(value, (int, float)):
                return bool(value)
            return default

        policy = {
            "query_timeout_s": _safe_float(
                director_cfg.get("query_timeout"),
                DirectorRAGClient.DEFAULT_TIMEOUT_S,
                minimum=0.05,
            ),
            "max_results": _safe_int(
                director_cfg.get("max_results"),
                DirectorRAGClient.DEFAULT_TOP_K,
                minimum=1,
            ),
            "fallback_on_timeout": _safe_bool(
                director_cfg.get("fallback_on_timeout"),
                True,
            ),
            "min_score": _safe_float(
                director_cfg.get("min_score"),
                0.0,
                minimum=0.0,
            ),
            "deadline_guard_s": _safe_float(
                director_cfg.get("deadline_guard_s"),
                0.05,
                minimum=0.0,
            ),
        }
        policy["min_score"] = min(1.0, policy["min_score"])
        return policy

    def _execution_capacity_hint(self) -> int | None:
        """Return best-available worker capacity hint for spawning."""
        try:
            pool_status = self.pool.get_pool_status()
            workers = pool_status.get("workers", {})
            if isinstance(workers, dict) and workers:
                healthy = sum(
                    1
                    for state in workers.values()
                    if str(state).lower() not in {"offline", "missing"}
                )
                if healthy > 0:
                    return healthy
                return len(workers)
            available = int(pool_status.get("available", 0))
            if available > 0:
                return available
        except Exception:
            pass
        pool_size = getattr(self.pool, "pool_size", None)
        if isinstance(pool_size, int) and pool_size > 0:
            return pool_size
        return None

    def _get_llm_queue_snapshot(self) -> dict[str, Any]:
        """Return current LLM queue and inflight snapshot."""
        snapshot: dict[str, Any] = {
            "total_queue_depth": 0,
            "director_queue_depth": 0,
            "agent_queue_depth": 0,
            "agent_inflight": 0,
            "max_agent_inflight": 0,
        }
        try:
            gateway = get_gateway()
        except Exception:
            return snapshot

        try:
            snapshot["total_queue_depth"] = int(getattr(gateway, "queue_depth", 0) or 0)
        except Exception:
            snapshot["total_queue_depth"] = 0
        try:
            snapshot["director_queue_depth"] = int(
                getattr(gateway, "director_queue_depth", 0) or 0
            )
        except Exception:
            snapshot["director_queue_depth"] = 0
        try:
            snapshot["agent_queue_depth"] = int(getattr(gateway, "agent_queue_depth", 0) or 0)
        except Exception:
            snapshot["agent_queue_depth"] = 0
        try:
            snapshot["agent_inflight"] = int(getattr(gateway, "agent_inflight", 0) or 0)
        except Exception:
            snapshot["agent_inflight"] = 0
        try:
            snapshot["max_agent_inflight"] = int(
                getattr(gateway, "max_agent_inflight", 0) or 0
            )
        except Exception:
            snapshot["max_agent_inflight"] = 0
        return snapshot

    async def _await_launch_backpressure_relief(
        self,
        *,
        phase: str,
        ordinal: int,
        total: int,
    ) -> dict[str, Any]:
        """Wait for queue/pressure relief before launching another agent."""
        waited_s = 0.0
        warned = False
        snapshot = self._get_llm_queue_snapshot()
        while not self._stopping:
            queue_depth = int(snapshot.get("total_queue_depth", 0))
            pressure_critical = self._pressure_state == "CRITICAL"
            queue_critical = queue_depth >= self._llm_queue_critical_depth

            if not pressure_critical and not queue_critical:
                return snapshot

            if not warned:
                warned = True
                self.logger.warning(
                    "agent_launch_backpressure_wait",
                    phase=phase,
                    ordinal=ordinal,
                    total=total,
                    pressure_state=self._pressure_state,
                    queue_depth=queue_depth,
                    queue_critical_depth=self._llm_queue_critical_depth,
                )

            if waited_s >= self._launch_backpressure_max_wait_s:
                self.logger.warning(
                    "agent_launch_backpressure_timeout",
                    phase=phase,
                    ordinal=ordinal,
                    total=total,
                    waited_s=round(waited_s, 2),
                    pressure_state=self._pressure_state,
                    queue_depth=queue_depth,
                )
                return snapshot

            await asyncio.sleep(self._launch_backpressure_sleep_s)
            waited_s += self._launch_backpressure_sleep_s
            snapshot = self._get_llm_queue_snapshot()

        return snapshot

    def apply_resource_contract(self, contract: dict[str, Any] | None) -> None:
        """Apply session-level resource contract to orchestrator runtime."""
        contract = contract or {}
        self._resource_contract = dict(contract)
        policy = contract.get("policy", {})
        self._resource_policy = policy if isinstance(policy, dict) else {}

        director_budget = contract.get("director_budget_profile", {})
        if isinstance(director_budget, dict):
            cycle_timeout = director_budget.get("cycle_timeout_s")
            trigger_timeout = director_budget.get("trigger_timeout_s")
            if cycle_timeout is not None:
                try:
                    self._director_cycle_timeout_s = max(120.0, float(cycle_timeout))
                except (TypeError, ValueError):
                    pass
            if trigger_timeout is not None:
                try:
                    self._director_trigger_timeout_s = max(
                        self._director_cycle_timeout_s + 60.0,
                        float(trigger_timeout),
                    )
                except (TypeError, ValueError):
                    pass

        self.logger.info(
            "resource_contract_applied",
            max_agents_allowed_now=contract.get("max_agents_allowed_now"),
            max_parallel_tools_now=contract.get("max_parallel_tools_now"),
            min_worker_reserve=contract.get("min_worker_reserve"),
            director_cycle_timeout_s=self._director_cycle_timeout_s,
            director_trigger_timeout_s=self._director_trigger_timeout_s,
        )

    def _reset_dynamic_spawn_state(self) -> None:
        """Reset per-engagement dynamic-spawn tracking."""
        self._desired_agent_count = 0
        self._latest_strategy_payload = None
        self._respawn_debt_queue.clear()
        self._pending_scale_hints.clear()
        self._scale_hint_seen.clear()
        self._scale_hint_last_prune_at = 0.0
        self._scale_triggers_total = 0
        self._scale_hints_enqueued_total = 0
        self._scale_hints_processed_total = 0
        self._scale_hints_deduped_total = 0
        self._scale_hints_dropped_total = 0
        self._scale_hints_requeued_total = 0
        self._respawn_debt_enqueued_total = 0
        self._respawn_debt_drained_total = 0
        self._respawn_debt_dropped_total = 0
        self._reconcile_topups_total = 0
        self._spawn_hydrated_total = 0
        self._spawn_reconcile_wakeups_total = 0
        self._spawn_blocked_no_slots_total = 0
        self._spawn_blocked_llm_total = 0
        self._spawn_blocked_pressure_total = 0
        self._desired_cap_clamps_total = 0
        self._last_spawn_reconcile_reason = None
        if hasattr(self, "_spawn_reconcile_wakeup"):
            self._spawn_reconcile_wakeup.clear()

    def _effective_agent_cap(self) -> int:
        """Resolve current hard cap for desired swarm size."""
        contract_cap = 0
        try:
            contract_cap = int(self._resource_contract.get("max_agents_allowed_now") or 0)
        except (TypeError, ValueError):
            contract_cap = 0

        spawn_cap = 0
        if self.spawner and hasattr(self.spawner, "_effective_spawn_limit"):
            try:
                spawn_cap = int(self.spawner._effective_spawn_limit())
            except Exception:
                spawn_cap = 0

        caps = [cap for cap in (contract_cap, spawn_cap) if isinstance(cap, int) and cap > 0]
        if caps:
            return max(1, min(caps))
        return 10_000

    def _current_active_agent_count(self) -> int:
        """Return current active agent count from spawner accounting."""
        if self.spawner and hasattr(self.spawner, "get_active_count"):
            try:
                return max(0, int(self.spawner.get_active_count()))
            except Exception:
                pass
        return max(0, len(self.agents))

    def _set_desired_agent_count(
        self,
        desired: int,
        *,
        reason: str,
        allow_decrease: bool = False,
    ) -> int:
        """Set desired swarm size with clamping and optional monotonic behavior."""
        requested = max(0, int(desired))
        cap = self._effective_agent_cap()
        requested = min(requested, cap)
        previous = self._desired_agent_count
        if not allow_decrease and requested < previous:
            requested = previous
        self._desired_agent_count = requested
        if requested != previous:
            self.logger.info(
                "desired_agent_count_updated",
                previous=previous,
                desired=requested,
                reason=reason,
                cap=cap,
            )
        return requested

    def _increase_desired_agent_count(self, delta: int, *, reason: str) -> int:
        """Increase desired swarm size by delta (best effort)."""
        delta = int(delta)
        if delta <= 0:
            return self._desired_agent_count
        return self._set_desired_agent_count(
            self._desired_agent_count + delta,
            reason=reason,
            allow_decrease=False,
        )

    def _agent_deficit(self) -> int:
        """Return deficit between desired and active agent counts."""
        return max(0, self._desired_agent_count - self._current_active_agent_count())

    def _signal_spawn_reconcile(self, reason: str) -> None:
        """Wake reconcile loop immediately for slot-driven spawning."""
        self._last_spawn_reconcile_reason = reason
        self._spawn_reconcile_wakeups_total = int(
            getattr(self, "_spawn_reconcile_wakeups_total", 0)
        ) + 1
        wake_event = getattr(self, "_spawn_reconcile_wakeup", None)
        if wake_event:
            wake_event.set()

    def _available_spawn_slots(self) -> int:
        """Return currently available spawn slots from spawner/cap accounting."""
        if self.spawner and hasattr(self.spawner, "available_slots"):
            try:
                return max(0, int(self.spawner.available_slots()))
            except Exception:
                pass
        return max(0, self._effective_agent_cap() - self._current_active_agent_count())

    def _spawn_llm_block_reason(self) -> str | None:
        """Return blocking reason when LLM queue is too saturated for more spawns."""
        snapshot = self._get_llm_queue_snapshot()
        queue_depth = int(snapshot.get("total_queue_depth", 0))
        if queue_depth >= self._llm_queue_critical_depth:
            return (
                f"llm_queue_depth={queue_depth}"
                f">=critical={self._llm_queue_critical_depth}"
            )
        inflight = int(snapshot.get("agent_inflight", 0))
        inflight_cap = int(snapshot.get("max_agent_inflight", 0))
        if (
            inflight_cap > 0
            and inflight >= inflight_cap
            and queue_depth >= max(2, self._llm_queue_elevated_depth // 2)
        ):
            return f"llm_inflight={inflight}/{inflight_cap}"
        if (
            queue_depth >= self._llm_queue_elevated_depth
            and inflight_cap > 0
            and inflight >= max(1, int(inflight_cap * 0.85))
        ):
            return (
                f"llm_queue_depth={queue_depth}"
                f">=elevated={self._llm_queue_elevated_depth}"
            )
        try:
            gateway = get_gateway()
            avg_latency_ms = float(getattr(gateway, "avg_latency_ms", 0.0) or 0.0)
        except Exception:
            avg_latency_ms = 0.0
        if (
            avg_latency_ms >= self._spawn_llm_latency_elevated_ms
            and queue_depth > 0
            and inflight_cap > 0
            and inflight >= max(1, int(inflight_cap * 0.75))
        ):
            return (
                f"llm_avg_latency_ms={avg_latency_ms:.0f}"
                f">=threshold={self._spawn_llm_latency_elevated_ms:.0f}"
            )
        return None

    def _resolve_strategy_for_hydration(self) -> Any | None:
        """Pick best-available strategy object for new-agent hydration."""
        for agent in self.agents.values():
            strategy_obj = getattr(agent, "_active_strategy", None)
            if strategy_obj:
                return strategy_obj

        payload = self._latest_strategy_payload
        if isinstance(payload, dict) and payload:
            try:
                return SimpleNamespace(
                    id=str(payload.get("id") or f"strategy-{int(time.time())}"),
                    objectives=list(payload.get("objectives", [])),
                    recommended_techniques=list(payload.get("recommended_techniques", [])),
                    avoid_targets=list(payload.get("avoid_targets", [])),
                )
            except Exception:
                return None
        return None

    def _hydrate_spawned_agents(
        self,
        agents: list[Any],
        *,
        source: str,
    ) -> int:
        """Hydrate newly spawned agents with latest swarm context."""
        if not agents:
            return 0
        findings = self._collect_hydration_findings(limit=50)
        strategy = self._resolve_strategy_for_hydration()
        hydrated = 0
        for agent in agents:
            hydrate_context = getattr(agent, "hydrate_context", None)
            if not callable(hydrate_context):
                continue
            try:
                hydrate_context(findings, strategy, runtime_state=None)
                hydrated += 1
            except Exception as e:
                self.logger.warning(
                    "spawn_hydration_failed",
                    source=source,
                    agent_id=getattr(agent, "agent_id", "unknown"),
                    error=str(e),
                )
        if hydrated > 0:
            self._spawn_hydrated_total += hydrated
            self.logger.info(
                "spawn_hydration_applied",
                source=source,
                agents=hydrated,
                findings=len(findings),
                has_strategy=bool(strategy),
            )
        return hydrated

    def _estimate_scale_demand(self, targets: list[Target]) -> int:
        """Estimate desired-agent increase implied by target hints."""
        weights = {
            "network": 10,
            "webapp": 5,
            "wireless": 3,
            "domain": 8,
        }
        return sum(weights.get(str(target.type), 0) for target in targets)

    def _prune_scale_hint_cache(self, now: float) -> None:
        """Prune expired scale-hint dedupe entries."""
        prune_interval = max(10.0, self._scale_hint_ttl_s * 0.25)
        if now - self._scale_hint_last_prune_at < prune_interval:
            return
        self._scale_hint_last_prune_at = now
        cutoff = now - self._scale_hint_ttl_s
        stale_keys = [key for key, seen_at in self._scale_hint_seen.items() if seen_at < cutoff]
        for key in stale_keys:
            self._scale_hint_seen.pop(key, None)

    def _sanitize_discovery_target_value(self, raw_value: Any) -> str:
        """Normalize a discovery target candidate value."""
        if raw_value is None:
            return ""
        value = str(raw_value).strip().strip(",;")
        if not value:
            return ""
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https", "ftp", "ssh", "ws"} and parsed.netloc:
            return value
        value = value.strip("[]")
        if ":" in value and value.count(":") == 1:
            host, port = value.rsplit(":", 1)
            if host and port.isdigit():
                value = host
        return value

    def _infer_discovery_target_type(
        self,
        *,
        finding_type: str,
        source_key: str,
        value: str,
    ) -> str:
        """Infer DynamicSpawner Target type from finding payload fields."""
        finding_type = finding_type.lower()
        source_key = source_key.lower()
        value_lower = value.lower()

        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return "webapp"
        if source_key in {"url", "uri", "endpoint", "webapp"} or "web" in finding_type:
            return "webapp"

        if (
            source_key in {"ssid", "bssid", "wireless"}
            or "wireless" in finding_type
            or "wifi" in finding_type
            or "bluetooth" in finding_type
        ):
            return "wireless"

        if (
            source_key in {"domain", "fqdn"}
            or finding_type in {"subdomain", "dns_record", "domain_enum", "kerberoast", "dcsync"}
            or "domain" in finding_type
            or "dns" in finding_type
            or "kerberos" in finding_type
            or "ldap" in finding_type
        ):
            return "domain"

        try:
            ipaddress.ip_network(value, strict=False)
            return "network"
        except ValueError:
            pass
        try:
            ipaddress.ip_address(value)
            return "network"
        except ValueError:
            pass

        if "." in value_lower and ":" not in value_lower and "/" not in value_lower:
            if "domain" in finding_type or "dns" in finding_type:
                return "domain"
        return "network"

    def _derive_scale_targets_from_finding(
        self,
        channel: str,
        payload: dict[str, Any],
    ) -> list[Target]:
        """Extract scale-worthy target hints from one finding event."""
        if not isinstance(payload, dict):
            return []

        finding_data = payload.get("data")
        if not isinstance(finding_data, dict):
            finding_data = payload
        if not isinstance(finding_data, dict):
            return []

        event_engagement = str(
            finding_data.get("engagement_id")
            or payload.get("engagement_id")
            or ""
        ).strip()
        if self._engagement_id and event_engagement and event_engagement != self._engagement_id:
            return []

        finding_type = str(
            finding_data.get("type")
            or finding_data.get("finding_type")
            or ""
        ).strip().lower()
        if finding_type:
            exact = {
                "port_scan",
                "open_port",
                "service_detection",
                "subdomain",
                "dns_record",
                "web_tech",
                "banner_grab",
                "ssl_cert",
                "waf_detect",
                "domain_enum",
                "host_discovery",
                "network_discovery",
                "wireless_discovery",
            }
            tokenized = (
                "discover",
                "recon",
                "service",
                "subdomain",
                "dns",
                "domain",
                "network",
                "host",
                "wireless",
                "wifi",
                "web",
            )
            if finding_type not in exact and not any(token in finding_type for token in tokenized):
                return []

        candidates: list[tuple[str, Any]] = []
        for key in ("target", "host", "hostname", "fqdn", "domain", "url", "endpoint", "service_host"):
            if finding_data.get(key):
                candidates.append((key, finding_data.get(key)))

        metadata = finding_data.get("metadata")
        if isinstance(metadata, dict):
            for key in (
                "discovered_hosts",
                "discovered_domains",
                "discovered_webapps",
                "discovered_networks",
                "discovered_targets",
                "new_targets",
            ):
                values = metadata.get(key)
                if isinstance(values, list):
                    candidates.extend((key, value) for value in values)

        targets: list[Target] = []
        dedupe: set[tuple[str, str]] = set()
        for key, raw_value in candidates:
            value = self._sanitize_discovery_target_value(raw_value)
            if not value:
                continue
            target_type = self._infer_discovery_target_type(
                finding_type=finding_type,
                source_key=key,
                value=value,
            )
            dedupe_key = (target_type, value)
            if dedupe_key in dedupe:
                continue
            try:
                target = Target(value=value, type=target_type)
            except ValueError:
                continue
            dedupe.add(dedupe_key)
            targets.append(target)

        self.logger.debug(
            "scale_targets_derived",
            channel=channel,
            finding_type=finding_type or "unknown",
            count=len(targets),
        )
        return targets

    def _enqueue_scale_hints(self, targets: list[Target], *, reason: str) -> int:
        """Queue deduplicated dynamic scale hints for incremental processing."""
        if not targets:
            return 0

        now = time.monotonic()
        self._prune_scale_hint_cache(now)
        accepted_targets: list[Target] = []

        for target in targets:
            cache_key = f"{target.type}:{target.value}".lower()
            seen_at = float(self._scale_hint_seen.get(cache_key, 0.0))
            if seen_at and (now - seen_at) < self._scale_hint_ttl_s:
                self._scale_hints_deduped_total += 1
                continue

            if len(self._pending_scale_hints) >= self._scale_hint_max_backlog:
                self._scale_hints_dropped_total += 1
                self.logger.warning(
                    "scale_hint_drop_backlog_full",
                    backlog=self._scale_hint_max_backlog,
                    target=f"{target.type}:{target.value}",
                )
                continue

            self._scale_hint_seen[cache_key] = now
            self._pending_scale_hints.append(
                {
                    "target": target,
                    "reason": reason,
                    "attempts": 0,
                    "enqueued_at": time.time(),
                }
            )
            self._scale_hints_enqueued_total += 1
            accepted_targets.append(target)

        if accepted_targets:
            desired_delta = self._estimate_scale_demand(accepted_targets)
            self._increase_desired_agent_count(
                desired_delta,
                reason=f"discovery_hint:{reason}",
            )

        return len(accepted_targets)

    async def _on_finding_for_dynamic_scaling(self, channel: str, payload: dict[str, Any]) -> None:
        """Handle finding events and enqueue dynamic scale hints."""
        if self._stopping or not self.spawner:
            return
        if not isinstance(payload, dict):
            return

        finding_data = payload.get("data")
        if not isinstance(finding_data, dict):
            finding_data = payload
        if str(finding_data.get("outcome_status", "validated")).strip().lower() == "failed":
            return
        reason = str(
            finding_data.get("type")
            or finding_data.get("finding_type")
            or "finding"
        ).strip().lower()

        targets = self._derive_scale_targets_from_finding(channel, payload)
        accepted = self._enqueue_scale_hints(targets, reason=reason)
        if accepted <= 0:
            return

        self.logger.info(
            "dynamic_scale_hint_enqueued",
            accepted=accepted,
            reason=reason,
            pending=len(self._pending_scale_hints),
            desired=self._desired_agent_count,
            active=self._current_active_agent_count(),
        )
        self._signal_spawn_reconcile("finding_hint")

    async def _subscribe_dynamic_scale_hints(self) -> None:
        """Subscribe to runtime signals used by slot-driven spawning."""
        if not self._dynamic_scale_subscription_active:
            self._bus_subscriptions.append(
                await self.bus.psubscribe("findings:*", self._on_finding_for_dynamic_scaling)
            )
            self._dynamic_scale_subscription_active = True
        if not self._worker_status_scale_subscription_active:
            self._bus_subscriptions.append(
                await self.bus.subscribe("swarm:worker_status", self._on_worker_status_for_spawn)
            )
            self._worker_status_scale_subscription_active = True

    async def _on_worker_status_for_spawn(self, data: dict[str, Any]) -> None:
        """Wake spawn reconcile loop when workers become available."""
        if self._stopping or not isinstance(data, dict):
            return
        status = str(data.get("status", "")).strip().lower()
        if status in {"idle", "ready"}:
            self._signal_spawn_reconcile("worker_idle")

    def _record_respawn_debt(
        self,
        *,
        role_value: str,
        reason: str,
        target: str,
        job_data: dict[str, Any],
    ) -> None:
        """Persist suppressed respawn intent for later reconciliation."""
        if len(self._respawn_debt_queue) >= self._respawn_debt_max_backlog:
            self._respawn_debt_queue.popleft()
            self._respawn_debt_dropped_total += 1

        self._respawn_debt_queue.append(
            {
                "source_role": role_value,
                "reason": reason,
                "target": target,
                "job_data": dict(job_data),
                "attempts": 0,
                "enqueued_at": time.time(),
            }
        )
        self._respawn_debt_enqueued_total += 1
        self._signal_spawn_reconcile("respawn_debt")

    def _start_spawn_reconcile_loop(self) -> None:
        """Start periodic reconciliation loop for spawn debt/deficit."""
        if self._spawn_reconcile_task and not self._spawn_reconcile_task.done():
            return
        self._spawn_reconcile_wakeup.clear()
        self._spawn_reconcile_task = asyncio.create_task(self._spawn_reconcile_loop())
        self._signal_spawn_reconcile("startup")

    async def _stop_spawn_reconcile_loop(self) -> None:
        """Stop periodic spawn reconciliation loop."""
        if self._spawn_reconcile_task is None:
            return
        self._spawn_reconcile_task.cancel()
        try:
            await self._spawn_reconcile_task
        except asyncio.CancelledError:
            pass
        finally:
            self._spawn_reconcile_task = None
            self._spawn_reconcile_wakeup.clear()

    async def _drain_respawn_debt(
        self,
        *,
        budget: int,
        default_target: str,
        default_job_data: dict[str, Any],
    ) -> int:
        """Drain queued respawn debt entries incrementally."""
        if budget <= 0:
            return 0
        launched = 0
        processed = 0
        while (
            processed < budget
            and self._respawn_debt_queue
            and not self._stopping
            and not self._dispatch_paused
        ):
            if self._available_spawn_slots() <= 0:
                self._spawn_blocked_no_slots_total += 1
                break

            entry = self._respawn_debt_queue.popleft()
            processed += 1

            role_value = str(entry.get("source_role") or "recon")
            reason = str(entry.get("reason") or "failed")
            target = str(entry.get("target") or default_target)
            job_data = entry.get("job_data")
            if not isinstance(job_data, dict):
                job_data = default_job_data
            else:
                job_data = dict(job_data)

            try:
                role = AgentRole(role_value)
            except ValueError:
                role = AgentRole.RECON

            debt_agent = SimpleNamespace(
                agent_id=f"debt-{int(time.time() * 1000)}-{processed}",
                role=role,
                _active_strategy=self._resolve_strategy_for_hydration(),
            )

            success = False
            try:
                success = await self._respawn_agent(
                    debt_agent,
                    target,
                    job_data,
                    reason=reason,
                )
            except Exception as e:
                self.logger.warning(f"Respawn debt drain failed: {e}")

            if success:
                launched += 1
                self._respawn_debt_drained_total += 1
                continue

            attempts = int(entry.get("attempts", 0)) + 1
            entry["attempts"] = attempts
            transient = self._dispatch_paused or self._pressure_state == "CRITICAL"
            if transient and attempts <= 3 and not self._stopping:
                self._respawn_debt_queue.appendleft(entry)
                break
            self._respawn_debt_dropped_total += 1

        return launched

    async def _drain_scale_hints(
        self,
        *,
        budget: int,
        target: str,
        job_data: dict[str, Any],
        engagement_id: str,
    ) -> int:
        """Process queued scale hints incrementally (bounded per cycle)."""
        if budget <= 0 or not self.spawner:
            return 0

        launched_agents = 0
        processed_hints = 0
        while (
            processed_hints < budget
            and self._pending_scale_hints
            and not self._stopping
            and not self._dispatch_paused
        ):
            hint = self._pending_scale_hints.popleft()
            enqueued_at = float(hint.get("enqueued_at") or time.time())
            if time.time() - enqueued_at > self._scale_hint_ttl_s:
                self._scale_hints_dropped_total += 1
                self.logger.info(
                    "scale_hint_expired",
                    age_s=round(time.time() - enqueued_at, 2),
                    ttl_s=self._scale_hint_ttl_s,
                )
                continue

            if self._available_spawn_slots() <= 0:
                self._pending_scale_hints.appendleft(hint)
                self._scale_hints_requeued_total += 1
                self._spawn_blocked_no_slots_total += 1
                break

            llm_block_reason = self._spawn_llm_block_reason()
            if llm_block_reason:
                self._pending_scale_hints.appendleft(hint)
                self._scale_hints_requeued_total += 1
                self._spawn_blocked_llm_total += 1
                break

            target_obj = hint.get("target")
            if not isinstance(target_obj, Target):
                continue

            reason = str(hint.get("reason") or "finding")
            try:
                spawned = await self.spawner.scale_up(
                    [target_obj],
                    reason=f"discovery:{reason}",
                )
            except Exception as e:
                self.logger.warning(f"Dynamic scale-up failed: {e}")
                spawned = []

            if not spawned:
                attempts = int(hint.get("attempts", 0)) + 1
                hint["attempts"] = attempts
                if attempts <= self._scale_hint_max_attempts and not self._dispatch_paused and not self._stopping:
                    self._pending_scale_hints.appendleft(hint)
                    self._scale_hints_requeued_total += 1
                    break
                self._scale_hints_dropped_total += 1
                self.logger.warning(
                    "scale_hint_drop_exhausted",
                    attempts=attempts,
                    max_attempts=self._scale_hint_max_attempts,
                    reason=reason,
                )
                continue

            processed_hints += 1
            self._scale_hints_processed_total += 1
            self._scale_triggers_total += 1
            self._hydrate_spawned_agents(spawned, source="discovery_scale")
            await self._launch_spawned_agents(
                spawned,
                target,
                job_data,
                engagement_id,
                phase_label="discovery_scale",
                hydrate=False,
            )
            launched_agents += len(spawned)

        return launched_agents

    async def _spawn_reconcile_loop(self) -> None:
        """Continuously reconcile desired swarm size against active workers."""
        try:
            while not self._stopping:
                try:
                    await asyncio.wait_for(
                        self._spawn_reconcile_wakeup.wait(),
                        timeout=self._spawn_reconcile_interval_s,
                    )
                except asyncio.TimeoutError:
                    pass
                self._spawn_reconcile_wakeup.clear()
                if self._stopping:
                    break
                if not self.spawner or not self._engagement_id:
                    continue

                if hasattr(self.spawner, "set_execution_capacity"):
                    try:
                        self.spawner.set_execution_capacity(self._execution_capacity_hint())
                    except Exception:
                        pass

                previous_desired = self._desired_agent_count
                self._set_desired_agent_count(
                    self._desired_agent_count,
                    reason="reconcile_cap_sync",
                    allow_decrease=True,
                )
                if self._desired_agent_count < previous_desired:
                    self._desired_cap_clamps_total += 1

                if self._dispatch_paused:
                    self._spawn_blocked_pressure_total += 1
                    continue

                available_slots = self._available_spawn_slots()
                if available_slots <= 0:
                    self._spawn_blocked_no_slots_total += 1
                    continue

                llm_block_reason = self._spawn_llm_block_reason()
                if llm_block_reason:
                    self._spawn_blocked_llm_total += 1
                    continue

                engagement_id = self._engagement_id or "default"
                primary_target = self._resolve_primary_target() or "127.0.0.1"
                base_job_data = {
                    "target": primary_target,
                    "full_attack": True,
                    "phase": self._current_phase,
                }

                cycle_budget = min(self._spawn_reconcile_batch_size, available_slots)
                if cycle_budget <= 0:
                    self._spawn_blocked_no_slots_total += 1
                    continue
                launched_agents = 0
                launched_agents += await self._drain_respawn_debt(
                    budget=cycle_budget,
                    default_target=primary_target,
                    default_job_data=base_job_data,
                )

                remaining_budget = max(0, cycle_budget - launched_agents)
                if remaining_budget > 0:
                    launched_agents += await self._drain_scale_hints(
                        budget=remaining_budget,
                        target=primary_target,
                        job_data=base_job_data,
                        engagement_id=engagement_id,
                    )

                remaining_budget = max(0, cycle_budget - launched_agents)
                if remaining_budget <= 0:
                    continue

                deficit = self._agent_deficit()
                if deficit <= 0:
                    continue
                available_slots = self._available_spawn_slots()
                if available_slots <= 0:
                    self._spawn_blocked_no_slots_total += 1
                    continue
                top_up_count = min(deficit, remaining_budget, available_slots)
                if top_up_count <= 0:
                    self._spawn_blocked_no_slots_total += 1
                    continue

                try:
                    spawned = await self.spawner.top_up(
                        top_up_count,
                        reason="reconcile_deficit",
                    )
                except Exception as e:
                    self.logger.warning(f"Reconcile top-up failed: {e}")
                    continue

                if not spawned:
                    continue

                self._reconcile_topups_total += len(spawned)
                self._hydrate_spawned_agents(spawned, source="reconcile_topup")
                await self._launch_spawned_agents(
                    spawned,
                    primary_target,
                    base_job_data,
                    engagement_id,
                    phase_label="reconcile_topup",
                    hydrate=False,
                )
                if self._agent_deficit() > 0:
                    self._signal_spawn_reconcile("deficit_remaining")
        except asyncio.CancelledError:
            pass

    async def _check_director_model_health(
        self,
        api_key: str,
        model_id: str,
    ) -> tuple[str, bool, str | None]:
        """Run a lightweight health check for one Director model."""
        try:
            provider = NIMProvider(api_key=api_key, model=model_id)
            status = await asyncio.wait_for(provider.health_check(), timeout=20.0)
            return model_id, bool(status.healthy), status.error
        except Exception as e:
            return model_id, False, str(e)

    async def _assert_engagement_readiness(self, engagement_id: str) -> None:
        """Fail fast when core engagement dependencies are unavailable."""
        issues: list[str] = []
        warnings: list[str] = []

        try:
            await asyncio.wait_for(self.bus.redis.ping(), timeout=5.0)
        except Exception as e:
            issues.append(f"redis_unreachable: {e}")

        pool_status = self.pool.get_pool_status()
        try:
            available_workers = int(pool_status.get("available", 0))
        except (TypeError, ValueError):
            available_workers = 0
        worker_map = pool_status.get("workers", {})
        total_workers = len(worker_map) if isinstance(worker_map, dict) else 0
        if available_workers <= 0:
            issues.append("worker_pool_no_available_workers")
        elif total_workers > 0 and available_workers < min(total_workers, 3):
            warnings.append(
                f"worker_pool_low_capacity: {available_workers}/{total_workers} available"
            )

        worker_probe_id = await self.pool.acquire_worker(timeout=5.0)
        if not worker_probe_id:
            issues.append("worker_probe_acquire_failed")
        else:
            self.pool.release_worker(worker_probe_id)

        api_key = resolve_llm_api_key()
        if not api_key:
            issues.append("llm_api_key_missing")
        else:
            director_models = sorted(set(NIMProvider.DIRECTOR_MODELS.values()))
            model_health = await asyncio.gather(
                *[
                    self._check_director_model_health(api_key, model_id)
                    for model_id in director_models
                ]
            )
            healthy_models = [model for model, healthy, _ in model_health if healthy]
            unhealthy_models = [model for model, healthy, _ in model_health if not healthy]
            if len(healthy_models) < self._director_min_quorum:
                issues.append(
                    "director_models_below_quorum: "
                    f"{len(healthy_models)}/{self._director_min_quorum} healthy"
                )
            elif unhealthy_models:
                warnings.append(
                    "director_models_degraded: " + ", ".join(unhealthy_models)
                )

        if warnings:
            self.logger.warning(
                "engagement_readiness_warning",
                engagement_id=engagement_id,
                warnings=warnings,
            )
            try:
                await self.bus.publish("swarm:log", {
                    "category": "READINESS",
                    "message": "Readiness warnings: " + " | ".join(warnings),
                })
            except Exception:
                pass

        if issues:
            detail = " | ".join(issues)
            self.logger.error(
                "engagement_readiness_failed",
                engagement_id=engagement_id,
                issues=issues,
            )
            try:
                await self.bus.publish("swarm:log", {
                    "category": "ERROR",
                    "message": f"Engagement readiness failed: {detail}",
                })
            except Exception:
                pass
            raise RuntimeError(f"Engagement readiness failed: {detail}")

        self.logger.info(
            "engagement_readiness_passed",
            engagement_id=engagement_id,
            available_workers=available_workers,
            total_workers=total_workers,
            director_min_quorum=self._director_min_quorum,
        )

    async def start(self):
        """Start the Orchestrator and initialize all subsystems."""
        self.logger.info("Orchestrator initializing...")

        # Initialize LLM Gateway singleton (rate limiting, retry, priority queue)
        try:
            api_key = resolve_llm_api_key()
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = resolve_llm_api_key()

            providers = {
                TaskComplexity.FAST: NIMProvider.for_tier("FAST", api_key),
                TaskComplexity.STANDARD: NIMProvider.for_tier("STANDARD", api_key),
                TaskComplexity.COMPLEX: NIMProvider.for_tier("COMPLEX", api_key),
            }
            router = ModelRouter(providers=providers)
            from cyberred.core.config import get_settings

            settings = get_settings()
            try:
                rate_limit_rpm = max(
                    1,
                    int(
                        os.getenv(
                            "CYBERRED_LLM_RATE_LIMIT_RPM",
                            str(settings.llm.rate_limit),
                        )
                    ),
                )
            except ValueError:
                rate_limit_rpm = int(settings.llm.rate_limit)
            rate_limiter = RateLimiter(rpm=rate_limit_rpm, burst=5)
            queue = LLMPriorityQueue()
            retry_policy = RetryPolicy()
            try:
                gateway_workers = max(
                    2,
                    int(os.getenv("CYBERRED_LLM_GATEWAY_WORKERS", "25")),
                )
            except ValueError:
                gateway_workers = 25

            # Load model fallback mapping from config/models.yaml
            fallback_models = {}
            self._models_config = self._load_models_config()
            try:
                models_cfg = self._models_config
                if models_cfg:
                    fallback_cfg = models_cfg.get("fallback", {})
                    # Map primary model -> fallback model for each role
                    role_sections = {
                        "brain": ["architect", "strategist", "ghost"],
                        "governance": ["critic", "dispatcher"],
                        "code_generation": ["engineer", "coder"],
                    }
                    for section, roles in role_sections.items():
                        for role in roles:
                            primary = models_cfg.get(section, {}).get(role)
                            fallback = fallback_cfg.get(role)
                            if primary and fallback and primary != fallback:
                                fallback_models[primary] = fallback
                    self.logger.info(f"Loaded {len(fallback_models)} model fallbacks")
            except Exception as e:
                self.logger.warning(f"Could not load model fallbacks: {e}")

            gateway = initialize_gateway(
                rate_limiter,
                router,
                queue,
                retry_policy,
                fallback_models,
                num_workers=gateway_workers,
            )
            await gateway.start()
            self.logger.info(
                "LLM Gateway initialized",
                rate_limit_rpm=rate_limit_rpm,
                queue_mode="priority",
                gateway_workers=gateway_workers,
            )
        except RuntimeError:
            self.logger.info("LLM Gateway already initialized (reusing existing)")

        # KaliExecutor initialization deferred to _deploy_stigmergic_swarm()
        # because session_manager replaces self.pool AFTER __init__.

        # Set scope_path in settings so agents can load scope validator
        self._configure_scope_path()

        # Initialize worker pool
        await self.pool.initialize()

        # Always-on stigmergic bus logger — subscribes to key channels
        # for observability even without a TUI client attached.
        await self._start_stigmergic_logger()

        # Subscribe to job events
        self._bus_subscriptions.append(await self.bus.subscribe("job:new", self.handle_new_job))
        self._bus_subscriptions.append(await self.bus.subscribe("cmd:nlp", self.handle_nlp_command))
        self._bus_subscriptions.append(await self.bus.subscribe("cmd:quick", self.handle_quick_command))
        self._bus_subscriptions.append(await self.bus.subscribe("agent:stop", self.handle_stop_agent))

        # Publish ready status
        await self.bus.publish("swarm:log", {
            "category": "SYSTEM",
            "message": f"Orchestrator online. {len(self.tool_orchestrator.get_available_tools())} tools available."
        })

        self._start_progress_watchdog()
        self._start_resource_monitor()

        self.logger.info("Orchestrator online.")

    async def _start_stigmergic_logger(self) -> None:
        """Start always-on subscribers for key stigmergic channels.

        Ensures that swarm:log, swarm:brain, swarm:status, findings,
        and audit events are captured to structlog even without a TUI
        client attached. This provides observability and an audit trail
        for headless/daemon-only operation.
        """
        stig_log = logging.getLogger("StigmergicBus")

        async def _log_swarm_event(data: dict) -> None:
            category = data.get("category", "?")
            message = data.get("message", str(data))
            stig_log.info("[swarm:log] [%s] %s", category, message)

        async def _log_brain_event(data: dict) -> None:
            category = data.get("category", "?")
            text = data.get("text", str(data))
            stig_log.info("[swarm:brain] [%s] %s", category, text)

        async def _log_status_event(data: dict) -> None:
            agent_id = data.get("agent_id", "?")[:8]
            status = data.get("status", "?")
            role = data.get("role", "?")
            stig_log.debug("[swarm:status] %s (%s) -> %s", agent_id, role, status)

        async def _log_finding(channel: str, data: dict) -> None:
            agent_id = data.get("agent_id", "?")[:8]
            finding_data = data.get("data", {})
            f_type = finding_data.get("type", "?")
            target = finding_data.get("target", "?")
            stig_log.info("[finding] agent=%s type=%s target=%s channel=%s", agent_id, f_type, target, channel)

        try:
            self._bus_subscriptions.append(await self.bus.subscribe("swarm:log", _log_swarm_event))
            self._bus_subscriptions.append(await self.bus.subscribe("swarm:brain", _log_brain_event))
            self._bus_subscriptions.append(await self.bus.subscribe("swarm:status", _log_status_event))
            self._bus_subscriptions.append(await self.bus.psubscribe("findings:*", _log_finding))
            self.logger.info("Stigmergic bus logger started (always-on)")
        except Exception as e:
            self.logger.warning(f"Stigmergic bus logger failed to start: {e}")

    def _init_kali_executor(self) -> None:
        """Initialize the kali_execute() singleton for stigmergic agents.

        Creates a WorkerPoolBridge wrapping self.pool and a ScopeValidator
        from engagement config, then initializes the module-level executor.

        Called from _deploy_stigmergic_swarm() (not __init__) so that
        self.pool is the shared WorkerPool injected by session_manager.
        """
        try:
            from cyberred.tools.kali_executor import initialize_executor, _executor
            if _executor is not None:
                self.logger.info("KaliExecutor already initialized, skipping")
                return

            from cyberred.tools.container_pool import WorkerPoolBridge
            from cyberred.tools.scope import ScopeValidator, ScopeConfig

            # Build scope validator - prefer scope.yaml file, fall back to engagement config
            scope_validator: ScopeValidator
            scope_file_loaded = False

            # Try scope.yaml next to engagement config first
            if self._engagement_config:
                config_path = self._engagement_config.get("engagement_config_path", "")
                if config_path:
                    from pathlib import Path
                    scope_file = Path(config_path).parent / "scope.yaml"
                    if scope_file.exists():
                        scope_validator = ScopeValidator.from_file(scope_file)
                        scope_file_loaded = True
                        self.logger.info(f"KaliExecutor scope loaded from {scope_file}")

            if not scope_file_loaded:
                if self._engagement_config and "scope" in self._engagement_config:
                    scope_data = self._engagement_config["scope"]
                    allowed_targets = list(
                        scope_data.get("allowed_targets") or scope_data.get("allowed_ips", [])
                    )

                    # Auto-populate hostnames from engagement targets so
                    # Docker container names (dvwa, wordpress, …) pass scope.
                    targets_section = self._engagement_config.get("targets", {})
                    for target_name in targets_section:
                        if target_name not in allowed_targets:
                            allowed_targets.append(target_name)
                        # Also add IP if the target has one
                        tinfo = targets_section[target_name]
                        if isinstance(tinfo, dict) and tinfo.get("ip"):
                            ip = tinfo["ip"]
                            if ip not in allowed_targets:
                                allowed_targets.append(ip)

                    self.logger.info(
                        "scope_targets_resolved",
                        networks=[t for t in allowed_targets if '/' in t or t[0].isdigit()],
                        hostnames=[t for t in allowed_targets if not ('/' in t or t[0].isdigit())],
                    )

                    scope_validator = ScopeValidator.from_config({
                        "allowed_targets": allowed_targets,
                        "allowed_ports": scope_data.get("allowed_ports"),
                        "egress_allowlist": scope_data.get("egress_allowlist"),
                        "allow_private": scope_data.get("allow_private", True),
                        "allow_loopback": scope_data.get("allow_loopback", False),
                    })
                else:
                    # Permissive default - scope enforcement happens at agent level too
                    scope_validator = ScopeValidator(ScopeConfig(allow_private=True))

            # Bridge to the shared WorkerPool for real Docker execution
            container_pool = WorkerPoolBridge(self.pool)
            initialize_executor(container_pool, scope_validator)
            self.logger.info("KaliExecutor initialized with WorkerPoolBridge (real containers)")
        except Exception as e:
            self.logger.warning(f"KaliExecutor init failed (agents will use fallback): {e}")

    def _resolve_kali_manifest_path(self) -> Path | None:
        """Resolve kali manifest path from env/config with safe fallbacks."""
        candidates: list[Path] = []

        env_manifest = os.getenv("CYBERRED_KALI_MANIFEST_PATH", "").strip()
        if env_manifest:
            candidates.append(Path(env_manifest).expanduser())

        if self._engagement_config:
            config_manifest = (
                self._engagement_config.get("kali_manifest_path")
                or self._engagement_config.get("manifest_path")
            )
            if config_manifest:
                candidates.append(Path(str(config_manifest)).expanduser())

            config_path = self._engagement_config.get("engagement_config_path", "")
            if config_path:
                base_dir = Path(config_path).expanduser().parent
                candidates.append(base_dir / "kali-manifest.yaml")
                candidates.append(base_dir / "config" / "kali-manifest.yaml")

        repo_root = Path(__file__).resolve().parents[3]
        candidates.append(Path.cwd() / "config" / "kali-manifest.yaml")
        candidates.append(Path.cwd() / "kali-manifest.yaml")
        candidates.append(repo_root / "config" / "kali-manifest.yaml")

        seen: set[str] = set()
        for candidate in candidates:
            normalized = candidate.expanduser()
            key = str(normalized)
            if key in seen:
                continue
            seen.add(key)
            if normalized.exists():
                return normalized
        return None

    def _load_manifest_loader(self) -> Any | None:
        """Best-effort initialize Kali ManifestLoader."""
        try:
            from cyberred.tools.manifest import ManifestLoader

            manifest_path = self._resolve_kali_manifest_path()
            if not manifest_path:
                return None
            return ManifestLoader(manifest_path)
        except Exception as e:
            self.logger.warning(f"ManifestLoader init failed: {e}")
            return None

    def _configure_scope_path(self) -> None:
        """Set scope_path in global settings so agents can load the scope validator.

        If no scope.yaml exists on disk, generates one from the engagement
        config (scope IPs + target hostnames) so that agents' own
        ``_get_scope_validator()`` picks up the correct scope.
        """
        try:
            from cyberred.core.config import get_settings
            settings = get_settings()

            if not self._engagement_config:
                return

            base_scope_path = ""
            
            # Check for scope_path in config
            scope_path_in_config = self._engagement_config.get("scope_path", "")
            if scope_path_in_config:
                 base_scope_path = scope_path_in_config
            
            # Check for default scope.yaml
            if not base_scope_path:
                config_path = self._engagement_config.get("engagement_config_path", "")
                if config_path:
                    from pathlib import Path
                    default_scope = Path(config_path).parent / "scope.yaml"
                    if default_scope.exists():
                        base_scope_path = str(default_scope)

            # Always generate an engagement-specific scope file, merging 
            # the base scope (if any) with the specific targets.
            final_scope_path = self._generate_scope_file(base_scope_path)

            if final_scope_path:
                settings.engagement.scope_path = final_scope_path
                self.logger.info(f"Scope path set: {final_scope_path}")
            else:
                self.logger.warning("Failed to set scope path (generation failed)")

        except Exception as e:
            self.logger.warning(f"Failed to configure scope path: {e}")

    def _generate_scope_file(self, base_scope_path: str = "") -> str:
        """Generate a scope.yaml from engagement config and optional base scope.

        Merges base scope (allowed_targets, allowed_ips) with target names from
        the ``targets`` section so that Docker container hostnames are
        recognised as in-scope.

        Args:
            base_scope_path: Path to an existing scope.yaml to use as base.

        Returns:
            Path to the generated scope.yaml, or empty string on failure.
        """
        try:
            import yaml as _yaml
            from pathlib import Path

            if not self._engagement_config:
                 return ""

            allowed = []
            allowed_ports = None 
            egress_allowlist: list[str] = []
            allow_private = True
            allow_loopback = False

            # 1. Load from base scope file if provided
            if base_scope_path:
                try:
                    p = Path(base_scope_path)
                    if p.exists():
                        with p.open() as f:
                            base_data = _yaml.safe_load(f)
                            if base_data and "scope" in base_data:
                                s = base_data["scope"]
                                allowed.extend(s.get("allowed_targets", []))
                                allowed.extend(s.get("allowed_ips", []))
                                allowed_ports = s.get("allowed_ports")
                                egress_allowlist.extend(
                                    s.get("egress_allowlist", s.get("allowed_egress_hostnames", []))
                                )
                                allow_private = s.get("allow_private", True)
                                allow_loopback = s.get("allow_loopback", False)
                except Exception as e:
                    self.logger.warning(f"Failed to load base scope {base_scope_path}: {e}")

            # 2. Merge/Load from engagement config
            scope_data = self._engagement_config.get("scope", {})
            eng_allowed = list(
                scope_data.get("allowed_targets")
                or scope_data.get("allowed_ips", [])
            )
            for t in eng_allowed:
                if t not in allowed:
                    allowed.append(t)
            
            if scope_data.get("allowed_ports"):
                 # prefer engagement config ports if specified
                 allowed_ports = scope_data["allowed_ports"]

            for hostname in scope_data.get("egress_allowlist", []):
                if hostname not in egress_allowlist:
                    egress_allowlist.append(hostname)
            
            # 3. Add target hostnames (Docker container names)
            targets_section = self._engagement_config.get("targets", {})
            for target_name in targets_section:
                if target_name not in allowed:
                    allowed.append(target_name)
                tinfo = targets_section[target_name]
                if isinstance(tinfo, dict) and tinfo.get("ip"):
                    ip = tinfo["ip"]
                    if ip not in allowed:
                        allowed.append(ip)

            if not allowed:
                return ""

            scope_doc = {
                "scope": {
                    "allowed_targets": allowed,
                    "allow_private": allow_private,
                    "allow_loopback": allow_loopback,
                }
            }
            if allowed_ports:
                scope_doc["scope"]["allowed_ports"] = allowed_ports
            if egress_allowlist:
                scope_doc["scope"]["egress_allowlist"] = egress_allowlist

            # Write to engagement directory
            engagement_id = self._engagement_id or "default"
            eng_dir = Path.home() / ".cyber-red" / "engagements" / engagement_id
            eng_dir.mkdir(parents=True, exist_ok=True)
            scope_file = eng_dir / "scope.yaml"
            scope_file.write_text(_yaml.dump(scope_doc, default_flow_style=False))
            
            self.logger.info(
                "scope_file_generated",
                path=str(scope_file),
                targets=allowed,
            )
            return str(scope_file)
        except Exception as e:
            self.logger.warning(f"Failed to generate scope file: {e}")
            return ""

    async def handle_nlp_command(self, data: dict):
        """
        Handle natural language commands from the user.

        Uses the AI Dispatcher to parse intent and create jobs.
        """
        text = data.get("text", "").strip()
        if not text:
            return

        self.logger.info(f"Processing NLP command: {text}")

        # Log to brain stream that we're processing
        await self.bus.publish("swarm:brain", {
            "category": "DISPATCH",
            "text": f"Dispatching command: {text}"
        })

        # Parse Intent via Council (Dispatcher)
        intent = await self.council.parse_intent(text)
        self.logger.info(f"Intent parsed: {intent}")

        await self.bus.publish("swarm:brain", {
            "category": "DISPATCH",
            "text": f"Intent: {intent}"
        })


        if "error" in intent:
            await self.bus.publish("swarm:log", {
                "category": "ERROR",
                "message": f"Parse error: {intent['error']}"
            })
            return

        target = intent.get("target")
        action = intent.get("action", "scan")

        # Validate target
        if not target or target.lower() in ["none", "null", "", "unknown"]:
            await self.bus.publish("swarm:log", {
                "category": "ERROR",
                "message": f"No valid target found in: {text}"
            })
            return

        await self.bus.publish("swarm:log", {
            "category": "CMD",
            "message": f"Engaging {target} (action: {action})"
        })

        # Create job
        await self.handle_new_job({
            "target": target,
            "action": action,
            # ALWAYS use full War Room attack flow
            "full_attack": True
        })


    async def handle_quick_command(self, data: dict):
        """Handle quick scan commands (no full kill chain). Uses GhostAgent."""
        target = data.get("target")
        if not target:
            return

        agent_id = self._get_next_agent_id()
        agent = GhostAgent(
            agent_id,
            self.council,
            self.tool_orchestrator,
            self.bus
        )
        self.agents[agent_id] = agent

        # Run quick attack in background
        asyncio.create_task(agent.quick_attack(target))

        self.logger.info(f"Deployed GhostAgent-{agent_id} for quick scan of {target}")

    async def handle_new_job(self, data: dict):
        """
        Handle new attack job.

        For full attacks: spawns a stigmergic swarm using DynamicSpawner.
        For quick attacks: falls back to GhostAgent.
        """
        target = data.get("target")
        full_attack = data.get("full_attack", True)

        if not target:
            self.logger.warning("Job received without target")
            return

        if self._dispatch_paused:
            reason = self._scale_block_reason or "critical_resource_pressure"
            self.logger.warning(
                f"Dispatch paused due to pressure governor; skipping new job target={target} reason={reason}"
            )
            await self.bus.publish("swarm:log", {
                "category": "RESOURCE",
                "message": f"Dispatch paused; skipping new job for {target} ({reason})",
            })
            return

        if not full_attack:
            # Quick mode: use legacy GhostAgent
            await self._deploy_ghost_agent(target, full_attack=False)
            return

        # Full attack mode: use stigmergic swarm
        await self._deploy_stigmergic_swarm(target, data)

    async def _deploy_ghost_agent(self, target: str, full_attack: bool = True) -> None:
        """Deploy a GhostAgent for legacy/quick attack mode."""
        agent_id = self._get_next_agent_id()

        agent = GhostAgent(
            agent_id,
            self.council,
            self.tool_orchestrator,
            self.bus
        )
        self.agents[agent_id] = agent

        self._active_jobs += 1

        async def run_and_cleanup():
            try:
                if full_attack:
                    await agent.engage(target)
                else:
                    await agent.quick_attack(target)
            finally:
                self._active_jobs -= 1
                self._jobs_processed += 1

        asyncio.create_task(run_and_cleanup())

        self.logger.info(f"Deployed GhostAgent-{agent_id} against {target}")

        await self.bus.publish("swarm:log", {
            "category": "DEPLOY",
            "message": f"GhostAgent-{agent_id} deployed against {target}"
        })

    async def _deploy_stigmergic_swarm(self, target: str, job_data: dict) -> None:
        """Deploy a stigmergic agent swarm for full engagement attack.

        Builds a Scope from the target, uses DynamicSpawner to calculate
        the right number and distribution of agents, spawns them, and
        launches their role-specific execution methods.
        """
        self.logger.info(f"DEBUG: Entering _deploy_stigmergic_swarm. Config present: {bool(self._engagement_config)}")
        engagement_id = self._engagement_id or "default"
        self._stopping = False
        await self._stop_spawn_reconcile_loop()
        self._reset_dynamic_spawn_state()

        # Initialize kali_execute() singleton now — self.pool has been
        # replaced by session_manager with the shared WorkerPool.
        self._init_kali_executor()

        # Re-run scope configuration now that _engagement_config is populated
        # (the call in __init__ runs when config is still None).
        self._configure_scope_path()

        # Fail fast if engagement dependencies are unavailable.
        await self._assert_engagement_readiness(engagement_id)

        # Build scope from target(s)
        scope = self._build_scope_from_job(target, job_data)

        # Get LLM gateway for agent tool selection
        llm_gw = None
        manifest = None
        try:
            llm_gw = get_gateway()
        except RuntimeError:
            self.logger.warning("LLM Gateway not available for stigmergic agents")

        manifest = self._load_manifest_loader()

        # --- Intelligence Layer ---
        intel_aggregator = None
        try:
            from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
            from cyberred.intelligence.stigmergic import (
                StigmergicIntelligencePublisher,
                StigmergicIntelligenceSubscriber,
            )
            from cyberred.intelligence.sources.cisa_kev import CisaKevSource
            from cyberred.intelligence.sources.exploitdb import ExploitDbSource
            from cyberred.intelligence.sources.metasploit import MetasploitSource
            from cyberred.intelligence.sources.nuclei import NucleiSource

            stig_pub = StigmergicIntelligencePublisher(self.bus)
            stig_sub = StigmergicIntelligenceSubscriber(self.bus)
            await stig_sub.subscribe()

            intel_aggregator = CachedIntelligenceAggregator(
                redis_client=self.bus.redis,
                stigmergic_subscriber=stig_sub,
                stigmergic_publisher=stig_pub,
            )
            # Register available sources (NVD excluded — requires nvdlib)
            for src in (CisaKevSource(), ExploitDbSource(), MetasploitSource(), NucleiSource()):
                intel_aggregator.add_source(src)

            self.logger.info(
                f"Intelligence layer initialized: {len(intel_aggregator._sources)} sources"
            )
        except Exception as e:
            self.logger.warning(f"Intelligence layer init failed (non-fatal): {e}")

        # --- RAG Layer ---
        rag_escalator = None
        director_rag_client = None
        self._director_rag_policy = {}
        try:
            from cyberred.rag.store import RAGStore
            from cyberred.rag.embeddings import RAGEmbeddings
            from cyberred.rag.query import RAGQueryInterface
            from cyberred.rag.director_client import DirectorRAGClient
            from cyberred.agents.rag_escalator import AgentRAGEscalator

            rag_store = RAGStore()
            rag_embeddings = RAGEmbeddings()
            rag_interface = RAGQueryInterface(rag_store, rag_embeddings)

            rag_escalator = AgentRAGEscalator(rag_interface)
            rag_policy = self._resolve_director_rag_policy()
            self._director_rag_policy = dict(rag_policy)
            director_rag_client = DirectorRAGClient(
                rag_interface,
                query_timeout_s=float(rag_policy["query_timeout_s"]),
                max_results=int(rag_policy["max_results"]),
                fallback_on_timeout=bool(rag_policy["fallback_on_timeout"]),
                min_score=float(rag_policy["min_score"]),
                deadline_guard_s=float(rag_policy["deadline_guard_s"]),
            )
            self.logger.info(
                "Director RAG policy loaded: timeout=%ss max_results=%s fallback_on_timeout=%s "
                "min_score=%s deadline_guard_s=%s",
                rag_policy["query_timeout_s"],
                rag_policy["max_results"],
                rag_policy["fallback_on_timeout"],
                rag_policy["min_score"],
                rag_policy["deadline_guard_s"],
            )

            self.logger.info("RAG layer initialized (store + embeddings + escalator + director client)")
        except Exception as e:
            self.logger.warning(f"RAG layer init failed (non-fatal): {e}")

        # Wire DirectorRAGClient into WarRoom for strategy enrichment
        if director_rag_client and hasattr(self, 'council'):
            self.council.war_room.set_rag_client(director_rag_client)

        # Store for swarm failure pivot and operator pivot
        if director_rag_client:
            self._director_rag_client = director_rag_client

        # Story 7.13: Create sharded event bus for stigmergic findings
        self._sharded_bus = ShardedEventBus(self.bus)
        self._shard_aggregator = ShardAggregator(
            event_bus=self.bus,
            engagement_id=engagement_id,
        )
        await self._shard_aggregator.start()

        # Story 7.8/7.15: Runtime decision-context tracker + emergent strategy loop
        try:
            from cyberred.orchestration.emergence.strategy import EmergentStrategyAggregator
            from cyberred.orchestration.emergence.tracker import DecisionContextTracker

            # Ensure stale runtime components from previous engagement are not reused.
            if self._emergent_strategy_aggregator:
                try:
                    await self._emergent_strategy_aggregator.stop()
                except Exception:
                    pass
                self._emergent_strategy_aggregator = None

            self._decision_context_tracker = DecisionContextTracker(
                engagement_id=engagement_id,
                event_bus=self.bus,
            )
            self._emergent_strategy_aggregator = EmergentStrategyAggregator(
                event_bus=self.bus,
                engagement_id=engagement_id,
            )
            await self._emergent_strategy_aggregator.start()
            self.logger.info("Emergence runtime initialized (tracker + strategy aggregator)")
        except Exception as e:
            self._decision_context_tracker = None
            self._emergent_strategy_aggregator = None
            self.logger.warning(f"Emergence runtime init failed (non-fatal): {e}")

        # --- Director Layer (Stories 8.1-8.11) ---
        try:
            from cyberred.llm.ensemble import DirectorEnsemble, DirectorContext, SynthesisInput
            from cyberred.orchestration.aggregator import FindingAggregator
            from cyberred.orchestration.strategy_publisher import StrategyPublisher
            from cyberred.orchestration.replan_triggers import (
                ReplanTriggerManager, ReplanTriggerConfig,
            )

            director_ensemble = DirectorEnsemble()
            finding_aggregator = FindingAggregator(event_bus=self.bus)
            strategy_publisher = StrategyPublisher(event_bus=self.bus)

            async def _handle_replan(trigger):
                await self._director_replan_cycle(
                    trigger, director_ensemble, finding_aggregator,
                    strategy_publisher, engagement_id,
                )

            trigger_timeout_s = max(
                director_ensemble.aggregate_timeout + 60.0,
                self._director_trigger_timeout_s,
            )

            replan_manager = ReplanTriggerManager(
                event_bus=self.bus,
                on_trigger=_handle_replan,
                config=ReplanTriggerConfig(
                    timer_interval_s=300.0,
                    trigger_callback_timeout_s=trigger_timeout_s,
                ),
            )
            await finding_aggregator.start(engagement_id)
            await replan_manager.start(engagement_id)

            self._director_ensemble = director_ensemble
            self._finding_aggregator = finding_aggregator
            self._strategy_publisher = strategy_publisher
            self._replan_manager = replan_manager
            self._current_phase = "recon"

            # Subscribe to strategies channel for phase transition detection
            self._bus_subscriptions.append(await self.bus.subscribe(
                f"strategies:{engagement_id}",
                lambda data: asyncio.ensure_future(
                    self._check_phase_transition(data, engagement_id)
                ),
            ))

            self.logger.info("Director layer initialized (ensemble + aggregator + triggers + publisher)")
        except Exception as e:
            self.logger.warning(f"Director layer init failed (non-fatal): {e}")

        # Create spawner for this engagement
        self.spawner = DynamicSpawner(
            router=self.router,
            event_bus=self.bus,
            engagement_id=engagement_id,
            execution_capacity=self._execution_capacity_hint(),
            execution_capacity_provider=self._execution_capacity_hint,
            llm_gateway=llm_gw,
            manifest_loader=manifest,
            intel_aggregator=intel_aggregator,
            rag_escalator=rag_escalator,
            sharded_event_bus=self._sharded_bus,
            context_tracker=self._decision_context_tracker,
        )
        if hasattr(self.spawner, "set_resource_contract"):
            self.spawner.set_resource_contract(self._resource_contract)
        if hasattr(self.spawner, "set_runtime_pressure"):
            self.spawner.set_runtime_pressure(
                state=self._pressure_state,
                reason=self._scale_block_reason,
                resource_contract=self._resource_contract,
            )
        await self.spawner.start()
        try:
            await self._subscribe_dynamic_scale_hints()
        except Exception as e:
            self.logger.warning(f"Dynamic scale subscription init failed (non-fatal): {e}")

        # Spawn initial agent swarm based on scope
        agents = await self.spawner.spawn_initial(scope)
        self._set_desired_agent_count(
            len(agents),
            reason="initial_spawn",
            allow_decrease=True,
        )

        agent_roles = {}
        for agent in agents:
            role_name = agent.role.value if hasattr(agent, 'role') else 'unknown'
            agent_roles[role_name] = agent_roles.get(role_name, 0) + 1
            # Track in orchestrator agents dict
            self.agents[agent.agent_id] = agent

        self.logger.info(
            f"Stigmergic swarm spawned: {len(agents)} agents, "
            f"roles: {agent_roles}"
        )

        await self.bus.publish("swarm:log", {
            "category": "DEPLOY",
            "message": (
                f"Stigmergic swarm deployed: {len(agents)} agents "
                f"({', '.join(f'{r}={c}' for r, c in agent_roles.items())})"
            ),
        })

        # --- Crash Monitor ---
        try:
            from cyberred.storage.checkpoint import CheckpointManager
            checkpoint_mgr = CheckpointManager()
            self._checkpoint_manager = checkpoint_mgr

            self._crash_monitor = AgentCrashMonitor(
                event_bus=self.bus,
                checkpoint_manager=checkpoint_mgr,
                on_crash_callback=self._on_agent_crash,
            )
            await self._crash_monitor.start()
            self.logger.info("Crash monitor started")
        except Exception as e:
            self.logger.warning(f"Crash monitor init failed (non-fatal): {e}")

        # Initialize each agent (subscriptions/heartbeat) and launch execution.
        await self._launch_spawned_agents(agents, target, job_data, engagement_id)
        self._start_spawn_reconcile_loop()

    async def _launch_spawned_agents(
        self,
        agents: list[Any],
        target: str,
        job_data: dict[str, Any],
        engagement_id: str,
        *,
        phase_label: str = "initial_spawn",
        hydrate: bool = False,
    ) -> None:
        """Launch newly spawned agents and register lifecycle tracking."""
        if not agents:
            return

        if hydrate:
            self._hydrate_spawned_agents(agents, source=phase_label)
        self._touch_progress()
        total_agents = len(agents)
        for ordinal, agent in enumerate(agents, start=1):
            queue_snapshot = await self._await_launch_backpressure_relief(
                phase=phase_label,
                ordinal=ordinal,
                total=total_agents,
            )
            self.agents[agent.agent_id] = agent
            self._agents_created_total += 1
            if self.spawner and hasattr(self.spawner, "mark_agent_active"):
                try:
                    self.spawner.mark_agent_active(agent)
                except Exception:
                    pass
            if self._crash_monitor:
                await self._crash_monitor.register_agent(agent.agent_id, engagement_id)
            self._active_jobs += 1
            task = asyncio.create_task(
                self._run_stigmergic_agent(agent, target, job_data)
            )
            self._swarm_tasks.append(task)
            queue_depth = int(queue_snapshot.get("total_queue_depth", 0))
            delay_s = self._agent_launch_base_delay_s
            if queue_depth >= self._llm_queue_elevated_depth:
                delay_s = max(delay_s, self._launch_backpressure_sleep_s)
            if delay_s > 0:
                await asyncio.sleep(delay_s)

    def _resolve_primary_target(self) -> str:
        """Resolve the primary engagement target for dynamic spawns."""
        if not self._engagement_config:
            return ""
        targets = self._engagement_config.get("targets", {})
        for name, info in targets.items():
            if isinstance(info, dict):
                ip = info.get("ip")
                if ip:
                    return ip
                return name
            return name
        return ""

    async def _run_stigmergic_agent(
        self, agent: Any, target: str, job_data: dict
    ) -> None:
        """Initialize and run a single stigmergic agent.

        Calls agent.spawn() for subscriptions/heartbeat, then dispatches
        to the role-specific execute method (execute_recon, etc.).
        """
        replacement_reason: str | None = None
        try:
            # Initialize async components (subscriptions, heartbeat)
            await agent.spawn()

            # Determine the role-specific execute method
            role_value = agent.role.value if hasattr(agent, 'role') else 'recon'
            execute_method_name = _ROLE_EXECUTE_METHODS.get(role_value, "execute")

            execute_fn = getattr(agent, execute_method_name, None)
            if execute_fn is None:
                # Fallback to base execute() if subclass method not found
                execute_fn = agent.execute
                execute_method_name = "execute"

            # Build context data from job_data
            context_data = {
                k: v for k, v in job_data.items()
                if k not in ("target", "full_attack")
            }

            # Call the role-specific method
            self.logger.info(
                f"Agent {agent.agent_id} ({role_value}) executing "
                f"{execute_method_name} against {target}"
            )

            await self.bus.publish("swarm:log", {
                "category": "AGENT",
                "message": f"Agent {agent.agent_id[:8]}.. ({role_value}) engaging {target}",
            })

            # Each role-specific method takes (first_arg, context_dict) as positional args.
            # The first arg is typically 'target' but varies by role:
            #   wireless -> 'interface', ad -> 'domain_controller'
            # All accept the context dict as second positional arg.
            if execute_method_name == "execute":
                execution_coro = execute_fn(f"Attack target {target}")
            else:
                execution_coro = execute_fn(target, context_data)
            await asyncio.wait_for(
                execution_coro,
                timeout=float(self._agent_execution_timeout_s),
            )

            # Agent completed successfully
            await agent.on_complete("success", {"target": target})
            replacement_reason = "completed"

        except asyncio.CancelledError:
            self.logger.info(f"Agent {agent.agent_id} cancelled")
        except asyncio.TimeoutError:
            timeout_message = (
                f"Agent {agent.agent_id} execution timed out "
                f"after {self._agent_execution_timeout_s}s"
            )
            self.logger.error(timeout_message)
            replacement_reason = "failed"
            try:
                await self.bus.publish("swarm:log", {
                    "category": "WATCHDOG",
                    "message": timeout_message,
                })
            except Exception:
                pass
            try:
                if hasattr(agent, "stop") and callable(agent.stop):
                    await agent.stop()
            except Exception:
                pass
            try:
                await agent.on_complete(
                    "failed",
                    {
                        "error": timeout_message,
                        "timeout_s": self._agent_execution_timeout_s,
                    },
                )
            except Exception:
                pass
            role_value = agent.role.value if hasattr(agent, 'role') else 'unknown'
            self._swarm_failure_counts[role_value] = self._swarm_failure_counts.get(role_value, 0) + 1
            try:
                await self._check_swarm_failure_pivot(role_value, timeout_message)
            except Exception:
                pass
        except Exception as e:
            self.logger.error(
                f"Agent {agent.agent_id} failed: {e}", exc_info=True
            )
            replacement_reason = "failed"
            try:
                await agent.on_complete("failed", {"error": str(e)})
            except Exception:
                pass
            # Track swarm-level failures for Director RAG pivot
            role_value = agent.role.value if hasattr(agent, 'role') else 'unknown'
            self._swarm_failure_counts[role_value] = self._swarm_failure_counts.get(role_value, 0) + 1
            try:
                await self._check_swarm_failure_pivot(role_value, str(e))
            except Exception:
                pass  # Never let pivot logic break agent lifecycle
        finally:
            # Save a final checkpoint for checkpoint-based respawn recovery.
            if self._checkpoint_manager:
                try:
                    await agent.save_checkpoint(self._checkpoint_manager)
                except Exception:
                    pass
            # Unregister from crash monitor (prevents double-detection)
            if self._crash_monitor:
                await self._crash_monitor.unregister_agent(agent.agent_id)
            self.agents.pop(agent.agent_id, None)
            if self.spawner and hasattr(self.spawner, "mark_agent_inactive"):
                try:
                    self.spawner.mark_agent_inactive(agent.agent_id)
                except Exception:
                    pass
            role_value = agent.role.value if hasattr(agent, 'role') else 'unknown'
            self._role_completion_counts[role_value] = (
                self._role_completion_counts.get(role_value, 0) + 1
            )
            self._agents_completed_total += 1
            self._active_jobs -= 1
            self._jobs_processed += 1
            self._signal_spawn_reconcile("agent_lifecycle")
            if replacement_reason and not self._stopping and not self._dispatch_paused:
                try:
                    respawned = await self._respawn_agent(
                        agent,
                        target,
                        job_data,
                        reason=replacement_reason,
                    )
                    if not respawned:
                        self._record_respawn_debt(
                            role_value=role_value,
                            reason=replacement_reason,
                            target=target,
                            job_data=job_data,
                        )
                except Exception as e:
                    self.logger.warning(f"Agent respawn failed: {e}")
            elif replacement_reason and self._dispatch_paused:
                self._record_respawn_debt(
                    role_value=role_value,
                    reason=replacement_reason,
                    target=target,
                    job_data=job_data,
                )
                try:
                    await self.bus.publish("swarm:log", {
                        "category": "RESOURCE",
                        "message": (
                            f"Respawn deferred for {agent.agent_id[:8]}.. due to "
                            f"{self._pressure_state} pressure (reason={replacement_reason}); "
                            f"queued debt={len(self._respawn_debt_queue)}"
                        ),
                    })
                except Exception:
                    pass

    def _collect_hydration_findings(self, *, limit: int = 50) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        if not self._finding_aggregator:
            return findings
        try:
            summary = self._finding_aggregator.get_summary()
        except Exception as e:
            self.logger.warning(f"Failed to gather hydration findings: {e}")
            return findings

        prioritized = list(getattr(summary, "findings", []))
        seen_keys: set[tuple[str, str]] = set()
        for finding in prioritized:
            key = (str(getattr(finding, "target", "")), str(getattr(finding, "finding_type", "")))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            metadata = getattr(finding, "metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            findings.append({
                "type": getattr(finding, "finding_type", "unknown"),
                "target": getattr(finding, "target", ""),
                "tool": str(metadata.get("tool", ""))[:120],
                "severity": (
                    finding.severity.name
                    if hasattr(getattr(finding, "severity", None), "name")
                    else str(getattr(finding, "severity", "info"))
                ),
                "evidence": str(metadata.get("evidence", ""))[:240],
            })
            if len(findings) >= limit:
                return findings

        for finding in prioritized:
            if len(findings) >= limit:
                break
            metadata = getattr(finding, "metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            findings.append({
                "type": getattr(finding, "finding_type", "unknown"),
                "target": getattr(finding, "target", ""),
                "tool": str(metadata.get("tool", ""))[:120],
                "severity": (
                    finding.severity.name
                    if hasattr(getattr(finding, "severity", None), "name")
                    else str(getattr(finding, "severity", "info"))
                ),
                "evidence": str(metadata.get("evidence", ""))[:240],
            })
        return findings

    def _collect_runtime_snapshot(self, agent: Any) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        if hasattr(agent, "export_runtime_hydration"):
            try:
                exported = agent.export_runtime_hydration()
                if isinstance(exported, dict):
                    snapshot.update(exported)
            except Exception as e:
                self.logger.warning(f"Failed to export runtime hydration for {agent.agent_id}: {e}")

        if "swarm_findings" not in snapshot:
            try:
                snapshot["swarm_findings"] = list(getattr(agent, "_swarm_findings", []))[-50:]
            except Exception:
                pass
        if "decision_context" not in snapshot:
            try:
                snapshot["decision_context"] = list(getattr(agent, "_decision_context", []))[-200:]
            except Exception:
                pass
        if "previous_results" not in snapshot:
            try:
                snapshot["previous_results"] = list(getattr(agent, "_recent_tool_results", []))[-60:]
            except Exception:
                pass
        if "command_fingerprints" not in snapshot:
            try:
                snapshot["command_fingerprints"] = list(getattr(agent, "_command_fingerprints", []))[-300:]
            except Exception:
                pass
        return snapshot

    async def _respawn_agent(
        self,
        old_agent: Any,
        target: str,
        job_data: dict,
        *,
        reason: str = "failed",
    ) -> bool:
        """Respawn an agent with hydrated context.

        Creates a fresh agent of the same role, hydrates it with accumulated
        findings and active strategy, and launches it.

        Args:
            old_agent: The completed, failed, or crashed agent.
            target: Target string for the engagement.
            job_data: Original job data dict.
            reason: Replacement reason label.

        Returns:
            True when a replacement agent is launched, else False.
        """
        import uuid

        old_role = old_agent.role if hasattr(old_agent, "role") else AgentRole.RECON
        if not isinstance(old_role, AgentRole):
            old_role = AgentRole.RECON
        role_value = old_role.value
        engagement_id = self._engagement_id or "default"

        # Check respawn limit per role (0 means unlimited)
        current_count = self._respawn_counts.get(role_value, 0)
        if self._max_respawns_per_role > 0 and current_count >= self._max_respawns_per_role:
            self.logger.info(
                f"Respawn limit reached for {role_value} "
                f"({current_count}/{self._max_respawns_per_role}), not respawning"
            )
            return False

        hydration_findings = self._collect_hydration_findings(limit=50)
        runtime_snapshot = self._collect_runtime_snapshot(old_agent)

        # Get active strategy from old agent
        active_strategy = None
        if hasattr(old_agent, '_active_strategy') and old_agent._active_strategy:
            active_strategy = old_agent._active_strategy
        if active_strategy is None:
            active_strategy = self._resolve_strategy_for_hydration()

        # Prefer checkpoint-backed restore when available (ERR5 alignment).
        checkpoint_state = None
        if self._checkpoint_manager:
            try:
                checkpoint_state = await self._checkpoint_manager.load_agent_state(
                    engagement_id, old_agent.agent_id
                )
            except Exception as e:
                self.logger.warning(f"Failed loading checkpoint state for {old_agent.agent_id}: {e}")

        selected_role = self._select_respawn_role(
            old_role=old_role,
            reason=reason,
            hydration_findings=hydration_findings,
        )

        # Create replacement agent with fresh UUID
        new_agent_id = str(uuid.uuid4())
        try:
            new_agent = self.router.create_agent(
                role=selected_role,
                agent_id=new_agent_id,
                engagement_id=engagement_id,
                event_bus=self.bus,
                llm_gateway=self.spawner._llm_gateway if self.spawner else None,
                manifest_loader=self.spawner._manifest_loader if self.spawner else None,
                intel_aggregator=self.spawner._intel_aggregator if self.spawner else None,
                rag_escalator=self.spawner._rag_escalator if self.spawner else None,
                sharded_event_bus=self._sharded_bus,
                context_tracker=self._decision_context_tracker,
            )
        except Exception as e:
            self.logger.error(f"Failed to create replacement agent: {e}")
            return False

        # Restore from checkpoint when available, then hydrate with latest swarm data.
        if checkpoint_state:
            try:
                await new_agent.restore_from_checkpoint(checkpoint_state)
            except Exception as e:
                self.logger.warning(f"Failed restoring checkpoint for {new_agent_id}: {e}")

        # Hydrate with accumulated swarm knowledge
        if hydration_findings or active_strategy or runtime_snapshot:
            new_agent.hydrate_context(
                hydration_findings,
                active_strategy,
                runtime_state=runtime_snapshot,
            )

        # Track
        self._respawn_counts[role_value] = current_count + 1
        selected_role_value = selected_role.value
        self._respawn_target_role_counts[selected_role_value] = (
            self._respawn_target_role_counts.get(selected_role_value, 0) + 1
        )
        self.agents[new_agent_id] = new_agent
        self._agents_created_total += 1
        if self.spawner and hasattr(self.spawner, "mark_agent_active"):
            try:
                self.spawner.mark_agent_active(new_agent)
            except Exception:
                pass

        # Register with crash monitor
        if self._crash_monitor:
            await self._crash_monitor.register_agent(new_agent_id, engagement_id)

        # Launch
        await self._await_launch_backpressure_relief(
            phase="respawn",
            ordinal=1,
            total=1,
        )
        self._active_jobs += 1
        task = asyncio.create_task(
            self._run_stigmergic_agent(new_agent, target, job_data)
        )
        self._swarm_tasks.append(task)

        limit_label = (
            str(self._max_respawns_per_role)
            if self._max_respawns_per_role > 0
            else "unlimited"
        )
        self.logger.info(
            f"Respawned {selected_role_value} agent {new_agent_id[:8]}.. "
            f"(reason={reason}, "
            f"gen {current_count + 1}/{limit_label}, "
            f"source_role={role_value}, "
            f"hydrated {len(hydration_findings)} findings, "
            f"runtime_results={len(runtime_snapshot.get('previous_results', []))}, "
            f"runtime_cmd_fps={len(runtime_snapshot.get('command_fingerprints', []))}, "
            f"checkpoint_restored={checkpoint_state is not None})"
        )
        await self.bus.publish("swarm:log", {
            "category": "RESPAWN",
            "message": (
                f"Respawned {selected_role_value} agent {new_agent_id[:8]}.. "
                f"(reason={reason}, gen {current_count + 1}, "
                f"source={role_value}, "
                f"{len(hydration_findings)} findings hydrated, "
                f"checkpoint={checkpoint_state is not None})"
            ),
        })
        return True

    async def _on_agent_crash(self, agent_id: str, engagement_id: str) -> None:
        """Callback invoked by AgentCrashMonitor when an agent is detected as crashed.

        Looks up the crashed agent and triggers respawn.
        """
        old_agent = self.agents.get(agent_id)
        if not old_agent:
            self.logger.warning(f"Crash detected for unknown agent {agent_id}")
            return

        # Need target/job_data — extract from engagement config
        target = ""
        if self._engagement_config:
            targets = self._engagement_config.get("targets", {})
            for name, info in targets.items():
                if isinstance(info, dict) and info.get("ip"):
                    target = info["ip"]
                    break
                else:
                    target = name
                    break

        job_data = {"full_attack": True}
        try:
            role_obj = getattr(old_agent, "role", AgentRole.RECON)
            role_value = getattr(role_obj, "value", None) or str(role_obj or AgentRole.RECON.value)
            self._record_respawn_debt(
                role_value=role_value,
                reason="crashed",
                target=target,
                job_data=job_data,
            )
        except Exception as e:
            self.logger.error(f"Crash respawn failed for {agent_id}: {e}")

    async def _check_swarm_failure_pivot(self, failed_role: str, error_msg: str) -> None:
        """Check if accumulated swarm failures warrant a Director RAG pivot."""
        total_failures = sum(self._swarm_failure_counts.values())
        if total_failures < self._swarm_failure_threshold or not self._director_rag_client:
            return

        failure_signals = [
            f"{role}: {count} failures"
            for role, count in self._swarm_failure_counts.items()
        ]
        failure_signals.append(f"latest: {failed_role} - {error_msg[:200]}")

        # Collect failed technique IDs from agents
        failed_techniques = []
        for agent in self.agents.values():
            if hasattr(agent, '_failure_counts'):
                failed_techniques.extend(
                    t for t, c in agent._failure_counts.items() if c >= 3
                )

        context = DirectorRAGClient.build_swarm_failure_context(
            failure_signals=failure_signals,
            target_service=None,
            failed_techniques=failed_techniques,
            current_phase=self._get_current_phase(),
            environment=self._get_engagement_environment(),
        )

        pivot_result = await self._director_rag_client.query_strategy_pivot(context)
        if pivot_result.methodologies:
            self.logger.info(
                f"Director RAG pivot: {len(pivot_result.methodologies)} methodologies "
                f"({total_failures} swarm failures)"
            )
            await self._publish_rag_pivot(pivot_result)
            self._swarm_failure_counts.clear()

    def _get_current_phase(self) -> str:
        """Get current engagement phase name."""
        if self._engagement_config:
            return self._engagement_config.get("phase", "reconnaissance")
        return "reconnaissance"

    def _get_engagement_environment(self) -> dict:
        """Get engagement environment metadata for RAG context."""
        env: dict[str, Any] = {}
        if self._engagement_config:
            env["target"] = self._engagement_config.get("target", "")
            env["scope"] = str(self._engagement_config.get("scope", {}))[:200]
        env["active_agents"] = len(self.agents)
        env["total_failures"] = sum(self._swarm_failure_counts.values())
        return env

    async def _publish_rag_pivot(self, pivot_result) -> None:
        """Publish RAG pivot guidance to strategies channel."""
        engagement_id = self._engagement_id or "default"
        await self.bus.publish(f"strategies:pivot:{engagement_id}", {
            "type": "rag_pivot",
            "trigger": pivot_result.query_context.trigger,
            "guidance": pivot_result.actionable_guidance[:3000],
            "technique_ids": pivot_result.technique_ids[:20],
            "query_time_ms": pivot_result.query_time_ms,
            "was_timeout": pivot_result.was_timeout,
        })
        await self.bus.publish("swarm:log", {
            "category": "RAG_PIVOT",
            "message": (
                f"Director RAG pivot ({pivot_result.query_context.trigger}): "
                f"{len(pivot_result.methodologies)} methodologies, "
                f"{len(pivot_result.technique_ids)} techniques"
            ),
        })

    async def _director_replan_cycle(
        self, trigger, ensemble, aggregator, publisher, engagement_id: str,
    ) -> None:
        """Run one Director analysis cycle when a replan trigger fires.

        1. Get aggregated findings from FindingAggregator
        2. Build DirectorContext with findings + trigger metadata
        3. Query all 3 models in parallel via query_all()
        4. Synthesize unified strategy
        5. Publish via StrategyPublisher
        6. Reset aggregation window
        """
        from cyberred.llm.ensemble import DirectorContext, SynthesisInput
        trigger_type = trigger.trigger_type.value

        if self._director_cycle_lock.locked():
            self._director_last_failure_type = "cycle_busy"
            await self._publish_director_status(
                engagement_id=engagement_id,
                status="cycle_busy",
                trigger_type=trigger_type,
            )
            return

        async with self._director_cycle_lock:
            cycle_started = time.monotonic()
            if self._dispatch_paused:
                self._director_last_failure_type = "pressure_paused"
                await self._publish_director_status(
                    engagement_id=engagement_id,
                    status="pressure_paused",
                    trigger_type=trigger_type,
                    pressure_state=self._pressure_state,
                    reasons=self._pressure_reasons,
                )
                try:
                    await self.bus.publish("swarm:log", {
                        "category": "DIRECTOR",
                        "message": (
                            f"Director cycle skipped due to {self._pressure_state} pressure"
                        ),
                    })
                except Exception:
                    pass
                return

            queue_snapshot = self._get_llm_queue_snapshot()
            queue_depth = int(queue_snapshot.get("total_queue_depth", 0))
            if queue_depth >= self._llm_queue_critical_depth:
                self._director_last_failure_type = "queue_backpressure_deferred"
                now = time.monotonic()
                should_emit = (
                    now - self._last_director_queue_defer_at
                    >= self._director_queue_defer_cooldown_s
                )
                if should_emit:
                    self._last_director_queue_defer_at = now
                    await self._publish_director_status(
                        engagement_id=engagement_id,
                        status="queue_backpressure_deferred",
                        trigger_type=trigger_type,
                        queue_depth=queue_depth,
                        queue_critical_depth=self._llm_queue_critical_depth,
                        queue_snapshot=queue_snapshot,
                    )
                    try:
                        await self.bus.publish("swarm:log", {
                            "category": "DIRECTOR",
                            "message": (
                                "Director cycle deferred due to LLM queue backpressure "
                                f"(depth={queue_depth}, critical={self._llm_queue_critical_depth})"
                            ),
                        })
                    except Exception:
                        pass
                self._schedule_director_recovery_trigger()
                return

            cycle_timeout_s = max(
                self._director_cycle_timeout_s,
                ensemble.aggregate_timeout + 60.0,
            )
            findings_prompt = aggregator.format_for_director()
            summary = aggregator.get_summary()

            context = DirectorContext(
                engagement_id=engagement_id,
                phase=self._current_phase,
                prompt=(
                    f"Analyze engagement state and recommend next strategy.\n\n"
                    f"{findings_prompt}"
                ),
                findings=[
                    {
                        "target": f.target,
                        "type": f.finding_type,
                        "severity": f.severity.name,
                        "category": f.category.name,
                    }
                    for f in summary.findings[:50]
                ],
                metadata={
                    "trigger_type": trigger_type,
                    "trigger_metadata": trigger.metadata,
                    "total_findings": summary.total_count,
                    "active_agents": len(self.agents),
                    "llm_queue": queue_snapshot,
                },
            )

            try:
                async with asyncio.timeout(cycle_timeout_s):
                    result = await ensemble.query_all(context)
                    if result.successful_count < self._director_min_quorum:
                        self._director_last_failure_type = "no_quorum"
                        error_summary = {
                            role.value: (response.error or "unknown")
                            for role, response in result.responses.items()
                            if not response.success
                        }
                        await self._handle_director_no_quorum(
                            engagement_id=engagement_id,
                            trigger_type=trigger_type,
                            successful=result.successful_count,
                            failed=result.failed_count,
                            model_errors=error_summary,
                        )
                        return

                    if self._director_no_quorum_since is not None:
                        stale_seconds = int(time.time() - self._director_no_quorum_since)
                        self._director_no_quorum_since = None
                        await self._publish_director_status(
                            engagement_id=engagement_id,
                            status="quorum_restored",
                            trigger_type=trigger_type,
                            stale_for_seconds=stale_seconds,
                        )

                    synthesis_input = SynthesisInput(query_result=result)
                    strategy = ensemble.synthesize(synthesis_input)

                    published = await publisher.publish_strategy(strategy, engagement_id)
                    if published:
                        self._director_last_strategy_ts = time.time()
                        self._director_last_failure_type = None
                        self.logger.info(
                            f"Director strategy published: confidence={published.confidence:.2f}, "
                            f"objectives={len(published.objectives)}, "
                            f"trigger={trigger_type}"
                        )
                        await self.bus.publish("swarm:log", {
                            "category": "DIRECTOR",
                            "message": (
                                f"Strategy published (trigger={trigger_type}, "
                                f"confidence={published.confidence:.2f})"
                            ),
                        })
                    else:
                        self._director_last_failure_type = "publish_suppressed"
                        await self._publish_director_status(
                            engagement_id=engagement_id,
                            status="strategy_suppressed",
                            trigger_type=trigger_type,
                        )
                        await self.bus.publish("swarm:log", {
                            "category": "DIRECTOR",
                            "message": (
                                "Director strategy was generated but suppressed by publisher policy"
                            ),
                        })

                    aggregator.reset_window()
            except asyncio.TimeoutError:
                elapsed_s = int(time.monotonic() - cycle_started)
                self._director_last_failure_type = "cycle_timeout"
                self.logger.error(
                    "director_replan_cycle_timeout",
                    trigger_type=trigger_type,
                    timeout_s=cycle_timeout_s,
                    elapsed_s=elapsed_s,
                )
                await self._publish_director_status(
                    engagement_id=engagement_id,
                    status="cycle_timeout",
                    trigger_type=trigger_type,
                    timeout_s=cycle_timeout_s,
                    elapsed_s=elapsed_s,
                )
                await self.bus.publish("swarm:log", {
                    "category": "DIRECTOR",
                    "message": (
                        f"Director cycle timed out after {elapsed_s}s "
                        f"(budget={int(cycle_timeout_s)}s)"
                    ),
                })
            except Exception as e:
                elapsed_s = int(time.monotonic() - cycle_started)
                failure_type = (
                    "cycle_timeout"
                    if "timeout" in str(e).lower()
                    else "cycle_error"
                )
                self._director_last_failure_type = failure_type
                self.logger.error(f"Director replan cycle failed: {e}")
                await self._publish_director_status(
                    engagement_id=engagement_id,
                    status=failure_type,
                    trigger_type=trigger_type,
                    elapsed_s=elapsed_s,
                    error=str(e),
                )
                await self.bus.publish("swarm:log", {
                    "category": "DIRECTOR",
                    "message": f"Strategy cycle failed: {e}",
                })

    async def _handle_director_no_quorum(
        self,
        *,
        engagement_id: str,
        trigger_type: str,
        successful: int,
        failed: int,
        model_errors: dict[str, str] | None = None,
    ) -> None:
        """Handle Director no-quorum state without strategy fallback synthesis."""
        now = time.time()
        if self._director_no_quorum_since is None:
            self._director_no_quorum_since = now
        stale_for_seconds = int(now - self._director_no_quorum_since)
        has_prior_strategy = self._director_last_strategy_ts is not None
        last_strategy_age_s = (
            int(now - self._director_last_strategy_ts)
            if self._director_last_strategy_ts is not None
            else None
        )

        self.logger.warning(
            "director_no_quorum",
            successful=successful,
            failed=failed,
            min_quorum=self._director_min_quorum,
            stale_for_seconds=stale_for_seconds,
            has_prior_strategy=has_prior_strategy,
            last_strategy_age_s=last_strategy_age_s,
        )
        await self._publish_director_status(
            engagement_id=engagement_id,
            status="no_quorum",
            trigger_type=trigger_type,
            successful=successful,
            failed=failed,
            min_quorum=self._director_min_quorum,
            stale_for_seconds=stale_for_seconds,
            has_prior_strategy=has_prior_strategy,
            last_strategy_age_s=last_strategy_age_s,
            model_errors=model_errors or {},
        )
        error_hint = ""
        if model_errors:
            first_error = next(iter(model_errors.items()))
            error_hint = f", sample_error={first_error[0]}:{first_error[1][:120]}"
        await self.bus.publish("swarm:log", {
            "category": "DIRECTOR",
            "message": (
                f"No Director quorum ({successful}/{self._director_min_quorum}); "
                f"holding last strategy, stale_for={stale_for_seconds}s"
                f"{error_hint}"
            ),
        })
        self._schedule_director_recovery_trigger()

    async def _publish_director_status(
        self,
        *,
        engagement_id: str,
        status: str,
        trigger_type: str,
        **extra: Any,
    ) -> None:
        """Publish Director status events for observability and control-plane logic."""
        payload: dict[str, Any] = {
            "engagement_id": engagement_id,
            "status": status,
            "trigger_type": trigger_type,
            "timestamp": time.time(),
        }
        payload.update(extra)
        try:
            await self.bus.publish(f"strategies:status:{engagement_id}", payload)
        except Exception as e:
            self.logger.warning(f"Failed publishing director status: {e}")

    def _schedule_director_recovery_trigger(self) -> None:
        """Schedule a delayed manual replan trigger to recover quorum."""
        if not self._replan_manager:
            return
        now = time.monotonic()
        if (now - self._last_no_quorum_recovery_trigger_at) < self._director_recovery_cooldown_s:
            return
        self._last_no_quorum_recovery_trigger_at = now

        async def _delayed_recovery_trigger() -> None:
            try:
                await asyncio.sleep(self._director_recovery_delay_s)
                if self._stopping or not self._replan_manager:
                    return
                engagement_id = self._engagement_id or "default"
                probe_result = await self._attempt_director_model_probe(
                    engagement_id=engagement_id,
                    trigger_type="director_no_quorum_recovery",
                )
                if probe_result:
                    await self._publish_director_status(
                        engagement_id=engagement_id,
                        status="recovery_probe",
                        trigger_type="director_no_quorum_recovery",
                        **probe_result,
                    )
                await self._replan_manager.trigger_replan(
                    reason="director_no_quorum_recovery",
                    operator_id="system",
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.warning(f"Director recovery trigger failed: {e}")

        task = asyncio.create_task(_delayed_recovery_trigger())
        self._director_recovery_tasks.add(task)
        task.add_done_callback(self._director_recovery_tasks.discard)

    async def _attempt_director_model_probe(
        self,
        *,
        engagement_id: str,
        trigger_type: str,
    ) -> dict[str, Any]:
        """Probe Director models directly and reset circuit-breaker for healthy roles."""
        if self._director_ensemble is None:
            return {}

        try:
            api_key = resolve_llm_api_key()
        except Exception:
            api_key = ""
        if not api_key:
            return {
                "probe_ok": False,
                "probe_error": "missing_api_key",
            }

        recovered_roles: list[str] = []
        failed_roles: dict[str, str] = {}
        try:
            from cyberred.llm.ensemble import DirectorRole
            from cyberred.llm.provider import LLMRequest
        except Exception as e:
            return {
                "probe_ok": False,
                "probe_error": f"probe_import_error:{type(e).__name__}:{e}",
            }

        for role in DirectorRole:
            model_cfg = self._director_ensemble.get_model(role)
            provider = NIMProvider(api_key=api_key, model=model_cfg.model_id)
            request = LLMRequest(
                prompt="Director readiness probe: respond with 'ready'.",
                model=model_cfg.model_id,
                max_tokens=24,
                temperature=0.0,
                timeout_budget_s=25.0,
            )
            try:
                response = await provider.complete_async(request)
                if response.content.strip():
                    self._director_ensemble.reset_role_circuit_breaker(role)
                    recovered_roles.append(role.value)
                else:
                    failed_roles[role.value] = "empty_probe_response"
            except Exception as e:
                failed_roles[role.value] = f"{type(e).__name__}:{str(e)[:200]}"

        if recovered_roles:
            await self.bus.publish("swarm:log", {
                "category": "DIRECTOR",
                "message": (
                    f"Director recovery probe restored {len(recovered_roles)} role(s): "
                    + ", ".join(recovered_roles)
                ),
            })
        elif failed_roles:
            await self.bus.publish("swarm:log", {
                "category": "DIRECTOR",
                "message": (
                    "Director recovery probe failed for all roles: "
                    + ", ".join(
                        f"{role}:{error[:60]}" for role, error in failed_roles.items()
                    )
                ),
            })

        return {
            "probe_ok": bool(recovered_roles),
            "probe_recovered_roles": recovered_roles,
            "probe_failed_roles": failed_roles,
            "trigger_type": trigger_type,
        }

    async def _check_phase_transition(self, data: Any, engagement_id: str) -> None:
        """Check if a published strategy signals a phase transition.

        Supports both legacy pattern-based messages and current published
        strategy payloads.
        """
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return
        if not isinstance(data, dict):
            return

        if any(key in data for key in ("objectives", "recommended_techniques", "priorities", "avoid_targets")):
            self._latest_strategy_payload = dict(data)

        def _extract_techniques(raw: Any) -> set[str]:
            techniques: set[str] = set()
            if not isinstance(raw, list):
                return techniques
            for item in raw:
                if isinstance(item, str):
                    techniques.add(item.split(".")[0].upper())
                elif isinstance(item, dict):
                    technique_id = str(item.get("technique_id", "")).strip()
                    if technique_id:
                        techniques.add(technique_id.split(".")[0].upper())
            return techniques

        pattern = str(data.get("pattern", "")).strip().lower()
        objectives = [str(x).lower() for x in data.get("objectives", []) if isinstance(x, str)]
        priorities = [str(x).lower() for x in data.get("priorities", []) if isinstance(x, str)]
        techniques = _extract_techniques(data.get("recommended_techniques", []))

        to_phase: str | None = None
        reason = ""

        if self._current_phase == "recon":
            if pattern == "enumeration_complete":
                to_phase = "exploit"
                reason = "enumeration_complete"
            else:
                exploit_terms = ("exploit", "vulnerability", "initial access", "weaponize", "attack surface")
                exploit_ttps = {"T1190", "T1133", "T1110", "T1078"}
                has_exploit_intent = any(term in text for text in (*objectives, *priorities) for term in exploit_terms)
                if has_exploit_intent or bool(techniques & exploit_ttps):
                    to_phase = "exploit"
                    reason = "strategy_inferred_exploit_focus"
        elif self._current_phase == "exploit":
            if pattern in ("credential_pivot", "shell_obtained"):
                to_phase = "postex"
                reason = pattern
            else:
                postex_terms = ("lateral movement", "privilege", "post-exploitation", "persistence", "domain admin")
                postex_ttps = {"T1003", "T1021", "T1550", "T1059", "T1068"}
                has_postex_intent = any(term in text for text in (*objectives, *priorities) for term in postex_terms)
                if has_postex_intent or bool(techniques & postex_ttps):
                    to_phase = "postex"
                    reason = "strategy_inferred_postex_focus"

        if not to_phase:
            return

        from_phase = self._current_phase
        if from_phase == to_phase:
            return

        self._current_phase = to_phase
        self._touch_progress()
        await self.bus.publish(
            f"engagement:{engagement_id}:phase",
            {
                "phase": to_phase,
                "from_phase": from_phase,
                "to_phase": to_phase,
                "reason": reason,
            },
        )
        self.logger.info(f"Phase transition: {from_phase} → {to_phase} ({reason})")
        await self.bus.publish(
            "swarm:log",
            {
                "category": "PHASE",
                "message": f"Phase transition: {from_phase} → {to_phase} ({reason})",
            },
        )

        # Trigger phase-driven growth via reconcile queue (slot-driven path).
        if self.spawner:
            try:
                self.spawner._current_phase = to_phase
                primary_target = self._resolve_primary_target() or "127.0.0.1"
                phase_targets = [Target(value=primary_target, type="network")]
                self._increase_desired_agent_count(
                    self._estimate_scale_demand(phase_targets),
                    reason=f"phase_transition:{from_phase}->{to_phase}",
                )
                self._signal_spawn_reconcile("phase_transition")
            except Exception as e:
                self.logger.warning(f"Phase transition scale-up failed: {e}")

    def _build_scope_from_job(self, target: str, job_data: dict) -> Scope:
        """Build a Scope object from job data and engagement config.

        Uses engagement config targets if available, otherwise builds
        a minimal scope from the single target.
        """
        networks: list[str] = []
        webapps: list[str] = []

        # If engagement config has full target list, use it
        if self._engagement_config:
            targets = self._engagement_config.get("targets", {})
            for target_name, target_info in targets.items():
                if isinstance(target_info, dict):
                    ip = target_info.get("ip")
                    services = target_info.get("services", [])
                    if ip:
                        networks.append(ip)
                    if "http" in services or "https" in services:
                        webapps.append(ip or target_name)

        # Ensure the current target is included
        if target not in networks:
            networks.append(target)

        return Scope(
            networks=networks,
            webapps=webapps,
        )

    def get_scope_targets(self) -> list[str]:
        """Return list of in-scope target IPs/hostnames from engagement config."""
        targets: list[str] = []
        if not self._engagement_config:
            return targets
        target_map = self._engagement_config.get("targets", {})
        for name, info in target_map.items():
            if isinstance(info, dict):
                ip = info.get("ip")
                if ip:
                    targets.append(ip)
                else:
                    targets.append(name)
            else:
                targets.append(name)
        return targets

    async def handle_stop_agent(self, data: dict):
        """Handle request to stop an agent."""
        agent_id = data.get("agent_id")

        if agent_id in self.agents:
            agent = self.agents[agent_id]
            # StigmergicAgent uses shutdown(), GhostAgent uses pause()
            if hasattr(agent, 'shutdown'):
                await agent.shutdown()
            elif hasattr(agent, 'pause'):
                agent.pause()
            await self.bus.publish("swarm:log", {
                "category": "SYSTEM",
                "message": f"Agent {agent_id} stopped"
            })

    def _get_next_agent_id(self) -> int:
        """Get next available agent ID (for GhostAgent legacy mode)."""
        agent_id = self.next_agent_id
        self.next_agent_id += 1
        if self.next_agent_id > 100:
            self.next_agent_id = 1  # Cycle IDs
        return agent_id

    async def start_swarm(self, scope: Scope, engagement_id: str | None = None) -> list:
        """Start a stigmergic swarm directly (called by SessionManager).

        This method is the direct entry point for SessionManager to spawn
        a swarm without going through the job:new event bus.

        Args:
            scope: Engagement scope with networks, webapps, etc.
            engagement_id: Optional engagement ID override.

        Returns:
            List of spawned agents.
        """
        eid = engagement_id or self._engagement_id or "default"
        self._stopping = False
        await self._stop_spawn_reconcile_loop()
        self._reset_dynamic_spawn_state()

        llm_gw = None
        manifest = None
        try:
            llm_gw = get_gateway()
        except RuntimeError:
            pass
        manifest = self._load_manifest_loader()

        if (
            self._decision_context_tracker is None
            or getattr(self._decision_context_tracker, "engagement_id", None) != eid
        ):
            try:
                from cyberred.orchestration.emergence.tracker import DecisionContextTracker

                self._decision_context_tracker = DecisionContextTracker(
                    engagement_id=eid,
                    event_bus=self.bus,
                )
            except Exception:
                self._decision_context_tracker = None

        self.spawner = DynamicSpawner(
            router=self.router,
            event_bus=self.bus,
            engagement_id=eid,
            execution_capacity=self._execution_capacity_hint(),
            execution_capacity_provider=self._execution_capacity_hint,
            llm_gateway=llm_gw,
            manifest_loader=manifest,
            context_tracker=self._decision_context_tracker,
        )
        if hasattr(self.spawner, "set_resource_contract"):
            self.spawner.set_resource_contract(self._resource_contract)
        if hasattr(self.spawner, "set_runtime_pressure"):
            self.spawner.set_runtime_pressure(
                state=self._pressure_state,
                reason=self._scale_block_reason,
                resource_contract=self._resource_contract,
            )
        await self.spawner.start()
        try:
            await self._subscribe_dynamic_scale_hints()
        except Exception as e:
            self.logger.warning(f"Dynamic scale subscription init failed (non-fatal): {e}")

        agents = await self.spawner.spawn_initial(scope)
        self._set_desired_agent_count(
            len(agents),
            reason="start_swarm_initial",
            allow_decrease=True,
        )

        for agent in agents:
            self.agents[agent.agent_id] = agent

        self.logger.info(f"Swarm started: {len(agents)} agents for engagement {eid}")
        self._start_spawn_reconcile_loop()
        return agents

    async def stop_all_agents(self):
        """Emergency stop all agents."""
        self._stopping = True
        await self._stop_progress_watchdog()
        await self._stop_resource_monitor()
        await self._stop_spawn_reconcile_loop()
        await self._cancel_director_recovery_tasks()
        self.logger.warning("PANIC: Stopping all agents")

        # Stop crash monitor
        if self._crash_monitor:
            try:
                await self._crash_monitor.stop()
            except Exception:
                pass

        # Stop Director layer if running
        if self._replan_manager:
            try:
                await self._replan_manager.stop()
            except Exception:
                pass
        if self._finding_aggregator:
            try:
                await self._finding_aggregator.stop()
            except Exception:
                pass

        # Stop shard aggregator if running
        if self._shard_aggregator:
            try:
                await self._shard_aggregator.stop()
            except Exception:
                pass
        if self._emergent_strategy_aggregator:
            try:
                await self._emergent_strategy_aggregator.stop()
            except Exception:
                pass
            self._emergent_strategy_aggregator = None
        self._decision_context_tracker = None
        if self.spawner:
            try:
                await self.spawner.stop()
            except Exception:
                pass

        # Cancel swarm tasks
        for task in self._swarm_tasks:
            task.cancel()
        self._swarm_tasks.clear()

        for agent_id, agent in self.agents.items():
            if hasattr(agent, 'shutdown'):
                try:
                    await agent.shutdown()
                except Exception:
                    pass
            elif hasattr(agent, 'pause'):
                agent.pause()

        if self.pool and hasattr(self.pool, "shutdown"):
            try:
                await self.pool.shutdown()
            except Exception:
                pass

        await self.bus.publish("swarm:log", {
            "category": "PANIC",
            "message": "All agents stopped"
        })
        await self._cleanup_bus_subscriptions()

    def get_status(self) -> dict:
        """Get orchestrator status."""
        pool_status = self.pool.get_pool_status()

        # Count active stigmergic agents
        stigmergic_count = sum(
            1 for a in self.agents.values()
            if hasattr(a, 'get_status') and callable(a.get_status)
            and isinstance(a.get_status(), str)  # StigmergicAgent returns str
        )

        status_counts: dict[str, int] = {}
        role_counts: dict[str, int] = {}
        for agent in self.agents.values():
            status = "unknown"
            role_obj = getattr(agent, "role", None)
            role_value = getattr(role_obj, "value", None) or str(role_obj or "unknown")
            role_counts[role_value] = role_counts.get(role_value, 0) + 1
            if hasattr(agent, "get_status") and callable(agent.get_status):
                try:
                    status = str(agent.get_status())
                except Exception:
                    status = "unknown"
            elif hasattr(agent, "is_active") and getattr(agent, "is_active"):
                status = "active"
            status_counts[status] = status_counts.get(status, 0) + 1

        active_working_states = {"active", "thinking", "scanning", "running"}
        waiting_states = {"waiting", "waiting_authorization"}
        active_working = sum(
            count for state, count in status_counts.items() if state in active_working_states
        )
        waiting = sum(
            count for state, count in status_counts.items() if state in waiting_states
        )
        idle = status_counts.get("idle", 0)
        error = status_counts.get("error", 0)
        shutdown = status_counts.get("shutdown", 0)

        findings_total_cumulative, findings_cycle_current = self._get_finding_progress_markers()
        director_availability: dict[str, Any] = {}
        if self._director_ensemble and hasattr(self._director_ensemble, "get_availability_snapshot"):
            try:
                director_availability = self._director_ensemble.get_availability_snapshot()
            except Exception:
                director_availability = {}

        llm_queue: dict[str, Any] = {}
        try:
            gateway = get_gateway()
            llm_queue = {
                "total_queue_depth": gateway.queue_depth,
                "director_queue_depth": getattr(gateway, "director_queue_depth", 0),
                "agent_queue_depth": getattr(gateway, "agent_queue_depth", 0),
                "agent_inflight": getattr(gateway, "agent_inflight", 0),
                "agent_inflight_cap": getattr(gateway, "max_agent_inflight", 0),
                "elevated_depth_threshold": self._llm_queue_elevated_depth,
                "critical_depth_threshold": self._llm_queue_critical_depth,
                "total_requests": gateway.total_requests,
                "total_successes": gateway.total_successes,
                "total_failures": gateway.total_failures,
                "total_retries": gateway.total_retries,
                "avg_latency_ms": gateway.avg_latency_ms,
            }
        except Exception:
            llm_queue = {}

        return {
            "agents": {
                "total": len(self.agents),
                "active": active_working + waiting,
                "active_working": active_working,
                "waiting": waiting,
                "idle": idle,
                "error": error,
                "shutdown": shutdown,
                "status_counts": status_counts,
                "role_counts": role_counts,
                "stigmergic": stigmergic_count,
                "created_total": self._agents_created_total,
                "completed_total": self._agents_completed_total,
                "completed_by_role": dict(self._role_completion_counts),
            },
            "worker_pool": pool_status,
            "tools": self.tool_orchestrator.get_available_tools(),
            "spawner": {
                "active": self.spawner.get_active_count() if self.spawner else 0,
                "effective_cap": (
                    int(self.spawner.effective_spawn_limit())
                    if self.spawner and hasattr(self.spawner, "effective_spawn_limit")
                    else self._effective_agent_cap()
                ),
                "available_slots": self._available_spawn_slots(),
                "desired": self._desired_agent_count,
                "deficit": self._agent_deficit(),
                "pending_scale_hints": len(self._pending_scale_hints),
                "pending_respawn_debt": len(self._respawn_debt_queue),
                "last_reconcile_reason": self._last_spawn_reconcile_reason,
            },
            "resources": {
                "pressure_state": self._pressure_state,
                "pressure_state_since_s": int(time.monotonic() - self._pressure_state_since),
                "pressure_reasons": list(self._pressure_reasons),
                "scale_block_reason": self._scale_block_reason,
                "dispatch_paused": self._dispatch_paused,
                "resource_contract": self._resource_contract,
                "pressure_metrics": self._pressure_metrics,
                "container_quarantine": {
                    "enabled": self._container_quarantine_enabled,
                    "cpu_threshold_pct": self._container_quarantine_cpu_pct,
                    "zombie_threshold": self._container_quarantine_zombie_threshold,
                    "cooldown_s": self._container_quarantine_cooldown_s,
                    "targets": list(self._container_quarantine_targets),
                    "inflight": sorted(self._container_quarantine_inflight),
                    "events_total": self._container_quarantine_events_total,
                    "success_total": self._container_quarantine_success_total,
                    "failure_total": self._container_quarantine_failure_total,
                },
            },
            "director": {
                "last_failure_type": self._director_last_failure_type,
                "min_quorum": self._director_min_quorum,
                "cycle_timeout_s": self._director_cycle_timeout_s,
                "trigger_timeout_s": self._director_trigger_timeout_s,
                "rag_policy": dict(self._director_rag_policy),
                "no_quorum_since": self._director_no_quorum_since,
                "last_strategy_ts": self._director_last_strategy_ts,
                "availability": director_availability,
            },
            "stats": {
                "jobs_processed": self._jobs_processed,
                "jobs_processed_total": self._jobs_processed,
                "active_jobs": self._active_jobs,
                "findings_total_cumulative": findings_total_cumulative,
                "findings_cycle_current": findings_cycle_current,
                "respawn_source_role_counts": dict(self._respawn_counts),
                "respawn_target_role_counts": dict(self._respawn_target_role_counts),
                "scale_triggers_total": self._scale_triggers_total,
                "scale_hints_enqueued_total": self._scale_hints_enqueued_total,
                "scale_hints_processed_total": self._scale_hints_processed_total,
                "scale_hints_deduped_total": self._scale_hints_deduped_total,
                "scale_hints_dropped_total": self._scale_hints_dropped_total,
                "scale_hints_requeued_total": self._scale_hints_requeued_total,
                "respawn_debt_enqueued_total": self._respawn_debt_enqueued_total,
                "respawn_debt_drained_total": self._respawn_debt_drained_total,
                "respawn_debt_dropped_total": self._respawn_debt_dropped_total,
                "reconcile_topups_total": self._reconcile_topups_total,
                "spawn_hydrated_total": self._spawn_hydrated_total,
                "spawn_reconcile_wakeups_total": self._spawn_reconcile_wakeups_total,
                "spawn_blocked_no_slots_total": self._spawn_blocked_no_slots_total,
                "spawn_blocked_llm_total": self._spawn_blocked_llm_total,
                "spawn_blocked_pressure_total": self._spawn_blocked_pressure_total,
                "desired_cap_clamps_total": self._desired_cap_clamps_total,
                "llm_queue": llm_queue,
            }
        }

    async def shutdown(self) -> None:
        """Graceful shutdown - stop all agents and LLM gateway."""
        self._stopping = True
        await self._stop_progress_watchdog()
        await self._stop_resource_monitor()
        await self._stop_spawn_reconcile_loop()
        await self._cancel_director_recovery_tasks()
        self.logger.info("Orchestrator shutting down...")

        # Stop crash monitor
        if self._crash_monitor:
            try:
                await self._crash_monitor.stop()
            except Exception:
                pass
        if self._replan_manager:
            try:
                await self._replan_manager.stop()
            except Exception:
                pass
        if self._finding_aggregator:
            try:
                await self._finding_aggregator.stop()
            except Exception:
                pass
        if self._shard_aggregator:
            try:
                await self._shard_aggregator.stop()
            except Exception:
                pass
        if self._emergent_strategy_aggregator:
            try:
                await self._emergent_strategy_aggregator.stop()
            except Exception:
                pass
            self._emergent_strategy_aggregator = None
        self._decision_context_tracker = None
        if self.spawner:
            try:
                await self.spawner.stop()
            except Exception:
                pass
        await self._cleanup_bus_subscriptions()

        # Cancel swarm tasks
        for task in self._swarm_tasks:
            task.cancel()
        if self._swarm_tasks:
            await asyncio.gather(*self._swarm_tasks, return_exceptions=True)
        self._swarm_tasks.clear()

        # Shutdown all agents
        for agent_id, agent in list(self.agents.items()):
            if hasattr(agent, 'shutdown') and asyncio.iscoroutinefunction(agent.shutdown):
                try:
                    await agent.shutdown()
                except Exception:
                    pass
            elif hasattr(agent, 'is_active'):
                agent.is_active = False
            self.logger.info(f"Stopped agent {agent_id}")

        self.agents.clear()

        if self.pool and hasattr(self.pool, "shutdown"):
            try:
                await self.pool.shutdown()
            except Exception:
                pass

        # Shutdown LLM Gateway
        try:
            gateway = get_gateway()
            await gateway.stop()
            shutdown_gateway()
            self.logger.info("LLM Gateway shutdown complete")
        except RuntimeError:
            pass  # Gateway was never initialized

        self.logger.info("Orchestrator shutdown complete")

    async def _cleanup_bus_subscriptions(self) -> None:
        """Cancel tracked EventBus subscriptions for this orchestrator."""
        for sub in self._bus_subscriptions:
            try:
                cancel_fn = getattr(sub, "cancel", None)
                unsubscribe_fn = getattr(sub, "unsubscribe", None)
                if callable(cancel_fn):
                    await cancel_fn()
                elif callable(unsubscribe_fn):
                    await unsubscribe_fn()
            except Exception:
                pass
        self._bus_subscriptions.clear()
        self._dynamic_scale_subscription_active = False
        self._worker_status_scale_subscription_active = False

    async def _cancel_director_recovery_tasks(self) -> None:
        """Cancel queued director recovery trigger tasks."""
        if not self._director_recovery_tasks:
            return
        for task in list(self._director_recovery_tasks):
            task.cancel()
        await asyncio.gather(*self._director_recovery_tasks, return_exceptions=True)
        self._director_recovery_tasks.clear()

    def _start_resource_monitor(self) -> None:
        """Start runtime pressure monitor."""
        if self._resource_monitor_task and not self._resource_monitor_task.done():
            return
        self._resource_monitor_task = asyncio.create_task(self._resource_monitor_loop())

    async def _stop_resource_monitor(self) -> None:
        """Stop runtime pressure monitor."""
        if self._resource_monitor_task is None:
            return
        self._resource_monitor_task.cancel()
        try:
            await self._resource_monitor_task
        except asyncio.CancelledError:
            pass
        finally:
            self._resource_monitor_task = None

    def _read_arp_table_fulls(self) -> int:
        """Read cumulative ARP table-full events from procfs."""
        path = "/proc/net/stat/arp_cache"
        try:
            with open(path, "r", encoding="utf-8") as handle:
                lines = [line.strip() for line in handle.readlines() if line.strip()]
            if len(lines) < 2:
                return 0
            headers = lines[0].split()
            if "table_fulls" not in headers:
                return 0
            index = headers.index("table_fulls")
            total = 0
            for row in lines[1:]:
                cols = row.split()
                if len(cols) <= index:
                    continue
                total += int(cols[index], 16)
            return total
        except Exception:
            return 0

    def _docker_binary(self) -> str:
        """Return best-effort Docker CLI path."""
        if Path("/usr/bin/docker").exists():
            return "/usr/bin/docker"
        return "docker"

    def _container_quarantine_matches(self, container_name: str) -> bool:
        """Check whether a container should be watched by quarantine policy."""
        name = container_name.strip()
        if not name:
            return False
        for raw_target in self._container_quarantine_targets:
            target = raw_target.strip()
            if not target:
                continue
            if target.endswith("*") and name.startswith(target[:-1]):
                return True
            if target.startswith("*") and name.endswith(target[1:]):
                return True
            if target.endswith("-") and name.startswith(target):
                return True
            if target == name:
                return True
        return False

    @staticmethod
    def _parse_cpu_percent(value: str) -> float:
        """Parse Docker CPU percentage string like '520.23%'."""
        cleaned = value.strip().rstrip("%")
        if not cleaned:
            return 0.0
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    async def _run_command_capture(
        self,
        *args: str,
        timeout: float = 20.0,
    ) -> tuple[int, str, str]:
        """Execute a subprocess command and capture output with timeout."""
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return 124, "", f"timeout>{timeout}s"
        return (
            int(process.returncode),
            stdout.decode("utf-8", errors="ignore"),
            stderr.decode("utf-8", errors="ignore"),
        )

    async def _collect_container_quarantine_snapshot(self) -> dict[str, dict[str, Any]]:
        """Collect per-container CPU and zombie indicators for quarantine policy."""
        docker_bin = self._docker_binary()
        return_code, stdout, stderr = await self._run_command_capture(
            docker_bin,
            "stats",
            "--no-stream",
            "--format",
            "{{.ID}}\t{{.Name}}\t{{.CPUPerc}}\t{{.PIDs}}",
            timeout=20.0,
        )
        if return_code != 0:
            self.logger.warning(
                "container_quarantine_stats_failed",
                code=return_code,
                error=stderr.strip(),
            )
            return {}

        snapshots: dict[str, dict[str, Any]] = {}
        id_lookup: dict[str, dict[str, Any]] = {}
        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            container_id = parts[0].strip().lower()
            container_name = parts[1].strip()
            if not self._container_quarantine_matches(container_name):
                continue
            sample = {
                "container_id": container_id,
                "cpu_percent": self._parse_cpu_percent(parts[2]),
                "pids": int(parts[3]) if parts[3].strip().isdigit() else 0,
                "zombie_count": 0,
            }
            snapshots[container_name] = sample
            id_lookup[container_id] = sample
            id_lookup[container_id[:12]] = sample

        if not snapshots or self._container_quarantine_zombie_threshold <= 0:
            return snapshots

        return_code, stdout, stderr = await self._run_command_capture(
            "ps",
            "-eo",
            "stat,cgroup",
            "--no-headers",
            timeout=15.0,
        )
        if return_code != 0:
            self.logger.warning(
                "container_quarantine_zombie_scan_failed",
                code=return_code,
                error=stderr.strip(),
            )
            return snapshots

        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            stat, _, cgroup = line.partition(" ")
            if not stat.startswith("Z"):
                continue
            match = _DOCKER_SCOPE_PATTERN.search(cgroup)
            if not match:
                continue
            container_id = match.group(1).lower()
            sample = id_lookup.get(container_id) or id_lookup.get(container_id[:12])
            if sample is None:
                continue
            sample["zombie_count"] = int(sample.get("zombie_count", 0)) + 1

        return snapshots

    async def _quarantine_container(
        self,
        container_name: str,
        reasons: list[str],
        sample: dict[str, Any],
    ) -> None:
        """Quarantine a runaway container by restart and publish observability signals."""
        if container_name in self._container_quarantine_inflight:
            return

        self._container_quarantine_inflight.add(container_name)
        self._container_quarantine_last_action[container_name] = time.monotonic()
        self._container_quarantine_events_total += 1
        reason_text = "; ".join(reasons[:3]) if reasons else "threshold_exceeded"

        self.logger.warning(
            "container_quarantine_triggered",
            container=container_name,
            reasons=reasons,
            sample=sample,
        )
        try:
            await self.bus.publish(
                "swarm:log",
                {
                    "category": "RESOURCE",
                    "message": (
                        f"Container quarantine triggered for {container_name}: {reason_text}; "
                        "action=restart"
                    ),
                },
            )
        except Exception:
            pass

        try:
            docker_bin = self._docker_binary()
            return_code, stdout, stderr = await self._run_command_capture(
                docker_bin,
                "restart",
                "--time",
                "2",
                container_name,
                timeout=120.0,
            )
            if return_code == 0:
                self._container_quarantine_success_total += 1
                self.logger.warning(
                    "container_quarantine_restart_ok",
                    container=container_name,
                    output=stdout.strip(),
                )
                try:
                    await self.bus.publish(
                        "swarm:log",
                        {
                            "category": "RESOURCE",
                            "message": f"Container quarantine restart succeeded for {container_name}",
                        },
                    )
                except Exception:
                    pass
            else:
                self._container_quarantine_failure_total += 1
                self.logger.error(
                    "container_quarantine_restart_failed",
                    container=container_name,
                    code=return_code,
                    error=stderr.strip(),
                )
                try:
                    await self.bus.publish(
                        "swarm:log",
                        {
                            "category": "RESOURCE",
                            "message": (
                                f"Container quarantine restart failed for {container_name}: "
                                f"{stderr.strip() or f'code={return_code}'}"
                            ),
                        },
                    )
                except Exception:
                    pass
        finally:
            self._container_quarantine_inflight.discard(container_name)

    async def _run_container_quarantine_hook(self) -> None:
        """Detect runaway containers and quarantine them within configured thresholds."""
        if not self._container_quarantine_enabled:
            return

        snapshots = await self._collect_container_quarantine_snapshot()
        if not snapshots:
            return

        now = time.monotonic()
        actions_taken = 0
        for container_name, sample in snapshots.items():
            reasons: list[str] = []
            cpu_percent = float(sample.get("cpu_percent", 0.0) or 0.0)
            zombie_count = int(sample.get("zombie_count", 0) or 0)
            if (
                self._container_quarantine_cpu_pct > 0
                and cpu_percent >= self._container_quarantine_cpu_pct
            ):
                reasons.append(
                    f"cpu_pct={cpu_percent:.2f}>=threshold={self._container_quarantine_cpu_pct:.2f}"
                )
            if (
                self._container_quarantine_zombie_threshold > 0
                and zombie_count >= self._container_quarantine_zombie_threshold
            ):
                reasons.append(
                    "zombies="
                    f"{zombie_count}>=threshold={self._container_quarantine_zombie_threshold}"
                )
            if not reasons:
                continue

            if container_name in self._container_quarantine_inflight:
                continue
            last_action = float(self._container_quarantine_last_action.get(container_name, 0.0))
            if now - last_action < self._container_quarantine_cooldown_s:
                continue

            await self._quarantine_container(container_name, reasons, sample)
            actions_taken += 1
            if actions_taken >= 2:
                break

    def _collect_resource_metrics(self) -> dict[str, Any]:
        """Collect host and worker-pool pressure metrics."""
        memory = psutil.virtual_memory()
        cpu_count = max(1, int(psutil.cpu_count() or 1))
        cpu_percent = float(psutil.cpu_percent(interval=None))
        cpu_times = psutil.cpu_times_percent(interval=None)
        iowait_percent = float(getattr(cpu_times, "iowait", 0.0))
        try:
            load1, load5, load15 = os.getloadavg()
        except (AttributeError, OSError):
            load1, load5, load15 = (0.0, 0.0, 0.0)
        load_per_cpu = float(load1) / cpu_count

        pool_status = self.pool.get_pool_status()
        try:
            pool_size = int(pool_status.get("pool_size", 0))
        except (TypeError, ValueError):
            pool_size = 0
        if pool_size <= 0:
            workers = pool_status.get("workers", {})
            pool_size = len(workers) if isinstance(workers, dict) else 1
        try:
            available_workers = int(pool_status.get("available", 0))
        except (TypeError, ValueError):
            available_workers = 0
        try:
            busy_workers = int(pool_status.get("busy", 0))
        except (TypeError, ValueError):
            busy_workers = max(0, pool_size - available_workers)

        worker_pressure = busy_workers / max(1, pool_size)
        arp_table_fulls_total = self._read_arp_table_fulls()
        if self._last_arp_table_fulls is None:
            arp_table_fulls_delta = 0
        else:
            arp_table_fulls_delta = max(0, arp_table_fulls_total - self._last_arp_table_fulls)
        self._last_arp_table_fulls = arp_table_fulls_total
        llm_queue_snapshot = self._get_llm_queue_snapshot()

        return {
            "memory_used_pct": float(getattr(memory, "percent", 0.0)),
            "memory_available_mb": memory.available / (1024 * 1024),
            "memory_total_mb": memory.total / (1024 * 1024),
            "cpu_percent": cpu_percent,
            "iowait_percent": iowait_percent,
            "load1": float(load1),
            "load5": float(load5),
            "load15": float(load15),
            "load_per_cpu": load_per_cpu,
            "cpu_count": cpu_count,
            "worker_pool_size": pool_size,
            "worker_available": available_workers,
            "worker_busy": busy_workers,
            "worker_pressure": worker_pressure,
            "arp_table_fulls_total": arp_table_fulls_total,
            "arp_table_fulls_delta": arp_table_fulls_delta,
            "llm_queue_depth": int(llm_queue_snapshot.get("total_queue_depth", 0)),
            "llm_director_queue_depth": int(
                llm_queue_snapshot.get("director_queue_depth", 0)
            ),
            "llm_agent_queue_depth": int(llm_queue_snapshot.get("agent_queue_depth", 0)),
            "llm_agent_inflight": int(llm_queue_snapshot.get("agent_inflight", 0)),
            "llm_agent_inflight_cap": int(llm_queue_snapshot.get("max_agent_inflight", 0)),
        }

    def _policy_float(self, key: str, default: float) -> float:
        """Resolve resource policy float value with fallback."""
        if key in self._resource_policy:
            try:
                return float(self._resource_policy[key])
            except (TypeError, ValueError):
                return default
        if key in self._resource_contract:
            try:
                return float(self._resource_contract[key])
            except (TypeError, ValueError):
                return default
        return default

    def _evaluate_pressure_state(self, metrics: dict[str, Any]) -> tuple[str, list[str]]:
        """Evaluate pressure state from runtime metrics."""
        memory_used_pct = float(metrics.get("memory_used_pct", 0.0))
        cpu_percent = float(metrics.get("cpu_percent", 0.0))
        iowait_percent = float(metrics.get("iowait_percent", 0.0))
        load_per_cpu = float(metrics.get("load_per_cpu", 0.0))
        worker_pressure = float(metrics.get("worker_pressure", 0.0))
        worker_available = int(metrics.get("worker_available", 0))
        arp_table_fulls_delta = int(metrics.get("arp_table_fulls_delta", 0))
        llm_queue_depth = int(metrics.get("llm_queue_depth", 0))
        llm_director_queue_depth = int(metrics.get("llm_director_queue_depth", 0))
        llm_agent_inflight = int(metrics.get("llm_agent_inflight", 0))
        llm_agent_inflight_cap = int(metrics.get("llm_agent_inflight_cap", 0))

        max_mem_pct = self._policy_float("max_mem_utilization_pct", 92.0)
        max_cpu_pct = self._policy_float("max_cpu_utilization_pct", 95.0)
        max_iowait_pct = self._policy_float("max_iowait_pct", 45.0)
        max_load_per_cpu = self._policy_float("max_load_per_cpu", 4.0)
        min_worker_reserve = int(self._resource_contract.get("min_worker_reserve", 1))

        critical_mem_pct = max(max_mem_pct + 3.0, 95.0)
        critical_cpu_pct = max(max_cpu_pct + 2.0, 98.0)
        critical_iowait_pct = max(max_iowait_pct + 20.0, 70.0)
        critical_load_per_cpu = max(max_load_per_cpu * 1.5, 6.0)
        worker_elevated_pressure = self._policy_float("worker_elevated_pressure", 0.85)
        worker_critical_pressure = self._policy_float("worker_critical_pressure", 0.95)
        arp_elevated_delta = int(self._policy_float("arp_table_fulls_elevated_delta", 5.0))
        arp_critical_delta = int(self._policy_float("arp_table_fulls_critical_delta", 25.0))
        llm_queue_elevated_depth = int(
            self._policy_float("llm_queue_elevated_depth", float(self._llm_queue_elevated_depth))
        )
        llm_queue_critical_depth = max(
            llm_queue_elevated_depth + 1,
            int(
                self._policy_float(
                    "llm_queue_critical_depth",
                    float(self._llm_queue_critical_depth),
                )
            ),
        )

        critical_reasons: list[str] = []
        elevated_reasons: list[str] = []

        if memory_used_pct >= critical_mem_pct:
            critical_reasons.append(
                f"memory_used_pct={memory_used_pct:.1f}>=critical_mem_pct={critical_mem_pct:.1f}"
            )
        elif memory_used_pct >= max_mem_pct:
            elevated_reasons.append(
                f"memory_used_pct={memory_used_pct:.1f}>=max_mem_pct={max_mem_pct:.1f}"
            )

        if cpu_percent >= critical_cpu_pct:
            critical_reasons.append(
                f"cpu_pct={cpu_percent:.1f}>=critical_cpu_pct={critical_cpu_pct:.1f}"
            )
        elif cpu_percent >= max_cpu_pct:
            elevated_reasons.append(
                f"cpu_pct={cpu_percent:.1f}>=max_cpu_pct={max_cpu_pct:.1f}"
            )

        if iowait_percent >= critical_iowait_pct:
            critical_reasons.append(
                f"iowait_pct={iowait_percent:.1f}>=critical_iowait_pct={critical_iowait_pct:.1f}"
            )
        elif iowait_percent >= max_iowait_pct:
            elevated_reasons.append(
                f"iowait_pct={iowait_percent:.1f}>=max_iowait_pct={max_iowait_pct:.1f}"
            )

        if load_per_cpu >= critical_load_per_cpu:
            critical_reasons.append(
                f"load_per_cpu={load_per_cpu:.2f}>=critical_load_per_cpu={critical_load_per_cpu:.2f}"
            )
        elif load_per_cpu >= max_load_per_cpu:
            elevated_reasons.append(
                f"load_per_cpu={load_per_cpu:.2f}>=max_load_per_cpu={max_load_per_cpu:.2f}"
            )

        worker_capacity_critical = (
            worker_pressure >= worker_critical_pressure
            or (
                worker_available <= 0
                and worker_pressure >= worker_elevated_pressure
            )
        )
        worker_capacity_elevated = (
            worker_pressure >= worker_elevated_pressure
            or worker_available <= min_worker_reserve
        )

        if worker_capacity_critical:
            critical_reasons.append(
                "worker_capacity_critical"
                f"(pressure={worker_pressure:.2f}, available={worker_available}, "
                f"reserve={min_worker_reserve})"
            )
        elif worker_capacity_elevated:
            elevated_reasons.append(
                "worker_capacity_elevated"
                f"(pressure={worker_pressure:.2f}, available={worker_available})"
            )

        llm_capacity_saturated = (
            llm_agent_inflight_cap > 0 and llm_agent_inflight >= llm_agent_inflight_cap
        )
        if llm_queue_depth >= llm_queue_critical_depth and llm_capacity_saturated:
            critical_reasons.append(
                f"llm_queue_depth={llm_queue_depth}>=critical={llm_queue_critical_depth}"
            )
        elif llm_queue_depth >= llm_queue_elevated_depth:
            elevated_reasons.append(
                f"llm_queue_depth={llm_queue_depth}>=elevated={llm_queue_elevated_depth}"
            )
        elif llm_capacity_saturated:
            elevated_reasons.append(
                f"llm_inflight_saturated={llm_agent_inflight}/{llm_agent_inflight_cap}"
            )

        if (
            llm_director_queue_depth > 0
            and llm_agent_inflight_cap > 0
            and llm_agent_inflight >= llm_agent_inflight_cap
        ):
            elevated_reasons.append(
                "director_queue_waiting_agent_slots"
                f"(director_depth={llm_director_queue_depth}, "
                f"agent_inflight={llm_agent_inflight}/{llm_agent_inflight_cap})"
            )

        arp_is_critical = arp_table_fulls_delta >= arp_critical_delta
        arp_is_elevated = arp_table_fulls_delta >= arp_elevated_delta
        arp_corroborated = (
            worker_pressure >= worker_elevated_pressure
            or worker_available <= min_worker_reserve
            or cpu_percent >= max_cpu_pct
            or memory_used_pct >= max_mem_pct
        )

        advisory_reasons: list[str] = []
        if arp_is_critical and arp_corroborated:
            critical_reasons.append(
                f"arp_table_fulls_delta={arp_table_fulls_delta}>=critical={arp_critical_delta}"
            )
        elif arp_is_critical and not arp_corroborated:
            advisory_reasons.append(
                "arp_table_fulls_delta_high_uncorroborated"
                f"(delta={arp_table_fulls_delta}, critical={arp_critical_delta})"
            )
        elif arp_is_elevated and arp_corroborated:
            elevated_reasons.append(
                f"arp_table_fulls_delta={arp_table_fulls_delta}>=elevated={arp_elevated_delta}"
            )
        elif arp_is_elevated:
            advisory_reasons.append(
                "arp_table_fulls_delta_elevated_uncorroborated"
                f"(delta={arp_table_fulls_delta}, elevated={arp_elevated_delta})"
            )

        if critical_reasons:
            return "CRITICAL", critical_reasons
        if elevated_reasons:
            return "ELEVATED", elevated_reasons
        if advisory_reasons:
            return "NORMAL", advisory_reasons
        return "NORMAL", []

    async def _apply_pressure_state(
        self,
        state: str,
        reasons: list[str],
        metrics: dict[str, Any],
    ) -> None:
        """Apply pressure state side-effects and publish observability events."""
        previous_state = self._pressure_state
        state_changed = state != previous_state

        self._pressure_state = state
        self._pressure_reasons = reasons
        self._pressure_metrics = metrics
        if state_changed:
            self._pressure_state_since = time.monotonic()

        if state == "CRITICAL":
            self._dispatch_paused = True
            self._scale_block_reason = "; ".join(reasons[:3]) if reasons else "critical_pressure"
        elif state == "ELEVATED":
            self._dispatch_paused = False
            self._scale_block_reason = "; ".join(reasons[:3]) if reasons else "elevated_pressure"
        else:
            self._dispatch_paused = False
            self._scale_block_reason = None
        if not self._dispatch_paused:
            self._signal_spawn_reconcile("pressure_relief")

        if self.spawner and hasattr(self.spawner, "set_runtime_pressure"):
            try:
                self.spawner.set_runtime_pressure(
                    state=state,
                    reason=self._scale_block_reason,
                    resource_contract=self._resource_contract,
                )
            except Exception as e:
                self.logger.warning(f"Failed applying spawner pressure state: {e}")

        if state_changed:
            self.logger.warning(
                "resource_pressure_state_changed",
                previous_state=previous_state,
                state=state,
                reasons=reasons,
                metrics=metrics,
            )
            try:
                await self.bus.publish(
                    "swarm:log",
                    {
                        "category": "RESOURCE",
                        "message": (
                            f"Pressure state {previous_state} -> {state}"
                            + (f" ({'; '.join(reasons[:2])})" if reasons else "")
                        ),
                    },
                )
                engagement_id = self._engagement_id or "default"
                await self.bus.publish(
                    f"strategies:status:{engagement_id}",
                    {
                        "engagement_id": engagement_id,
                        "status": f"pressure_{state.lower()}",
                        "trigger_type": "resource_governor",
                        "reasons": reasons,
                        "metrics": metrics,
                        "timestamp": time.time(),
                    },
                )
            except Exception:
                pass

    async def _resource_monitor_loop(self) -> None:
        """Monitor host pressure and gate scale-up/dispatch accordingly."""
        try:
            while not self._stopping:
                await asyncio.sleep(self._resource_monitor_interval_s)
                if self._stopping:
                    break

                try:
                    metrics = self._collect_resource_metrics()
                    try:
                        await self._run_container_quarantine_hook()
                    except Exception as e:
                        self.logger.warning("container_quarantine_hook_failed", error=str(e))
                    proposed_state, reasons = self._evaluate_pressure_state(metrics)
                except Exception as e:
                    self.logger.warning(f"Resource monitor sample failed: {e}")
                    continue

                if proposed_state == "CRITICAL":
                    self._pressure_critical_strikes += 1
                    self._pressure_elevated_strikes = 0
                    self._pressure_clear_strikes = 0
                elif proposed_state == "ELEVATED":
                    self._pressure_elevated_strikes += 1
                    self._pressure_critical_strikes = 0
                    self._pressure_clear_strikes = 0
                else:
                    self._pressure_clear_strikes += 1
                    self._pressure_critical_strikes = 0
                    self._pressure_elevated_strikes = 0

                if proposed_state == "CRITICAL" and self._pressure_critical_strikes < 2:
                    continue
                if (
                    proposed_state == "ELEVATED"
                    and self._pressure_state == "NORMAL"
                    and self._pressure_elevated_strikes < 2
                ):
                    continue
                if (
                    proposed_state == "NORMAL"
                    and self._pressure_state != "NORMAL"
                    and self._pressure_clear_strikes < 2
                ):
                    continue

                await self._apply_pressure_state(proposed_state, reasons, metrics)
        except asyncio.CancelledError:
            pass

    def _touch_progress(self) -> None:
        """Mark that the engagement made forward progress."""
        findings_total, findings_cycle = self._get_finding_progress_markers()
        self._last_progress_at = time.monotonic()
        self._last_progress_findings_total = findings_total
        self._last_progress_findings_cycle = findings_cycle
        self._last_progress_strategy_ts = float(self._director_last_strategy_ts or 0.0)
        self._last_progress_role_completion_total = sum(self._role_completion_counts.values())
        self._last_progress_jobs_processed = self._jobs_processed
        self._last_stall_replan_at = 0.0

    def _get_finding_progress_markers(self) -> tuple[int, int]:
        """Return (validated_cumulative, validated_cycle) progress markers."""
        findings_total = 0
        findings_cycle = 0
        if self._finding_aggregator:
            try:
                summary = self._finding_aggregator.get_summary()
                findings_cycle = int(summary.by_outcome.get("validated", 0))
                totals = self._finding_aggregator.get_outcome_totals()
                findings_total = int(totals.get("validated", 0))
            except Exception:
                findings_cycle = 0
                findings_total = 0
        return findings_total, findings_cycle

    def _get_live_role_counts(self) -> dict[str, int]:
        """Return active role distribution for currently running agents."""
        role_counts: dict[str, int] = {}
        for agent in self.agents.values():
            role_obj = getattr(agent, "role", None)
            role_value = getattr(role_obj, "value", None) or str(role_obj or "unknown")
            role_counts[role_value] = role_counts.get(role_value, 0) + 1
        return role_counts

    def _has_meaningful_progress(self) -> bool:
        """Check whether the engagement made meaningful progress recently."""
        findings_total, findings_cycle = self._get_finding_progress_markers()
        strategy_ts = float(self._director_last_strategy_ts or 0.0)
        role_completion_total = sum(self._role_completion_counts.values())
        active_role_count = sum(
            1 for _, count in self._get_live_role_counts().items() if count > 0
        )

        if findings_total > self._last_progress_findings_total:
            return True
        if findings_cycle > self._last_progress_findings_cycle:
            return True
        if strategy_ts > self._last_progress_strategy_ts:
            return True

        # Fallback: job completions count as progress only when multiple roles
        # are actively contributing.
        if (
            role_completion_total > self._last_progress_role_completion_total
            and active_role_count > 1
        ):
            return True
        return False

    def _select_respawn_role(
        self,
        *,
        old_role: AgentRole,
        reason: str,
        hydration_findings: list[dict[str, Any]],
    ) -> AgentRole:
        """Select target role for respawn with diversity protection."""
        if reason != "completed":
            return old_role
        if self.spawner is None:
            return old_role

        try:
            distribution = self.spawner.adjust_distribution_for_phase(self._current_phase)
        except Exception:
            distribution = {}
        if not distribution:
            return old_role

        role_counts = self._get_live_role_counts()
        total_active = max(1, sum(role_counts.values()))
        old_role_count = role_counts.get(old_role.value, 0)
        old_role_target = max(
            1,
            int(round(float(distribution.get(old_role, 0.0)) * total_active)),
        )

        # Only rebalance when role is clearly overrepresented.
        saturation_buffer = 2 if hydration_findings else 1
        if old_role_count <= (old_role_target + saturation_buffer):
            return old_role

        candidate = old_role
        best_deficit = 0
        for role, weight in distribution.items():
            desired = max(1, int(round(float(weight) * total_active)))
            current = role_counts.get(role.value, 0)
            deficit = desired - current
            if deficit > best_deficit:
                best_deficit = deficit
                candidate = role

        if best_deficit <= 0:
            return old_role
        return candidate

    def _live_swarm_task_count(self) -> int:
        """Return number of active swarm tasks and prune completed entries."""
        alive_tasks = [task for task in self._swarm_tasks if not task.done()]
        if len(alive_tasks) != len(self._swarm_tasks):
            self._swarm_tasks = alive_tasks
        return len(alive_tasks)

    def _start_progress_watchdog(self) -> None:
        """Start background stall watchdog if not already running."""
        if self._stall_watchdog_task and not self._stall_watchdog_task.done():
            return
        self._stall_watchdog_task = asyncio.create_task(self._progress_watchdog_loop())

    async def _stop_progress_watchdog(self) -> None:
        """Stop background stall watchdog."""
        if self._stall_watchdog_task is None:
            return
        self._stall_watchdog_task.cancel()
        try:
            await self._stall_watchdog_task
        except asyncio.CancelledError:
            pass
        finally:
            self._stall_watchdog_task = None

    async def _progress_watchdog_loop(self) -> None:
        """Detect long stalls and trigger recovery re-plan attempts."""
        try:
            while not self._stopping:
                await asyncio.sleep(30)
                if self._stopping:
                    break

                if self._has_meaningful_progress():
                    self._touch_progress()
                    continue

                live_tasks = self._live_swarm_task_count()
                if self._active_jobs > 0 and live_tasks == 0:
                    self.logger.error(
                        "engagement_invariant_active_jobs_without_tasks",
                        active_jobs=self._active_jobs,
                        jobs_processed=self._jobs_processed,
                    )
                    self._active_jobs = 0
                    try:
                        await self.bus.publish("swarm:log", {
                            "category": "WATCHDOG",
                            "message": (
                                "Detected stale active-job accounting with no live swarm tasks; "
                                "resetting active job count."
                            ),
                        })
                    except Exception:
                        pass
                    self._touch_progress()
                    continue

                # No active jobs means idle, not stalled.
                if self._active_jobs <= 0:
                    self._touch_progress()
                    continue

                elapsed = time.monotonic() - self._last_progress_at
                if elapsed < self._stall_timeout_s:
                    continue

                now = time.monotonic()
                if now - self._last_stall_replan_at < self._stall_cooldown_s:
                    continue
                self._last_stall_replan_at = now

                self.logger.warning(
                    "engagement_stalled",
                    active_jobs=self._active_jobs,
                    live_tasks=live_tasks,
                    jobs_processed=self._jobs_processed,
                    stalled_for_seconds=int(elapsed),
                )
                try:
                    await self.bus.publish("swarm:log", {
                        "category": "WATCHDOG",
                        "message": (
                            f"Engagement appears stalled ({int(elapsed)}s without job completion, "
                            f"active_jobs={self._active_jobs}); triggering re-plan."
                        ),
                    })
                except Exception:
                    pass

                hard_stall = elapsed >= self._stall_hard_timeout_s
                if hard_stall:
                    self.logger.error(
                        "engagement_hard_stalled",
                        active_jobs=self._active_jobs,
                        live_tasks=live_tasks,
                        jobs_processed=self._jobs_processed,
                        stalled_for_seconds=int(elapsed),
                        hard_timeout_s=self._stall_hard_timeout_s,
                    )
                    try:
                        engagement_id = self._engagement_id or "default"
                        await self.bus.publish(f"strategies:status:{engagement_id}", {
                            "engagement_id": engagement_id,
                            "status": "hard_stall",
                            "trigger_type": "stall_watchdog",
                            "stalled_for_seconds": int(elapsed),
                            "active_jobs": self._active_jobs,
                            "live_tasks": live_tasks,
                            "timestamp": time.time(),
                        })
                        await self.bus.publish("swarm:log", {
                            "category": "WATCHDOG",
                            "message": (
                                f"HARD stall detected ({int(elapsed)}s >= {self._stall_hard_timeout_s}s); "
                                "forcing immediate Director re-plan."
                            ),
                        })
                    except Exception:
                        pass

                if self._replan_manager and hasattr(self._replan_manager, "trigger_replan"):
                    try:
                        await self._replan_manager.trigger_replan(
                            reason=(
                                f"hard_stall_watchdog_{int(elapsed)}s"
                                if hard_stall
                                else f"stall_watchdog_{int(elapsed)}s"
                            )
                        )
                    except Exception as e:
                        self.logger.warning(f"Stall watchdog re-plan trigger failed: {e}")
        except asyncio.CancelledError:
            pass
