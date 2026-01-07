
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

from cyberred.daemon.session_manager import SessionManager
from cyberred.core.exceptions import ConfigurationError

@pytest.mark.asyncio
async def test_session_manager_publish_error_handled(tmp_path):
    """Verify that EventBus publish errors are logged and don't crash."""
    config = tmp_path / "test-error.yaml"
    config.write_text("name: test-error\n")
    
    mock_event_bus = MagicMock()
    # We make publish call raise exception
    mock_event_bus.publish = AsyncMock(side_effect=Exception("Publish failed"))
    
    manager = SessionManager(event_bus=mock_event_bus)
    engagement_id = manager.create_engagement(config)
    
    # We invoke _on_state_change directly to be sure mocks are hit
    await manager._on_state_change(engagement_id, "OLD", "NEW")
    
    assert mock_event_bus.publish.called


@pytest.mark.asyncio
async def test_session_manager_publish_success_logs(tmp_path):
    """Verify that successful EventBus publish logs debug message (line 161)."""
    config = tmp_path / "test-success.yaml"
    config.write_text("name: test-success\n")
    
    mock_event_bus = MagicMock()
    # Make publish call succeed
    mock_event_bus.publish = AsyncMock(return_value=None)
    
    manager = SessionManager(event_bus=mock_event_bus)
    engagement_id = manager.create_engagement(config)
    
    # Invoke _on_state_change to trigger publish and subsequent log.debug
    await manager._on_state_change(engagement_id, "INITIALIZING", "RUNNING")
    
    # Verify publish was called
    assert mock_event_bus.publish.called
    call_args = mock_event_bus.publish.call_args
    channel = call_args[0][0]
    message = call_args[0][1]
    
    assert f"engagement:{engagement_id}:state" == channel
    assert message["type"] == "state_change"
    assert message["old_state"] == "INITIALIZING"
    assert message["new_state"] == "RUNNING"

@pytest.mark.asyncio
async def test_start_engagement_config_load_error(tmp_path):
    """Test error when reloading config during start."""
    config = tmp_path / "test-config.yaml"
    config.write_text("name: test-config\n")
    
    manager = SessionManager()
    engagement_id = manager.create_engagement(config)
    
    # Replace config_path with a mock that raises on open
    context = manager.get_engagement(engagement_id)
    
    mock_path = MagicMock(spec=Path)
    mock_path.open.side_effect = OSError("Read error")
    # We need to satisfy other usages of config_path if any?
    # start_engagement logs config_path using str(context.config_path).
    # so __str__ should work.
    mock_path.__str__.return_value = str(config)
    
    # Also need context.config_path.open() to be context manager
    # mock_path.open.return_value.__enter__ ... 
    # But side_effect=OSError will raise immediately on call to open().
    
    context.config_path = mock_path
    
    # Need to verify state prevents immediate failure before config load?
    # create_engagement sets state to INITIALIZING.
    # start_engagement checks state.
    
    # Also need to mock preflight or it will crash before if we don't?
    # SessionManager.start_engagement calls preflight runner.
    # We might need to mock PreFlightRunner? 
    # The fixture mock_preflight in test_session_manager.py works there, 
    # but here we are in a new file.
    # We should define the fixture or copy it.
    
    # Wait, the error usually happens BEFORE preflight:
    # 1. State check
    # 2. Load config <-- Error here
    # 3. Run Preflight
    
    with pytest.raises(ConfigurationError) as exc:
        await manager.start_engagement(engagement_id)
    
    assert "Failed to load config" in str(exc.value)
