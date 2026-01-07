import pytest
from cyberred.daemon.ipc import build_request, IPCCommand

def test_engagement_start_params_support():
    """Test that ENGAGEMENT_START accepts ignore_warnings parameter."""
    # This verifies the protocol supports the parameter structure
    req = build_request(
        IPCCommand.ENGAGEMENT_START, 
        config_path="/tmp/engagement.yaml", 
        ignore_warnings=True
    )
    
    assert req.command == IPCCommand.ENGAGEMENT_START
    assert req.params["config_path"] == "/tmp/engagement.yaml"
    assert req.params["ignore_warnings"] is True
    
    # Verify serialization
    json_str = req.to_json()
    assert "ignore_warnings" in json_str
