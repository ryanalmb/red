import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from cyberred.daemon.session_manager import SessionManager
from cyberred.core.exceptions import PreFlightCheckError, PreFlightWarningError
from cyberred.daemon.preflight import CheckResult, CheckStatus, CheckPriority

@pytest.fixture
def mock_runner():
    # Patch WHERE it is used
    with patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
        runner_instance = Mock()
        runner_instance.run_all = AsyncMock()
        MockRunner.return_value = runner_instance
        yield runner_instance


@pytest.fixture
def manager(mock_runner, tmp_path):
    # Setup manager with pre-created engagement
    mgr = SessionManager()
    config = tmp_path / "eng.yaml"
    config.write_text("name: eng1")
    eid = mgr.create_engagement(config)
    return mgr, eid, mock_runner

@pytest.mark.asyncio
async def test_start_engagement_runs_preflight(manager):
    mgr, eid, runner = manager
    
    # Mock successful run
    runner.run_all.return_value = [CheckResult("PASS_CHECK", CheckStatus.PASS, CheckPriority.P0, "OK")]
    
    # Needs to be awaited if we convert to async. 
    # Current code is sync, so this test expects it to be/become async?
    # The Task 6 implies integration which means making it async.
    # So I will test it AS IF it is async.
    
    await mgr.start_engagement(eid)
    
    runner.run_all.assert_called_once()
    runner.validate_results.assert_called_once()

@pytest.mark.asyncio
async def test_start_engagement_passes_ignore_warnings(manager):
    mgr, eid, runner = manager
    runner.run_all.return_value = []
    
    await mgr.start_engagement(eid, ignore_warnings=True)
    
    # Validate passed ignore_warnings arg
    runner.validate_results.assert_called_once()
    args, kwargs = runner.validate_results.call_args
    assert kwargs.get("ignore_warnings") is True

@pytest.mark.asyncio
async def test_start_engagement_fails_p0(manager):
    mgr, eid, runner = manager
    
    # Mock P0 fail
    runner.validate_results.side_effect = PreFlightCheckError([
        CheckResult("FAIL", CheckStatus.FAIL, CheckPriority.P0, "Fail")
    ])
    
    with pytest.raises(PreFlightCheckError):
        await mgr.start_engagement(eid)
    
    # Verify state didn't change (should still be INITIALIZING if exception raised)
    eng = mgr.get_engagement(eid)
    assert str(eng.state) == "INITIALIZING"

@pytest.mark.asyncio
async def test_start_engagement_fails_p1_warn(manager):
    mgr, eid, runner = manager
    
    runner.validate_results.side_effect = PreFlightWarningError([
        CheckResult("WARN", CheckStatus.WARN, CheckPriority.P1, "Warn")
    ])
    
    with pytest.raises(PreFlightWarningError):
        await mgr.start_engagement(eid)

@pytest.mark.asyncio
async def test_start_engagement_config_load_error(tmp_path: Path) -> None:
    """start_engagement should raise ConfigurationError if config file cannot be read."""
    from cyberred.core.exceptions import ConfigurationError

    config = tmp_path / "broken.yaml"
    config.write_text("name: broken\n")
    
    manager = SessionManager()
    engagement_id = manager.create_engagement(config)
    
    # Mock file open to fail for this engagement's config path
    with patch("pathlib.Path.open", side_effect=OSError("Permission denied")):
        with pytest.raises(ConfigurationError) as exc_info:
            await manager.start_engagement(engagement_id)
        assert "Failed to load config" in str(exc_info.value)
