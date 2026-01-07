"""DNSrecon output parser for structured finding extraction."""
import json
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def dnsrecon_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse dnsrecon output and return a list of Findings.
    
    Supports JSON format (-j) and stdout format.
    
    Args:
        stdout: Raw dnsrecon output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target domain that was scanned
        
    Returns:
        List of Finding objects for DNS records
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Try JSON parsing
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            for record in data:
                record_type = record.get("type", "")
                name = record.get("name", record.get("hostname", ""))
                value = record.get("address", record.get("target", record.get("data", "")))
                
                if record_type and (name or value):
                    severity = "high" if record_type.upper() == "AXFR" else "info"
                    evidence = f"DNS {record_type}: {name}"
                    if value:
                        evidence += f" -> {value}"
                    
                    findings.append(common.create_finding(
                        type_val="dns_record",
                        severity=severity,
                        target=target,
                        evidence=evidence,
                        agent_id=agent_id,
                        tool="dnsrecon"
                    ))
        return findings
    except json.JSONDecodeError:
        pass
    
    # Parse stdout format
    # Pattern for common DNS record formats in dnsrecon output
    patterns = [
        # A record: [*] A example.com 192.168.1.1
        re.compile(r'\[\*\]\s+(\w+)\s+(\S+)\s+(\S+)'),
        # Zone transfer indicator
        re.compile(r'Zone Transfer', re.IGNORECASE),
    ]
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Check for zone transfer (high severity)
        if 'zone transfer' in line.lower():
            findings.append(common.create_finding(
                type_val="dns_record",
                severity="high",
                target=target,
                evidence=f"Zone Transfer detected: {line}",
                agent_id=agent_id,
                tool="dnsrecon"
            ))
            continue
            
        match = patterns[0].match(line)
        if match:
            record_type, name, value = match.groups()
            findings.append(common.create_finding(
                type_val="dns_record",
                severity="info",
                target=target,
                evidence=f"DNS {record_type}: {name} -> {value}",
                agent_id=agent_id,
                tool="dnsrecon"
            ))
    
    return findings
