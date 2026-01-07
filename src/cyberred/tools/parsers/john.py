"""John the Ripper output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def john_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse John the Ripper output and return a list of Findings.
    
    Extracts cracked passwords from --show output and status messages.
    
    Args:
        stdout: Raw John output
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
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Skip info/status lines
        if line.startswith('Loaded') or line.startswith('Using') or line.startswith('Press'):
            continue
        
        # Pattern for --show output: username:password
        # or hash:password
        show_match = re.match(r'^([^:]+):(.+)$', line)
        if show_match:
            username_or_hash, plaintext = show_match.groups()
            
            # Skip empty or null passwords
            if not plaintext or plaintext == '*':
                continue
            
            # Detect if it's a hash or username
            is_hash = len(username_or_hash) >= 32 and re.match(r'^[a-f0-9]+$', username_or_hash, re.IGNORECASE)
            
            if is_hash:
                evidence = f"Hash cracked: {username_or_hash[:16]}... -> {plaintext}"
            else:
                evidence = f"Password cracked: {username_or_hash} -> {plaintext}"
            
            findings.append(common.create_finding(
                type_val="cracked_hash",
                severity="critical",
                target=target,
                evidence=evidence,
                agent_id=agent_id,
                tool="john"
            ))
            continue
        
        # Pattern for real-time cracking: user (hash) -> password
        realtime_match = re.search(r'(\S+)\s+\([^)]+\)\s*->\s*(.+)', line)
        if realtime_match:
            username, plaintext = realtime_match.groups()
            
            findings.append(common.create_finding(
                type_val="cracked_hash",
                severity="critical",
                target=target,
                evidence=f"Password cracked: {username} -> {plaintext}",
                agent_id=agent_id,
                tool="john"
            ))
    
    return findings
