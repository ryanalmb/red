"""Gobuster output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def gobuster_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse gobuster output and return a list of Findings.
    
    Supports dir, dns, and vhost modes.
    
    Args:
        stdout: Raw gobuster output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for discovered paths/subdomains
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Detect mode and parse accordingly
    if 'Status:' in stdout:
        # Dir mode output
        findings.extend(_parse_dir_mode(stdout, agent_id, target))
    elif 'Found:' in stdout and ('.' in stdout):
        # DNS or vhost mode
        findings.extend(_parse_dns_mode(stdout, agent_id, target))
    else:
        # Try both parsers
        findings.extend(_parse_dir_mode(stdout, agent_id, target))
        if not findings:
            findings.extend(_parse_dns_mode(stdout, agent_id, target))
    
    return findings


def _parse_dir_mode(stdout: str, agent_id: str, target: str) -> List[Finding]:
    """Parse gobuster dir mode output."""
    findings: List[Finding] = []
    
    # Pattern: /path (Status: 200) [Size: 1234]
    # Or: /path                    (Status: 200) [Size: 1234]
    pattern = re.compile(r'^(/\S+)\s+\(Status:\s*(\d+)\)(?:\s+\[Size:\s*(\d+)\])?', re.MULTILINE)
    
    for match in pattern.finditer(stdout):
        path, status, size = match.groups()
        status = int(status)
        
        # Determine if directory or file
        is_dir = path.endswith('/') or (status in [301, 302] and not '.' in path.split('/')[-1])
        finding_type = "directory" if is_dir else "file"
        
        # Map severity based on status code
        if status == 200:
            severity = "info"
        elif status == 403:
            severity = "low"  # Forbidden might indicate something interesting
        elif status in [301, 302]:
            severity = "info"
        else:
            severity = "info"
        
        evidence = f"[{status}] {path}"
        if size:
            evidence += f" (Size: {size})"
        
        findings.append(common.create_finding(
            type_val=finding_type,
            severity=severity,
            target=target,
            evidence=evidence,
            agent_id=agent_id,
            tool="gobuster"
        ))
    
    return findings


def _parse_dns_mode(stdout: str, agent_id: str, target: str) -> List[Finding]:
    """Parse gobuster dns/vhost mode output."""
    findings: List[Finding] = []
    
    # Pattern: Found: subdomain.example.com
    pattern = re.compile(r'Found:\s+(\S+)', re.IGNORECASE)
    
    for match in pattern.finditer(stdout):
        hostname = match.group(1).strip()
        
        findings.append(common.create_finding(
            type_val="subdomain",
            severity="info",
            target=target,
            evidence=f"Subdomain: {hostname}",
            agent_id=agent_id,
            tool="gobuster"
        ))
    
    return findings
