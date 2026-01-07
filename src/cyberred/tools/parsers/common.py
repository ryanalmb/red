import uuid
import hashlib
from typing import Optional
from datetime import datetime, timezone
from cyberred.core.models import Finding

def generate_topic(target: str, finding_type: str) -> str:
    """
    Generate architecture-compliant topic: findings:{target_hash}:{type}
    Target hash is first 8 chars of MD5(target).
    """
    target_hash = hashlib.md5(target.encode()).hexdigest()[:8]
    return f"findings:{target_hash}:{finding_type}"

def create_finding(
    type_val: str,
    severity: str,
    target: str,
    evidence: str,
    agent_id: str,
    tool: str,
    topic: Optional[str] = None
) -> Finding:
    """
    Factory for Finding objects. 
    If topic is None, auto-generated using generate_topic(target, type_val).
    """
    if topic is None:
        topic = generate_topic(target, type_val)
        
    return Finding(
        id=str(uuid.uuid4()),
        type=type_val,
        severity=severity,
        target=target,
        evidence=evidence,
        agent_id=agent_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        tool=tool,
        topic=topic,
        signature=""
    )
