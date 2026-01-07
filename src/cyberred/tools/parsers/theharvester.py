"""TheHarvester output parser for structured finding extraction."""
import re
import xml.etree.ElementTree as ET
from typing import List, Set
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def theharvester_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse theHarvester output and return a list of Findings.
    
    Supports XML format and stdout format.
    
    Args:
        stdout: Raw theHarvester output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target domain that was scanned
        
    Returns:
        List of Finding objects for emails and subdomains
    """
    findings: List[Finding] = []
    seen_items: Set[str] = set()
    
    if not stdout or not stdout.strip():
        return findings
    
    # Try XML parsing
    try:
        root = ET.fromstring(stdout)
        
        # Parse emails
        for email_elem in root.findall('.//email'):
            email = email_elem.text
            if email and email not in seen_items:
                seen_items.add(email)
                findings.append(common.create_finding(
                    type_val="email",
                    severity="info",
                    target=target,
                    evidence=f"Email: {email}",
                    agent_id=agent_id,
                    tool="theharvester"
                ))
        
        # Parse hosts/subdomains
        for host_elem in root.findall('.//host'):
            host = host_elem.text
            if host and host not in seen_items:
                seen_items.add(host)
                findings.append(common.create_finding(
                    type_val="subdomain",
                    severity="info",
                    target=target,
                    evidence=f"Subdomain: {host}",
                    agent_id=agent_id,
                    tool="theharvester"
                ))
                
        return findings
    except ET.ParseError:
        pass
    
    # Parse stdout format
    # Email pattern
    email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    
    # Common section headers in theHarvester output
    in_emails_section = False
    in_hosts_section = False
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Detect section headers
        if 'emails' in line.lower() and ':' in line:
            in_emails_section = True
            in_hosts_section = False
            continue
        elif 'hosts' in line.lower() and ':' in line:
            in_hosts_section = True
            in_emails_section = False
            continue
        elif line.startswith('[') or line.startswith('*'):
            in_emails_section = False
            in_hosts_section = False
        
        # Extract emails
        for email in email_pattern.findall(line):
            if email not in seen_items:
                seen_items.add(email)
                findings.append(common.create_finding(
                    type_val="email",
                    severity="info",
                    target=target,
                    evidence=f"Email: {email}",
                    agent_id=agent_id,
                    tool="theharvester"
                ))
        
        # Extract hosts (if in hosts section or looks like a domain)
        if in_hosts_section or (target in line and '.' in line):
            # Try to extract hostname
            host_match = re.search(r'([\w\.-]+\.' + re.escape(target.split('.')[-2] if '.' in target else target) + r'[\w\.]*)', line, re.IGNORECASE)
            if host_match:
                host = host_match.group(1)
                if host not in seen_items and '@' not in host:
                    seen_items.add(host)
                    findings.append(common.create_finding(
                        type_val="subdomain",
                        severity="info",
                        target=target,
                        evidence=f"Subdomain: {host}",
                        agent_id=agent_id,
                        tool="theharvester"
                    ))
    
    return findings
