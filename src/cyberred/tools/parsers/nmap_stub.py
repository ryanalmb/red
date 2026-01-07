"""Stub nmap parser for testing OutputProcessor routing.

This is a minimal implementation for testing purposes.
The full nmap parser will be implemented in Story 4-6.
"""
from typing import List
import uuid
from datetime import datetime, timezone
from cyberred.core.models import Finding
from cyberred.tools.parsers.base import ParserFn


def nmap_stub_parser(
    stdout: str, 
    stderr: str, 
    exit_code: int, 
    agent_id: str, 
    target: str
) -> List[Finding]:
    """Stub nmap parser for testing Tier 1 routing.
    
    This parser does minimal extraction for testing purposes.
    Real implementation in Story 4-6 will use proper XML parsing.
    
    Args:
        stdout: Tool stdout output
        stderr: Tool stderr output  
        exit_code: Process exit code
        agent_id: Agent that ran the tool
        target: Target of the scan
        
    Returns:
        List of Finding objects (stub returns single finding for any non-empty output)
    """
    if not stdout.strip():
        return []
    
    # Stub: create a single generic finding for non-empty output
    return [
        Finding(
            id=str(uuid.uuid4()),
            type="nmap_scan",
            severity="info",
            target=target,
            evidence=stdout[:500],
            agent_id=agent_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic=f"findings:{agent_id}:nmap",
            signature=""
        )
    ]
