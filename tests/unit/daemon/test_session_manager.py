"""Unit tests for SessionManager.

Tests for multi-engagement orchestration, lifecycle operations,
isolation guarantees, and resource limits.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import time

import pytest

from cyberred.daemon.session_manager import (
    SessionManager,
    EngagementContext,
    EngagementSummary,
    validate_engagement_name,
)
from cyberred.daemon.state_machine import EngagementState, EngagementStateMachine
from cyberred.core.exceptions import (
    ConfigurationError,
    EngagementNotFoundError,
    InvalidStateTransition,
    ResourceLimitError,
)


@pytest.fixture(autouse=True)
def mock_preflight():
    """Mock pre-flight checks globally for all tests."""
    with patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
        runner = MagicMock()
        runner.run_all = AsyncMock(return_value=[])
        runner.validate_results = MagicMock()
        MockRunner.return_value = runner
        yield runner


class TestValidateEngagementName:
    """Tests for engagement name validation."""

    def test_valid_simple_names(self) -> None:
        """Valid simple names should pass validation."""
        assert validate_engagement_name("a") is True
        assert validate_engagement_name("test") is True
        assert validate_engagement_name("ministry") is True
        assert validate_engagement_name("x") is True

    def test_valid_names_with_numbers(self) -> None:
        """Valid names with numbers should pass validation."""
        assert validate_engagement_name("test1") is True
        assert validate_engagement_name("1test") is True
        assert validate_engagement_name("pentest2026") is True
        assert validate_engagement_name("123") is True

    def test_valid_names_with_hyphens(self) -> None:
        """Valid names with hyphens should pass validation."""
        assert validate_engagement_name("acme-corp") is True
        assert validate_engagement_name("test-123-abc") is True
        assert validate_engagement_name("pentest-q1-2026") is True

    def test_invalid_uppercase_names(self) -> None:
        """Names with uppercase letters should fail validation."""
        assert validate_engagement_name("Ministry") is False
        assert validate_engagement_name("ACME") is False
        assert validate_engagement_name("TestName") is False

    def test_invalid_special_characters(self) -> None:
        """Names with special characters should fail validation."""
        assert validate_engagement_name("test_name") is False
        assert validate_engagement_name("test name") is False
        assert validate_engagement_name("test.name") is False
        assert validate_engagement_name("test@name") is False

    def test_invalid_hyphen_positions(self) -> None:
        """Names starting or ending with hyphen should fail validation."""
        assert validate_engagement_name("-test") is False
        assert validate_engagement_name("test-") is False
        assert validate_engagement_name("-") is False

    def test_empty_name_is_invalid(self) -> None:
        """Empty name should fail validation."""
        assert validate_engagement_name("") is False


class TestEngagementContext:
    """Tests for EngagementContext dataclass."""

    def test_state_property_returns_current_state(self) -> None:
        """State property should return state machine's current state."""
        sm = EngagementStateMachine("test-123")
        ctx = EngagementContext(
            id="test-123",
            state_machine=sm,
            config_path=Path("/tmp/config.yaml"),
        )
        assert ctx.state == EngagementState.INITIALIZING

    def test_is_active_true_for_initializing(self) -> None:
        """INITIALIZING state should be considered active."""
        sm = EngagementStateMachine("test-123")
        ctx = EngagementContext(
            id="test-123",
            state_machine=sm,
            config_path=Path("/tmp/config.yaml"),
        )
        assert ctx.is_active is True

    @pytest.mark.asyncio
    async def test_is_active_true_for_running(self) -> None:
        """RUNNING state should be considered active."""
        sm = EngagementStateMachine("test-123")
        sm.start()  # INITIALIZING -> RUNNING
        ctx = EngagementContext(
            id="test-123",
            state_machine=sm,
            config_path=Path("/tmp/config.yaml"),
        )
        assert ctx.is_active is True

    @pytest.mark.asyncio
    async def test_is_active_true_for_paused(self) -> None:
        """PAUSED state should be considered active."""
        sm = EngagementStateMachine("test-123")
        sm.start()
        sm.pause()  # RUNNING -> PAUSED
        ctx = EngagementContext(
            id="test-123",
            state_machine=sm,
            config_path=Path("/tmp/config.yaml"),
        )
        assert ctx.is_active is True

    @pytest.mark.asyncio
    async def test_is_active_false_for_stopped(self) -> None:
        """STOPPED state should NOT be considered active."""
        sm = EngagementStateMachine("test-123")
        sm.start()
        sm.stop()  # RUNNING -> STOPPED
        ctx = EngagementContext(
            id="test-123",
            state_machine=sm,
            config_path=Path("/tmp/config.yaml"),
        )
        assert ctx.is_active is False

    @pytest.mark.asyncio
    async def test_is_active_false_for_completed(self) -> None:
        """COMPLETED state should NOT be considered active."""
        sm = EngagementStateMachine("test-123")
        sm.start()
        sm.stop()
        sm.complete()  # STOPPED -> COMPLETED
        ctx = EngagementContext(
            id="test-123",
            state_machine=sm,
            config_path=Path("/tmp/config.yaml"),
        )
        assert ctx.is_active is False


