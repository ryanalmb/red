"""Amass output parser for structured finding extraction."""
import json
from typing import List, Set
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def amass_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse amass output and return a list of Findings.
    
    Supports JSON format and plain stdout.
    
    Args:
        stdout: Raw amass output
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
    
    lines = stdout.strip().split('\n')
    
    # Try JSON lines parsing
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        try:
            data = json.loads(line)
            host = data.get("name", data.get("host", "")).strip()
            source = data.get("source", data.get("tag", ""))
            addresses = data.get("addresses", [])
            
            if host and host not in seen_hosts:
                seen_hosts.add(host)
                evidence = f"Subdomain: {host}"
                if source:
                    evidence += f" (source: {source})"
                if addresses:
                    # Extract DNS records
                    dns_info = []
                    for addr in addresses:
                        if isinstance(addr, dict):
                            ip = addr.get("ip", "")
                            if ip:
                                dns_info.append(ip)
                        elif isinstance(addr, str):
                            dns_info.append(addr)
                    if dns_info:
                        evidence += f" DNS: {', '.join(dns_info[:3])}"
                    
                findings.append(common.create_finding(
                    type_val="subdomain",
                    severity="info",
                    target=target,
                    evidence=evidence,
                    agent_id=agent_id,
                    tool="amass"
                ))
        except json.JSONDecodeError:
            # Plain text line - treat as hostname
            host = line.strip()
            if host and host not in seen_hosts and '.' in host:
                seen_hosts.add(host)
                findings.append(common.create_finding(
                    type_val="subdomain",
                    severity="info",
                    target=target,
                    evidence=f"Subdomain: {host}",
                    agent_id=agent_id,
                    tool="amass"
                ))
    
    return findings
