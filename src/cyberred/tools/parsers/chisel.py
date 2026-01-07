"""Chisel output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def chisel_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse chisel output and return a list of Findings.
    
    Detects tunnel establishment and connection status.
    
    Args:
        stdout: Raw chisel output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for established tunnels
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Server started
        # Pattern: server: Listening on 0.0.0.0:8080
        server_match = re.search(r'(?:server|Listening)\s+(?:on\s+)?(\S+:\d+)', line, re.IGNORECASE)
        if server_match:
            listen_addr = server_match.group(1)
            
            findings.append(common.create_finding(
                type_val="tunnel",
                severity="info",
                target=target,
                evidence=f"Chisel server listening on {listen_addr}",
                agent_id=agent_id,
                tool="chisel"
            ))
            continue
        
        # Client connected / tunnel established
        # Pattern: client: Connected / Proxy: R:8080 => 127.0.0.1:80
        tunnel_match = re.search(r'(?:Proxy|proxy)\s*:\s*(\S+)\s*=>\s*(\S+)', line)
        if tunnel_match:
            local_spec, remote_spec = tunnel_match.groups()
            
            findings.append(common.create_finding(
                type_val="tunnel",
                severity="info",
                target=target,
                evidence=f"Tunnel established: {local_spec} => {remote_spec}",
                agent_id=agent_id,
                tool="chisel"
            ))
            continue
        
        # Connection success
        connect_match = re.search(r'(?:client|Connected)\s+(?:to\s+)?(\S+)', line, re.IGNORECASE)
        if connect_match and 'connected' in line.lower():
            server_addr = connect_match.group(1)
            
            findings.append(common.create_finding(
                type_val="tunnel",
                severity="info",
                target=target,
                evidence=f"Chisel client connected to {server_addr}",
                agent_id=agent_id,
                tool="chisel"
            ))
    
    return findings