class TestEngagementSummary:
    """Tests for EngagementSummary dataclass."""

    def test_summary_is_frozen(self) -> None:
        """EngagementSummary should be immutable."""
        summary = EngagementSummary(
            id="test-123",
            state="RUNNING",
            agent_count=5,
            finding_count=10,
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            summary.id = "new-id"  # type: ignore


class TestSessionManagerInit:
    """Tests for SessionManager initialization."""

    def test_default_max_engagements(self) -> None:
        """Default max_engagements should be 10."""
        manager = SessionManager()
        assert manager.max_engagements == 10

    def test_custom_max_engagements(self) -> None:
        """Custom max_engagements should be respected."""
        manager = SessionManager(max_engagements=5)
        assert manager.max_engagements == 5

    def test_initial_active_count_zero(self) -> None:
        """Initial active count should be 0."""
        manager = SessionManager()
        assert manager.active_count == 0

    def test_initial_remaining_capacity(self) -> None:
        """Initial remaining capacity should equal max_engagements."""
        manager = SessionManager(max_engagements=5)
        assert manager.remaining_capacity == 5

    def test_max_history_property(self) -> None:
        """Should return configured max_history."""
        manager = SessionManager(max_history=99)
        assert manager.max_history == 99


class TestSessionManagerCreateEngagement:
    """Tests for SessionManager.create_engagement()."""

    def test_create_engagement_returns_id(self, tmp_path: Path) -> None:
        """create_engagement should return engagement ID."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)

        assert engagement_id.startswith("test-")
        assert len(engagement_id) > 5

    def test_create_engagement_starts_in_initializing(self, tmp_path: Path) -> None:
        """New engagement should start in INITIALIZING state."""
        config = tmp_path / "test.yaml"
        config.write_text("name: mytest\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        context = manager.get_engagement(engagement_id)

        assert context is not None
        assert context.state == EngagementState.INITIALIZING

    def test_create_engagement_id_format(self, tmp_path: Path) -> None:
        """Engagement ID should follow {name}-{YYYYMMDD-HHMMSS}-{suffix} format."""
        config = tmp_path / "ministry.yaml"
        config.write_text("name: ministry\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)

        # Should match pattern: ministry-YYYYMMDD-HHMMSS-suffix
        assert engagement_id.startswith("ministry-")
        parts = engagement_id.split("-")
        assert len(parts) == 4
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert len(parts[3]) == 6  # suffix (3 bytes hex)

    def test_create_engagement_uses_filename_if_no_name_in_config(
        self, tmp_path: Path
    ) -> None:
        """Should use filename stem if no name in config."""
        config = tmp_path / "acmecorp.yaml"
        config.write_text("scope: [10.0.0.0/8]\n")  # No 'name' key

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)

        assert engagement_id.startswith("acmecorp-")

    def test_create_engagement_file_not_found(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError if config file missing."""
        config = tmp_path / "nonexistent.yaml"

        manager = SessionManager()
        with pytest.raises(FileNotFoundError) as exc_info:
            manager.create_engagement(config)

        assert "nonexistent.yaml" in str(exc_info.value)

    def test_create_engagement_invalid_yaml(self, tmp_path: Path) -> None:
        """Should raise ConfigurationError for invalid YAML."""
        config = tmp_path / "invalid.yaml"
        config.write_text("{ invalid yaml without closing brace")

        manager = SessionManager()
        with pytest.raises(ConfigurationError) as exc_info:
            manager.create_engagement(config)

        assert "Invalid YAML" in str(exc_info.value)

    def test_create_engagement_invalid_name_raises_error(self, tmp_path: Path) -> None:
        """Should raise ConfigurationError for invalid engagement name."""
        config = tmp_path / "test.yaml"
        config.write_text("name: Invalid_Name\n")

        manager = SessionManager()
        with pytest.raises(ConfigurationError) as exc_info:
            manager.create_engagement(config)

        assert "Invalid engagement name" in str(exc_info.value)

    def test_create_engagement_empty_name_raises_error(self, tmp_path: Path) -> None:
        """Should raise ConfigurationError for empty engagement name."""
        config = tmp_path / ".yaml"  # Empty stem
        config.write_text("scope: [10.0.0.0/8]\n")

        manager = SessionManager()
        with pytest.raises(ConfigurationError) as exc_info:
            manager.create_engagement(config)

        assert "Invalid engagement name" in str(exc_info.value)

    def test_create_engagement_id_unique_rapid_calls(self, tmp_path: Path) -> None:
        """Rapid calls should generate unique IDs even with same name."""
        config = tmp_path / "test.yaml"
        config.write_text("name: rapid\n")
        
        manager = SessionManager()
        id1 = manager.create_engagement(config)
        id2 = manager.create_engagement(config)
        
        assert id1 != id2
        assert id1.startswith("rapid-")
        assert id2.startswith("rapid-")
        assert len(id1) > len("rapid-") + 15 

    def test_max_engagements_active_limit(self, tmp_path: Path) -> None:
        """Should raise ResourceLimitError when max_engagements reached."""
        manager = SessionManager(max_engagements=2)

        # Create 2 engagements (they're in INITIALIZING, which counts as active)
        for i in range(2):
            config = tmp_path / f"config{i}.yaml"
            config.write_text(f"name: test{i}\n")
            manager.create_engagement(config)

        # Third should fail
        config = tmp_path / "config2.yaml"
        config.write_text("name: test2\n")

        with pytest.raises(ResourceLimitError) as exc_info:
            manager.create_engagement(config)

        assert "Maximum active engagements (2) reached" in str(exc_info.value)
        assert exc_info.value.limit_type == "max_engagements"
        assert exc_info.value.max_value == 2

    def test_create_engagement_stores_config_path(self, tmp_path: Path) -> None:
        """Created engagement should store config path."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        context = manager.get_engagement(engagement_id)

        assert context is not None
        assert context.config_path == config


class TestSessionManagerHistoryPruning:
    """Tests for engagement history pruning."""

    @pytest.mark.asyncio
    async def test_prunes_oldest_stopped_engagement(self, tmp_path: Path) -> None:
        """Should prune oldest STOPPED engagement when history limit reached."""
        manager = SessionManager(max_engagements=5, max_history=2)
        
        # 1. Create and complete first engagement
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: first\n")
        id1 = manager.create_engagement(config1)
        await manager.start_engagement(id1)
        state, _ = await manager.stop_engagement(id1)
        manager.complete_engagement(id1)
        time.sleep(0.01) # Ensure timestamp diff
        
        # 2. Create second engagement (active)
        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: second\n")
        id2 = manager.create_engagement(config2)
        
        # History is full (2/2)
        assert len(manager.list_engagements()) == 2
        
        # 3. Create third engagement -> Should prune first (completed)
        config3 = tmp_path / "config3.yaml"
        config3.write_text("name: third\n")
        id3 = manager.create_engagement(config3)
        
        summaries = manager.list_engagements()
        ids = [s.id for s in summaries]
        
        assert len(ids) == 2
        assert id1 not in ids # Pruned
        assert id2 in ids
        assert id3 in ids
        
    def test_does_not_prune_active_engagements(self, tmp_path: Path) -> None:
        """Should NOT prune active engagements, raise ResourceLimitError instead."""
        manager = SessionManager(max_engagements=5, max_history=2)
        
        # 1. Create first engagement (ACTIVE)
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: first\n")
        id1 = manager.create_engagement(config1)
        
        # 2. Create second engagement (ACTIVE)
        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: second\n")
        id2 = manager.create_engagement(config2)
        
        # History is full (2/2) and ALL ACTIVE
        
        # 3. Create third engagement -> Should FAIL (cannot prune active)
        config3 = tmp_path / "config3.yaml"
        config3.write_text("name: third\n")
        
        with pytest.raises(ResourceLimitError) as exc_info:
            manager.create_engagement(config3)
            
        assert "Maximum total engagements" in str(exc_info.value)
        assert exc_info.value.limit_type == "max_history"


class TestSessionManagerGetEngagement:
    """Tests for SessionManager.get_engagement() methods."""

    def test_get_engagement_returns_context(self, tmp_path: Path) -> None:
        """get_engagement should return context for existing engagement."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        context = manager.get_engagement(engagement_id)

        assert context is not None
        assert context.id == engagement_id

    def test_get_engagement_returns_none_for_missing(self) -> None:
        """get_engagement should return None for missing engagement."""
        manager = SessionManager()
        context = manager.get_engagement("nonexistent-123")

        assert context is None

    def test_get_engagement_or_raise_returns_context(self, tmp_path: Path) -> None:
        """get_engagement_or_raise should return context for existing."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        context = manager.get_engagement_or_raise(engagement_id)

        assert context.id == engagement_id

    def test_get_engagement_or_raise_raises_for_missing(self) -> None:
        """get_engagement_or_raise should raise EngagementNotFoundError."""
        manager = SessionManager()

        with pytest.raises(EngagementNotFoundError) as exc_info:
            manager.get_engagement_or_raise("nonexistent-123")

        assert exc_info.value.engagement_id == "nonexistent-123"


class TestSessionManagerListEngagements:
    """Tests for SessionManager.list_engagements()."""

    def test_list_engagements_empty(self) -> None:
        """list_engagements should return empty list when no engagements."""
        manager = SessionManager()
        summaries = manager.list_engagements()

        assert summaries == []

    def test_list_engagements_returns_all(self, tmp_path: Path) -> None:
        """list_engagements should return all engagements."""
        manager = SessionManager()

        for i in range(3):
            config = tmp_path / f"config{i}.yaml"
            config.write_text(f"name: eng{i}\n")
            manager.create_engagement(config)
            time.sleep(0.01)  # Ensure different timestamps

        summaries = manager.list_engagements()

        assert len(summaries) == 3

    def test_list_engagements_sorted_newest_first(self, tmp_path: Path) -> None:
        """list_engagements should sort by created_at (newest first)."""
        manager = SessionManager()
        created_ids = []

        for i in range(3):
            config = tmp_path / f"config{i}.yaml"
            config.write_text(f"name: eng{i}\n")
            eid = manager.create_engagement(config)
            created_ids.append(eid)
            time.sleep(0.01)  # Ensure different timestamps

        summaries = manager.list_engagements()

        # Newest should be first
        assert summaries[0].id == created_ids[2]
        assert summaries[2].id == created_ids[0]

    @pytest.mark.asyncio
    async def test_list_engagements_includes_correct_fields(self, tmp_path: Path) -> None:
        """list_engagements should include all required fields."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        await manager.start_engagement(engagement_id)

        summaries = manager.list_engagements()

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.id == engagement_id
        assert summary.state == "RUNNING"
        assert summary.agent_count == 0
        assert summary.finding_count == 0
        assert isinstance(summary.created_at, datetime)


@pytest.mark.asyncio
class TestSessionManagerLifecycleOperations:
    """Tests for engagement lifecycle operations."""

    async def test_start_engagement_transitions_to_running(self, tmp_path: Path) -> None:
        """start_engagement should transition to RUNNING."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        state = await manager.start_engagement(engagement_id)

        assert state == EngagementState.RUNNING

    async def test_pause_engagement_transitions_to_paused(self, tmp_path: Path) -> None:
        """pause_engagement should transition to PAUSED."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        await manager.start_engagement(engagement_id)
        state = manager.pause_engagement(engagement_id)

        assert state == EngagementState.PAUSED

    async def test_resume_engagement_transitions_to_running(self, tmp_path: Path) -> None:
        """resume_engagement should transition to RUNNING."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        await manager.start_engagement(engagement_id)
        manager.pause_engagement(engagement_id)
        state = manager.resume_engagement(engagement_id)

        assert state == EngagementState.RUNNING

    async def test_stop_engagement_transitions_to_stopped(self, tmp_path: Path) -> None:
        """stop_engagement should transition to STOPPED."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        await manager.start_engagement(engagement_id)
        state, checkpoint_path = await manager.stop_engagement(engagement_id)

        assert state == EngagementState.STOPPED
        assert checkpoint_path is None  # No checkpoint manager configured

    async def test_complete_engagement_transitions_to_completed(
        self, tmp_path: Path
    ) -> None:
        """complete_engagement should transition to COMPLETED."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        await manager.start_engagement(engagement_id)
        await manager.stop_engagement(engagement_id)
        state = manager.complete_engagement(engagement_id)

        assert state == EngagementState.COMPLETED

    async def test_lifecycle_operations_raise_for_missing_engagement(self) -> None:
        """Lifecycle operations should raise EngagementNotFoundError."""
        manager = SessionManager()

        with pytest.raises(EngagementNotFoundError):
            await manager.start_engagement("nonexistent")

        with pytest.raises(EngagementNotFoundError):
            manager.pause_engagement("nonexistent")

        with pytest.raises(EngagementNotFoundError):
            manager.resume_engagement("nonexistent")

        with pytest.raises(EngagementNotFoundError):
            await manager.stop_engagement("nonexistent")

        with pytest.raises(EngagementNotFoundError):
            manager.complete_engagement("nonexistent")

    async def test_start_engagement_already_running(self, tmp_path: Path) -> None:
        """start_engagement should raise InvalidStateTransition if already RUNNING."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        await manager.start_engagement(engagement_id)

        with pytest.raises(InvalidStateTransition):
            await manager.start_engagement(engagement_id)


@pytest.mark.asyncio
class TestSessionManagerRemoveEngagement:
    """Tests for SessionManager.remove_engagement()."""

    async def test_remove_stopped_engagement_succeeds(self, tmp_path: Path) -> None:
        """remove_engagement should succeed for STOPPED engagement."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        await manager.start_engagement(engagement_id)
        await manager.stop_engagement(engagement_id)

        result = await manager.remove_engagement(engagement_id)

        assert result is True
        assert manager.get_engagement(engagement_id) is None

    async def test_remove_completed_engagement_succeeds(self, tmp_path: Path) -> None:
        """remove_engagement should succeed for COMPLETED engagement."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        await manager.start_engagement(engagement_id)
        await manager.stop_engagement(engagement_id)
        manager.complete_engagement(engagement_id)

        result = await manager.remove_engagement(engagement_id)

        assert result is True
        assert manager.get_engagement(engagement_id) is None

    @pytest.mark.asyncio
    async def test_remove_nonexistent_returns_false(self) -> None:
        """remove_engagement should return False for nonexistent."""
        manager = SessionManager()
        result = await manager.remove_engagement("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_initializing_raises_error(self, tmp_path: Path) -> None:
        """remove_engagement should raise for INITIALIZING engagement."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)

        with pytest.raises(InvalidStateTransition) as exc_info:
            await manager.remove_engagement(engagement_id)

        assert "Cannot remove engagement" in str(exc_info.value)
        assert "INITIALIZING" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_remove_running_raises_error(self, tmp_path: Path) -> None:
        """remove_engagement should raise for RUNNING engagement."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        await manager.start_engagement(engagement_id)

        with pytest.raises(InvalidStateTransition) as exc_info:
            await manager.remove_engagement(engagement_id)

        assert "Cannot remove engagement" in str(exc_info.value)
        assert "RUNNING" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_remove_paused_raises_error(self, tmp_path: Path) -> None:
        """remove_engagement should raise for PAUSED engagement."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        await manager.start_engagement(engagement_id)
        manager.pause_engagement(engagement_id)

        with pytest.raises(InvalidStateTransition) as exc_info:
            await manager.remove_engagement(engagement_id)

        assert "Cannot remove engagement" in str(exc_info.value)
        assert "PAUSED" in str(exc_info.value)


class TestSessionManagerCapacity:
    """Tests for capacity tracking."""

    def test_active_count_includes_initializing(self, tmp_path: Path) -> None:
        """active_count should include INITIALIZING engagements."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        manager.create_engagement(config)

        assert manager.active_count == 1

    @pytest.mark.asyncio
    async def test_active_count_includes_running(self, tmp_path: Path) -> None:
        """active_count should include RUNNING engagements."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)

        assert manager.active_count == 1

    @pytest.mark.asyncio
    async def test_active_count_excludes_stopped(self, tmp_path: Path) -> None:
        """active_count should exclude STOPPED engagements."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)
        await manager.stop_engagement(eid)

        assert manager.active_count == 0

    @pytest.mark.asyncio
    async def test_remaining_capacity_updates(self, tmp_path: Path) -> None:
        """remaining_capacity should update as engagements are added/stopped."""
        manager = SessionManager(max_engagements=3)

        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        eid1 = manager.create_engagement(config1)

        assert manager.remaining_capacity == 2

        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")
        manager.create_engagement(config2)

        assert manager.remaining_capacity == 1

        # Stop first engagement
        await manager.start_engagement(eid1)
        await manager.stop_engagement(eid1)

        assert manager.remaining_capacity == 2


class TestSessionManagerIsolation:
    """Tests for engagement isolation."""

    @pytest.mark.asyncio
    async def test_engagements_have_separate_state_machines(self, tmp_path: Path) -> None:
        """Each engagement should have its own state machine."""
        manager = SessionManager()

        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        eid1 = manager.create_engagement(config1)

        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")
        eid2 = manager.create_engagement(config2)

        # Start only the first
        await manager.start_engagement(eid1)

        ctx1 = manager.get_engagement(eid1)
        ctx2 = manager.get_engagement(eid2)

        assert ctx1 is not None
        assert ctx2 is not None
        assert ctx1.state == EngagementState.RUNNING
        assert ctx2.state == EngagementState.INITIALIZING

    @pytest.mark.asyncio
    async def test_state_change_doesnt_affect_others(self, tmp_path: Path) -> None:
        """State change in one engagement should not affect others."""
        manager = SessionManager()

        # Create and start both engagements
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        eid1 = manager.create_engagement(config1)
        await manager.start_engagement(eid1)

        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")
        eid2 = manager.create_engagement(config2)
        await manager.start_engagement(eid2)

        # Pause first, stop second
        manager.pause_engagement(eid1)
        await manager.stop_engagement(eid2)

        ctx1 = manager.get_engagement(eid1)
        ctx2 = manager.get_engagement(eid2)

        assert ctx1 is not None
        assert ctx2 is not None
        assert ctx1.state == EngagementState.PAUSED
        assert ctx2.state == EngagementState.STOPPED


@pytest.mark.asyncio
class TestSessionManagerSubscriptions:
    """Tests for engagement subscription methods."""

    async def test_subscribe_returns_subscription_id(self, tmp_path: Path) -> None:
        """subscribe_to_engagement should return unique subscription ID."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)

        callback = MagicMock()
        sub_id = manager.subscribe_to_engagement(eid, callback)

        assert sub_id.startswith("sub-")
        assert len(sub_id) > 4

    async def test_subscribe_requires_running_or_paused(self, tmp_path: Path) -> None:
        """subscribe_to_engagement requires RUNNING or PAUSED state."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        # Engagement is INITIALIZING

        callback = MagicMock()
        with pytest.raises(InvalidStateTransition) as exc_info:
            manager.subscribe_to_engagement(eid, callback)

        assert "INITIALIZING" in str(exc_info.value)

    async def test_subscribe_works_for_paused(self, tmp_path: Path) -> None:
        """subscribe_to_engagement should work for PAUSED engagements."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)
        manager.pause_engagement(eid)

        callback = MagicMock()
        sub_id = manager.subscribe_to_engagement(eid, callback)

        assert sub_id.startswith("sub-")

    async def test_subscribe_raises_for_nonexistent(self) -> None:
        """subscribe_to_engagement should raise for nonexistent engagement."""
        manager = SessionManager()
        callback = MagicMock()

        with pytest.raises(EngagementNotFoundError):
            manager.subscribe_to_engagement("nonexistent", callback)

    async def test_unsubscribe_removes_subscription(self, tmp_path: Path) -> None:
        """unsubscribe_from_engagement should remove the callback."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)

        callback = MagicMock()
        sub_id = manager.subscribe_to_engagement(eid, callback)
        assert manager.get_subscription_count(eid) == 1

        manager.unsubscribe_from_engagement(sub_id)
        assert manager.get_subscription_count(eid) == 0

    async def test_unsubscribe_nonexistent_is_noop(self) -> None:
        """unsubscribe_from_engagement for unknown ID should be no-op."""
        manager = SessionManager()
        # Should not raise
        manager.unsubscribe_from_engagement("nonexistent-sub-id")

    async def test_broadcast_event_calls_callbacks(self, tmp_path: Path) -> None:
        """broadcast_event should call all subscriber callbacks."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)

        callback1 = MagicMock()
        callback2 = MagicMock()
        manager.subscribe_to_engagement(eid, callback1)
        manager.subscribe_to_engagement(eid, callback2)

        event = {"type": "test", "data": "value"}
        count = manager.broadcast_event(eid, event)

        assert count == 2
        callback1.assert_called_once_with(event)
        callback2.assert_called_once_with(event)

    async def test_broadcast_event_no_subscribers(self, tmp_path: Path) -> None:
        """broadcast_event with no subscribers returns 0."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)

        event = {"type": "test"}
        count = manager.broadcast_event(eid, event)

        assert count == 0

    async def test_broadcast_removes_broken_callbacks(self, tmp_path: Path) -> None:
        """broadcast_event should remove callbacks that raise exceptions."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)

        good_callback = MagicMock()
        bad_callback = MagicMock(side_effect=Exception("callback error"))
        manager.subscribe_to_engagement(eid, good_callback)
        manager.subscribe_to_engagement(eid, bad_callback)
        assert manager.get_subscription_count(eid) == 2

        event = {"type": "test"}
        count = manager.broadcast_event(eid, event)

        # Only good callback succeeded
        assert count == 1
        # Bad callback was removed
        assert manager.get_subscription_count(eid) == 1

    async def test_subscription_count_accurate(self, tmp_path: Path) -> None:
        """get_subscription_count should return accurate count."""
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)

        assert manager.get_subscription_count(eid) == 0

        sub1 = manager.subscribe_to_engagement(eid, MagicMock())
        assert manager.get_subscription_count(eid) == 1

        manager.subscribe_to_engagement(eid, MagicMock())
        assert manager.get_subscription_count(eid) == 2

        manager.unsubscribe_from_engagement(sub1)
        assert manager.get_subscription_count(eid) == 1

    async def test_subscription_count_nonexistent_returns_zero(self) -> None:
        """get_subscription_count for unknown engagement returns 0."""
        manager = SessionManager()
        assert manager.get_subscription_count("nonexistent") == 0

    async def test_multiple_engagements_isolated_subscriptions(
        self, tmp_path: Path
    ) -> None:
        """Subscriptions should be isolated per engagement."""
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")

        manager = SessionManager()
        eid1 = manager.create_engagement(config1)
        eid2 = manager.create_engagement(config2)
        await manager.start_engagement(eid1)
        await manager.start_engagement(eid2)

        callback1 = MagicMock()
        callback2 = MagicMock()
        manager.subscribe_to_engagement(eid1, callback1)
        manager.subscribe_to_engagement(eid2, callback2)

        # Broadcast to eng1 only
        manager.broadcast_event(eid1, {"type": "test1"})

        callback1.assert_called_once()
        callback2.assert_not_called()


# =============================================================================
# Story 2.11: Graceful Shutdown Tests
# =============================================================================

@pytest.mark.asyncio
class TestSessionManagerGracefulShutdown:
    """Tests for graceful shutdown methods (Story 2.11)."""

    async def test_pause_all_engagements_pauses_running(self, tmp_path: Path) -> None:
        """pause_all_engagements should pause all RUNNING engagements."""
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")

        manager = SessionManager()
        eid1 = manager.create_engagement(config1)
        eid2 = manager.create_engagement(config2)
        await manager.start_engagement(eid1)
        await manager.start_engagement(eid2)

        # Both are RUNNING
        assert manager.get_engagement(eid1).state == EngagementState.RUNNING
        assert manager.get_engagement(eid2).state == EngagementState.RUNNING

        paused_ids = manager.pause_all_engagements()

        assert len(paused_ids) == 2
        assert eid1 in paused_ids
        assert eid2 in paused_ids
        assert manager.get_engagement(eid1).state == EngagementState.PAUSED
        assert manager.get_engagement(eid2).state == EngagementState.PAUSED

    async def test_pause_all_engagements_skips_paused(self, tmp_path: Path) -> None:
        """pause_all_engagements should skip already PAUSED engagements."""
        config = tmp_path / "config.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)
        manager.pause_engagement(eid)  # Already paused

        paused_ids = manager.pause_all_engagements()

        assert len(paused_ids) == 0  # Nothing to pause

    async def test_pause_all_engagements_continues_on_error(self, tmp_path: Path) -> None:
        """pause_all_engagements should continue if one engagement fails."""
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")

        manager = SessionManager()
        eid1 = manager.create_engagement(config1)
        eid2 = manager.create_engagement(config2)
        await manager.start_engagement(eid1)
        await manager.start_engagement(eid2)

        # Force first pause to fail by mocking state machine
        ctx1 = manager.get_engagement(eid1)
        ctx1.state_machine.pause = MagicMock(side_effect=Exception("pause failed"))

        paused_ids = manager.pause_all_engagements()

        # Second one should still be paused
        assert len(paused_ids) == 1
        assert eid2 in paused_ids
        assert manager.get_engagement(eid2).state == EngagementState.PAUSED

    async def test_checkpoint_all_engagements_checkpoints_paused(self, tmp_path: Path) -> None:
        """checkpoint_all_engagements should checkpoint all PAUSED engagements."""
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")

        manager = SessionManager()
        eid1 = manager.create_engagement(config1)
        eid2 = manager.create_engagement(config2)
        await manager.start_engagement(eid1)
        await manager.start_engagement(eid2)
        manager.pause_engagement(eid1)
        manager.pause_engagement(eid2)

        checkpoints, errors = await manager.checkpoint_all_engagements()

        assert len(checkpoints) == 2
        assert len(errors) == 0
        assert eid1 in checkpoints
        assert eid2 in checkpoints
        assert manager.get_engagement(eid1).state == EngagementState.STOPPED
        assert manager.get_engagement(eid2).state == EngagementState.STOPPED

    async def test_checkpoint_all_engagements_continues_on_error(self, tmp_path: Path) -> None:
        """checkpoint_all_engagements should continue if one fails."""
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")

        manager = SessionManager()
        eid1 = manager.create_engagement(config1)
        eid2 = manager.create_engagement(config2)
        await manager.start_engagement(eid1)
        await manager.start_engagement(eid2)
        manager.pause_engagement(eid1)
        manager.pause_engagement(eid2)

        # Force first stop to fail
        ctx1 = manager.get_engagement(eid1)
        ctx1.state_machine.stop = MagicMock(side_effect=Exception("stop failed"))

        checkpoints, errors = await manager.checkpoint_all_engagements()

        # eid1 failed so not in checkpoints, eid2 succeeded
        assert len(checkpoints) == 1
        assert eid2 in checkpoints
        assert len(errors) == 1
        assert eid1 in errors[0]  # Error message contains engagement ID
        assert manager.get_engagement(eid2).state == EngagementState.STOPPED

    async def test_graceful_shutdown_sequence(self, tmp_path: Path) -> None:
        """graceful_shutdown should pause then checkpoint all engagements."""
        from cyberred.daemon.session_manager import ShutdownResult
        
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")

        manager = SessionManager()
        eid1 = manager.create_engagement(config1)
        eid2 = manager.create_engagement(config2)
        await manager.start_engagement(eid1)
        await manager.start_engagement(eid2)

        result = await manager.graceful_shutdown()

        assert isinstance(result, ShutdownResult)
        assert len(result.paused_ids) == 2
        assert len(result.checkpoint_paths) == 2
        assert len(result.errors) == 0
        # All engagements should be STOPPED
        assert manager.get_engagement(eid1).state == EngagementState.STOPPED
        assert manager.get_engagement(eid2).state == EngagementState.STOPPED

    async def test_notify_all_clients_broadcasts_to_all(self, tmp_path: Path) -> None:
        """notify_all_clients should broadcast event to all subscriptions."""
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")

        manager = SessionManager()
        eid1 = manager.create_engagement(config1)
        eid2 = manager.create_engagement(config2)
        await manager.start_engagement(eid1)
        await manager.start_engagement(eid2)

        callback1 = MagicMock()
        callback2 = MagicMock()
        callback3 = MagicMock()
        manager.subscribe_to_engagement(eid1, callback1)
        manager.subscribe_to_engagement(eid1, callback2)
        manager.subscribe_to_engagement(eid2, callback3)

        event = {"type": "shutdown"}
        count = manager.notify_all_clients(event)

        assert count == 3
        callback1.assert_called_once_with(event)
        callback2.assert_called_once_with(event)
        callback3.assert_called_once_with(event)

    async def test_notify_all_clients_handles_broken_callbacks(self, tmp_path: Path) -> None:
        """notify_all_clients should remove broken callbacks."""
        config = tmp_path / "config.yaml"
        config.write_text("name: test\n")

        manager = SessionManager()
        eid = manager.create_engagement(config)
        await manager.start_engagement(eid)

        good_callback = MagicMock()
        bad_callback = MagicMock(side_effect=Exception("broken"))
        manager.subscribe_to_engagement(eid, good_callback)
        manager.subscribe_to_engagement(eid, bad_callback)

        event = {"type": "shutdown"}
        count = manager.notify_all_clients(event)

        # Only good callback succeeded
        assert count == 1
        # Bad callback was removed
        assert manager.get_subscription_count(eid) == 1

    async def test_disconnect_all_clients_clears_all(self, tmp_path: Path) -> None:
        """disconnect_all_clients should clear all subscriptions."""
        config1 = tmp_path / "config1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "config2.yaml"
        config2.write_text("name: eng2\n")

        manager = SessionManager()
        eid1 = manager.create_engagement(config1)
        eid2 = manager.create_engagement(config2)
        await manager.start_engagement(eid1)
        await manager.start_engagement(eid2)

        manager.subscribe_to_engagement(eid1, MagicMock())
        manager.subscribe_to_engagement(eid1, MagicMock())
        manager.subscribe_to_engagement(eid2, MagicMock())

        count = manager.disconnect_all_clients()

        assert count == 3
        assert manager.get_subscription_count(eid1) == 0
        assert manager.get_subscription_count(eid2) == 0

    async def test_disconnect_all_clients_empty_is_safe(self) -> None:
        """disconnect_all_clients with no subscriptions returns 0."""
        manager = SessionManager()
        count = manager.disconnect_all_clients()
        assert count == 0


@pytest.mark.asyncio
class TestSessionManagerCoverage:
    """Tests to close coverage gaps for 100%."""

    async def test_stop_engagement_raises_invalid_transition(self, tmp_path: Path) -> None:
        """stop_engagement should raise if transition is invalid."""
        config = tmp_path / "test-inv.yaml"
        config.write_text("name: test-inv\n")
        
        manager = SessionManager()
        eid = manager.create_engagement(config)
        
        # Replace context with mock to control state
        mock_ctx = MagicMock()
        mock_ctx.state = EngagementState.COMPLETED
        manager._engagements[eid] = mock_ctx
        
        with pytest.raises(InvalidStateTransition):
            await manager.stop_engagement(eid)

    async def test_stop_engagement_extracts_scope_path(self, tmp_path: Path) -> None:
        """stop_engagement should extract scope_path from config for checkpoint."""
        scope_location = tmp_path / "scope.md"
        scope_location.write_text("# Scope")
        
        config = tmp_path / "test-scope.yaml"
        # use valid name 'test-scope' (no underscores allowed if restrictive)
        config.write_text(f"name: test-scope\nscope_path: {scope_location}\n")
        
        manager = SessionManager()
        
        # Mock checkpoint manager
        mock_cp = MagicMock()
        mock_cp.save = AsyncMock(return_value=Path("/tmp/checkpoint"))
        manager._checkpoint_manager = mock_cp
        
        eid = manager.create_engagement(config)
        
        # Replace context with mock to control state and config
        mock_ctx = MagicMock()
        mock_ctx.state = EngagementState.PAUSED
        mock_ctx.config_path = config
        manager._engagements[eid] = mock_ctx
        
        await manager.stop_engagement(eid)
        
        # Verify save called with correct scope_path
        args = mock_cp.save.call_args
        assert args.kwargs["scope_path"] == scope_location

    async def test_remove_engagement_cleans_up_checkpoint(self, tmp_path: Path) -> None:
        """remove_engagement should delete checkpoint if it exists."""
        config = tmp_path / "test-rem.yaml"
        config.write_text("name: test-rem\n")
        
        manager = SessionManager()
        
        # Mock checkpoint manager
        mock_cp = MagicMock()
        mock_cp.delete = AsyncMock()
        manager._checkpoint_manager = mock_cp
        
        eid = manager.create_engagement(config)
        
        # Replace context with mock to control state
        mock_ctx = MagicMock()
        mock_ctx.state = EngagementState.STOPPED
        manager._engagements[eid] = mock_ctx
        
        await manager.remove_engagement(eid)
        
        mock_cp.delete.assert_called_once_with(eid)

    async def test_unsubscribe_removes_specific_subscription(self, tmp_path: Path) -> None:
        """unsubscribe_from_engagement should remove specific sub."""
        config = tmp_path / "test-sub.yaml"
        config.write_text("name: test-sub\n")
        
        # Mock preflight to avoid actual execution
        with patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
            runner = MagicMock()
            runner.run_all = AsyncMock(return_value=[])
            runner.validate_results = MagicMock()
            MockRunner.return_value = runner

            manager = SessionManager()
            eid = manager.create_engagement(config)
            await manager.start_engagement(eid)
            
            sub_id = manager.subscribe_to_engagement(eid, MagicMock())
            assert manager.get_subscription_count(eid) == 1
            
            manager.unsubscribe_from_engagement(sub_id)
            assert manager.get_subscription_count(eid) == 0

    async def test_stop_engagement_handles_config_read_error(self, tmp_path: Path) -> None:
        """stop_engagement should continue without scope if config read fails."""
        # Create directory where file expected to cause read error (IsADirectoryError)
        config = tmp_path / "test-err.yaml"
        config.mkdir() 
        
        manager = SessionManager()
        
        # Mock checkpoint manager
        mock_cp = MagicMock()
        mock_cp.save = AsyncMock(return_value=Path("/tmp/checkpoint"))
        manager._checkpoint_manager = mock_cp
        
        # Create dummy engagement entry manually since create_engagement would fail reading config
        eid = "test-err"
        mock_ctx = MagicMock()
        mock_ctx.state = EngagementState.PAUSED
        mock_ctx.config_path = config
        manager._engagements[eid] = mock_ctx
        
        await manager.stop_engagement(eid)
        
        # Should call save with scope_path=None
        mock_cp.save.assert_called_once()
        assert mock_cp.save.call_args.kwargs["scope_path"] is None

    async def test_unsubscribe_ignores_unknown_subscription(self) -> None:
        """unsubscribe_from_engagement should safely ignore unknown ID."""
        manager = SessionManager()
        # Should not raise
        manager.unsubscribe_from_engagement("unknown-id")

    async def test_notify_handler_cleans_up_concurrent_removal(self, tmp_path: Path) -> None:
        """notify_all_clients should handle concurrent unsubscription during iteration."""
        config = tmp_path / "test-conc.yaml"
        config.write_text("name: test-conc\n")
        
        # Mock preflight
        with patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
            runner = MagicMock()
            runner.run_all = AsyncMock(return_value=[])
            runner.validate_results = MagicMock()
            MockRunner.return_value = runner

            manager = SessionManager()
            eid = manager.create_engagement(config)
            await manager.start_engagement(eid)
            
            # Define a callback that raises error AND removes the subscription
            # This simulates a race or side-effect where sub is gone before cleanup
            def evil_callback(event):
                # Remove the engagement from subscriptions entirely to trigger line 891 False branch
                if eid in manager._subscriptions:
                    del manager._subscriptions[eid]
                raise ValueError("Boom")
                
            manager.subscribe_to_engagement(eid, evil_callback)
            
            # Trigger notification
            count = manager.notify_all_clients({"type": "test"})
            
            # Should return 0 (0 sent, 1 failed)
            assert count == 0
            # Subscription dict should be empty (deleted by callback)
            assert eid not in manager._subscriptions
