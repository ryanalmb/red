import asyncio
from collections import deque
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from cyberred.agents.roles import AgentRole
from cyberred.core.orchestrator import Orchestrator


def _orchestrator_stub() -> Orchestrator:
    orchestrator = object.__new__(Orchestrator)
    orchestrator.logger = logging.getLogger("test_orchestrator_runtime")
    orchestrator.spawner = None
    orchestrator._current_phase = "recon"
    orchestrator.agents = {}
    orchestrator._director_last_strategy_ts = None
    orchestrator._latest_strategy_payload = None
    orchestrator._desired_agent_count = 0
    orchestrator._respawn_debt_queue = deque()
    orchestrator._pending_scale_hints = deque()
    orchestrator._scale_hint_seen = {}
    orchestrator._scale_hint_last_prune_at = 0.0
    orchestrator._scale_hint_ttl_s = 600.0
    orchestrator._scale_hint_max_backlog = 256
    orchestrator._respawn_debt_max_backlog = 512
    orchestrator._respawn_debt_dropped_total = 0
    orchestrator._last_progress_findings_total = 0
    orchestrator._last_progress_findings_cycle = 0
    orchestrator._last_progress_strategy_ts = 0.0
    orchestrator._last_progress_role_completion_total = 0
    orchestrator._role_completion_counts = {}
    orchestrator._get_finding_progress_markers = lambda: (0, 0)
    orchestrator._get_live_role_counts = lambda: {}
    orchestrator._llm_queue_elevated_depth = 24
    orchestrator._llm_queue_critical_depth = 48
    orchestrator._launch_backpressure_sleep_s = 0.01
    orchestrator._launch_backpressure_max_wait_s = 0.01
    orchestrator._agent_launch_base_delay_s = 0.0
    orchestrator._pressure_state = "NORMAL"
    orchestrator._stopping = False
    orchestrator._get_llm_queue_snapshot = lambda: {
        "total_queue_depth": 0,
        "director_queue_depth": 0,
        "agent_queue_depth": 0,
        "agent_inflight": 0,
        "max_agent_inflight": 0,
    }
    return orchestrator


def test_select_respawn_role_keeps_old_role_when_not_completed() -> None:
    orchestrator = _orchestrator_stub()
    orchestrator.spawner = SimpleNamespace(
        adjust_distribution_for_phase=lambda phase: {
            AgentRole.AD: 0.1,
            AgentRole.RECON: 0.9,
        }
    )
    orchestrator._get_live_role_counts = lambda: {"ad": 9, "recon": 1}

    selected = orchestrator._select_respawn_role(
        old_role=AgentRole.AD,
        reason="failed",
        hydration_findings=[{"target": "10.0.0.10", "type": "service"}],
    )
    assert selected == AgentRole.AD


def test_select_respawn_role_rebalances_when_old_role_saturated() -> None:
    orchestrator = _orchestrator_stub()
    orchestrator.spawner = SimpleNamespace(
        adjust_distribution_for_phase=lambda phase: {
            AgentRole.AD: 0.2,
            AgentRole.RECON: 0.8,
        }
    )
    orchestrator._get_live_role_counts = lambda: {"ad": 6, "recon": 1}

    selected = orchestrator._select_respawn_role(
        old_role=AgentRole.AD,
        reason="completed",
        hydration_findings=[{"target": "dc01.corp.local", "type": "ad_hint"}],
    )
    assert selected == AgentRole.RECON


def test_meaningful_progress_ignores_single_role_completion_churn() -> None:
    orchestrator = _orchestrator_stub()
    orchestrator._role_completion_counts = {"ad": 14}
    orchestrator._last_progress_role_completion_total = 0
    orchestrator._get_live_role_counts = lambda: {"ad": 11}

    assert orchestrator._has_meaningful_progress() is False


def test_meaningful_progress_accepts_multi_role_completions() -> None:
    orchestrator = _orchestrator_stub()
    orchestrator._role_completion_counts = {"ad": 14}
    orchestrator._last_progress_role_completion_total = 0
    orchestrator._get_live_role_counts = lambda: {"ad": 10, "recon": 2}

    assert orchestrator._has_meaningful_progress() is True


def test_meaningful_progress_accepts_findings_deltas() -> None:
    orchestrator = _orchestrator_stub()
    orchestrator._get_finding_progress_markers = lambda: (5, 0)

    assert orchestrator._has_meaningful_progress() is True


@pytest.mark.asyncio
async def test_respawn_agent_marks_spawner_active() -> None:
    orchestrator = _orchestrator_stub()
    orchestrator._engagement_id = "eng-1"
    orchestrator._max_respawns_per_role = 0
    orchestrator._respawn_counts = {}
    orchestrator._respawn_target_role_counts = {}
    orchestrator._checkpoint_manager = None
    orchestrator._sharded_bus = None
    orchestrator._decision_context_tracker = None
    orchestrator._crash_monitor = None
    orchestrator._agents_created_total = 0
    orchestrator._active_jobs = 0
    orchestrator._swarm_tasks = []
    orchestrator._stopping = False
    orchestrator._dispatch_paused = False
    orchestrator._collect_hydration_findings = lambda limit=50: []
    orchestrator._collect_runtime_snapshot = lambda old_agent: {}
    orchestrator._select_respawn_role = Mock(return_value=AgentRole.AD)
    orchestrator._resolve_strategy_for_hydration = Mock(return_value=None)
    orchestrator._run_stigmergic_agent = AsyncMock(return_value=None)
    orchestrator._await_launch_backpressure_relief = AsyncMock(return_value={})

    new_agent = SimpleNamespace(
        agent_id="new-agent-id",
        role=AgentRole.AD,
        hydrate_context=Mock(),
    )
    orchestrator.router = SimpleNamespace(create_agent=Mock(return_value=new_agent))
    orchestrator.spawner = SimpleNamespace(
        _llm_gateway=None,
        _manifest_loader=None,
        _intel_aggregator=None,
        _rag_escalator=None,
        mark_agent_active=Mock(),
    )
    orchestrator.bus = SimpleNamespace(publish=AsyncMock())

    old_agent = SimpleNamespace(
        agent_id="old-agent-id",
        role=AgentRole.AD,
        _active_strategy=None,
    )

    result = await orchestrator._respawn_agent(
        old_agent=old_agent,
        target="10.10.10.10",
        job_data={"phase": "recon"},
        reason="failed",
    )

    assert result is True
    orchestrator.spawner.mark_agent_active.assert_called_once_with(new_agent)
    assert orchestrator._active_jobs == 1
    assert orchestrator._respawn_counts["ad"] == 1
    assert orchestrator._respawn_target_role_counts["ad"] == 1
    assert any(getattr(agent, "agent_id", "") == "new-agent-id" for agent in orchestrator.agents.values())

    await asyncio.gather(*orchestrator._swarm_tasks)
