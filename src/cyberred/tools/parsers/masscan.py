"""Masscan output parser for structured finding extraction."""
import json
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def masscan_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse masscan output and return a list of Findings.
    
    Supports both JSON format (-oJ) and standard stdout format.
    
    Args:
        stdout: Raw masscan output (JSON or text)
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for discovered open ports
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Try JSON parsing first
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            findings.extend(_parse_json_output(data, agent_id, target))
            return findings
    except json.JSONDecodeError:
        pass
    
    # Fall back to stdout regex parsing
    findings.extend(_parse_stdout_output(stdout, agent_id, target))
    
    return findings


def _parse_json_output(data: list, agent_id: str, target: str) -> List[Finding]:
    """Parse masscan JSON output format."""
    findings: List[Finding] = []
    
    for entry in data:
        ip = entry.get("ip", target)
        ports = entry.get("ports", [])
        
        for port_info in ports:
            port = port_info.get("port")
            proto = port_info.get("proto", "tcp")
            status = port_info.get("status", "open")
            
            if port is None:
                continue
                
            evidence = f"Port {port}/{proto} {status} on {ip}"
            
            findings.append(common.create_finding(
                type_val="open_port",
                severity="info",
                target=ip,
                evidence=evidence,
                agent_id=agent_id,
                tool="masscan"
            ))
    
    return findings


def _parse_stdout_output(stdout: str, agent_id: str, target: str) -> List[Finding]:
    """Parse masscan stdout format (non-JSON)."""
    findings: List[Finding] = []
    
    # Pattern: Discovered open port 80/tcp on 192.168.1.1
    pattern = re.compile(r'Discovered open port (\d+)/(\w+) on (\S+)')
    
    for match in pattern.finditer(stdout):
        port, proto, ip = match.groups()
        
        evidence = f"Port {port}/{proto} open on {ip}"
        
        findings.append(common.create_finding(
            type_val="open_port",
            severity="info",
            target=ip,
            evidence=evidence,
            agent_id=agent_id,
            tool="masscan"
        ))
    
    return findings
