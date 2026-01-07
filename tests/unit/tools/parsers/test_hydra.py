import pytest
import uuid
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import hydra

def test_hydra_parser_signature():
    """Test that hydra_parser matches the ParserFn signature."""
    assert hasattr(hydra, 'hydra_parser')
    assert callable(hydra.hydra_parser)
    
    try:
        # Pass empty string for now
        result = hydra.hydra_parser(
            stdout="",
            agent_id=str(uuid.uuid4()),
            target="test-target"
        )
        assert isinstance(result, list)
    except Exception as e:
        pytest.fail(f"hydra_parser raised unexpected exception: {e}")

def test_hydra_credentials():
    """Test parsing of success credentials from Hydra."""
    stdout = """
Hydra v9.4 (c) 2022 by van Hauser/THC - Please do not use in military or secret service organizations, or for illegal purposes.

[DATA] max 16 tasks per 1 server, overall 16 tasks, 219 login tries (l:1/p:219), ~13 tries per task
[DATA] attacking ssh://192.168.1.5:22/
[22][ssh] host: 192.168.1.5   login: admin   password: password123
[80][http-get] host: 192.168.1.5   login: user   password: complex_password!
1 of 1 target successfully completed, 2 valid passwords found
    """
    
    findings = hydra.hydra_parser(
        stdout=stdout,
        agent_id=str(uuid.uuid4()),
        target="192.168.1.5"
    )
    
    assert len(findings) == 2
    
    # Check SSH credential
    ssh = next((f for f in findings if "ssh" in f.evidence), None)
    assert ssh is not None
    assert ssh.type == "credential"
    assert ssh.severity == "critical"
    assert "admin:password123" in ssh.evidence
    
    # Check HTTP credential
    http = next((f for f in findings if "http-get" in f.evidence), None)
    assert http is not None
    assert http.severity == "critical"
    assert "user:complex_password!" in http.evidence
