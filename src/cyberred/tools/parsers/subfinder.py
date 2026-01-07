"""Subfinder output parser for structured finding extraction."""
import json
from typing import List, Set
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def subfinder_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse subfinder output and return a list of Findings.
    
    Supports both JSON lines format (-oJ) and plain stdout (one hostname per line).
    Automatically deduplicates findings.
    
    Args:
        stdout: Raw subfinder output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target domain that was scanned
        
    Returns:
        List of Finding objects for discovered subdomains
    """
    findings: List[Finding] = []
    seen_hosts: Set[str] = set()
    
    if not stdout or not stdout.strip():
        return findings
    
    # Try JSON lines parsing first
    lines = stdout.strip().split('\n')
    json_parsed = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        try:
            data = json.loads(line)
            host = data.get("host", "").strip()
            source = data.get("source", "")
            
            if host and host not in seen_hosts:
                seen_hosts.add(host)
                evidence = f"Subdomain: {host}"
                if source:
                    evidence += f" (source: {source})"
                    
                findings.append(common.create_finding(
                    type_val="subdomain",
                    severity="info",
                    target=target,
                    evidence=evidence,
                    agent_id=agent_id,
                    tool="subfinder"
                ))
            json_parsed = True
        except json.JSONDecodeError:
            continue
    
    # If JSON parsing found results, return them
    if json_parsed and findings:
        return findings
    
    # Fall back to plain text parsing (one hostname per line)
    seen_hosts.clear()
    findings.clear()
    
    for line in lines:
        host = line.strip()
        if host and host not in seen_hosts and '.' in host:
            seen_hosts.add(host)
            findings.append(common.create_finding(
                type_val="subdomain",
                severity="info",
                target=target,
                evidence=f"Subdomain: {host}",
                agent_id=agent_id,
                tool="subfinder"
            ))
    
    return findings
