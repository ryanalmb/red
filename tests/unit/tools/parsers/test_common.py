import pytest
import uuid
from uuid import UUID
from cyberred.tools.parsers import common
from cyberred.core.models import Finding

def test_generate_topic_structure():
    """Test that generate_topic returns correct format."""
    target = "192.168.1.1"
    finding_type = "open_port"
    
    topic = common.generate_topic(target, finding_type)
    
    # Check prefix
    assert topic.startswith("findings:")
    # Check parts count
    parts = topic.split(":")
    assert len(parts) == 3
    # Check hash length (first 8 chars of md5)
    assert len(parts[1]) == 8
    # Check type suffix
    assert parts[2] == finding_type

def test_generate_topic_consistency():
    """Test that generate_topic is deterministic."""
    target = "example.com"
    t1 = common.generate_topic(target, "vuln")
    t2 = common.generate_topic(target, "vuln")
    assert t1 == t2

def test_create_finding_basic():
    """Test creating a valid Finding object."""
    agent_id_val = str(uuid.uuid4())
    finding = common.create_finding(
        type_val="test_type",
        severity="high",
        target="10.0.0.1",
        evidence="Some evidence",
        agent_id=agent_id_val,
        tool="test_tool"
    )
    
    assert isinstance(finding, Finding)
    assert finding.type == "test_type"
    assert finding.severity == "high"
    assert finding.target == "10.0.0.1"
    assert finding.evidence == "Some evidence"
    assert finding.agent_id == agent_id_val
    assert finding.tool == "test_tool"
    
    # Check auto-generated fields
    assert finding.topic == common.generate_topic("10.0.0.1", "test_type")
    assert finding.timestamp is not None
    # ID should be a valid UUID string
    assert UUID(finding.id)

def test_create_finding_custom_topic():
    """Test creating a finding with an explicit topic."""
    custom_topic = "my:custom:topic"
    finding = common.create_finding(
        type_val="test",
        severity="low",
        target="target",
        evidence="evidence",
        agent_id=str(uuid.uuid4()),
        tool="tool",
        topic=custom_topic
    )
    
    assert finding.topic == custom_topic
