"""Hashcat output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def hashcat_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse hashcat output and return a list of Findings.
    
    Extracts cracked passwords from output and potfile format.
    
    Args:
        stdout: Raw hashcat output or potfile content
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target (hash file or description)
        
    Returns:
        List of Finding objects for cracked hashes
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    mode = ""
    speed = ""
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Extract mode info
        mode_match = re.search(r'Hash\.Mode\.+:\s*(\d+)', line)
        if mode_match:
            mode = mode_match.group(1)
            continue
        
        # Extract speed
        speed_match = re.search(r'Speed\.#\d+\.+:\s*(.+)', line)
        if speed_match:
            speed = speed_match.group(1)
            continue
        
        # Potfile format: hash:plaintext
        # or hash:salt:plaintext for salted hashes
        potfile_match = re.match(r'^([^:]+(?::[^:]+)?):(.+)$', line)
        if potfile_match:
            hash_part, plaintext = potfile_match.groups()
            
            # Skip status/info lines
            if any(skip in line.lower() for skip in ['session', 'status', 'speed', 'recovered', 'progress']):
                continue
            
            # Skip empty passwords
            if not plaintext:
                continue
            
            # Truncate long hashes for readability
            display_hash = hash_part[:32] + "..." if len(hash_part) > 32 else hash_part
            
            evidence = f"Hash cracked: {display_hash} -> {plaintext}"
            if mode:
                evidence += f" [mode:{mode}]"
            
            findings.append(common.create_finding(
                type_val="cracked_hash",
                severity="critical",
                target=target,
                evidence=evidence,
                agent_id=agent_id,
                tool="hashcat"
            ))
            continue
        
        # Real-time crack notification
        # Pattern: [hash] -> plaintext
        realtime_match = re.search(r'([a-f0-9]{16,})\s*:\s*(.+)', line, re.IGNORECASE)
        if realtime_match:
            hash_val, plaintext = realtime_match.groups()
            
            display_hash = hash_val[:32] + "..." if len(hash_val) > 32 else hash_val
            
            findings.append(common.create_finding(
                type_val="cracked_hash",
                severity="critical",
                target=target,
                evidence=f"Hash cracked: {display_hash} -> {plaintext}",
                agent_id=agent_id,
                tool="hashcat"
            ))
    
    return findings
