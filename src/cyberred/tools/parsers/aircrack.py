"""Aircrack-ng output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def aircrack_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse aircrack-ng output and return a list of Findings.
    
    Detects successful key cracks for WEP and WPA/WPA2.
    
    Args:
        stdout: Raw aircrack-ng output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target BSSID/network
        
    Returns:
        List of Finding objects for cracked WiFi keys
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Look for KEY FOUND message
    # Pattern: KEY FOUND! [ XX:XX:XX:XX:XX ] (ASCII: password123)
    # Or: KEY FOUND! [ password123 ]
    key_patterns = [
        re.compile(r'KEY FOUND!\s*\[\s*([^\]]+)\s*\](?:\s*\(ASCII:\s*([^)]+)\))?', re.IGNORECASE),
        re.compile(r'Passphrase:\s*"?([^"\n]+)"?', re.IGNORECASE),
    ]
    
    bssid = ""
    essid = ""
    packets = 0
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Extract network info
        bssid_match = re.search(r'([0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2})', line, re.IGNORECASE)
        if bssid_match:
            bssid = bssid_match.group(1)
        
        essid_match = re.search(r'ESSID:\s*"?([^"\n]+)"?', line, re.IGNORECASE)
        if essid_match:
            essid = essid_match.group(1)
        
        # Extract packet count
        packets_match = re.search(r'(\d+)\s+(?:packets|IVs)', line, re.IGNORECASE)
        if packets_match:
            try:
                packets = int(packets_match.group(1))
            except ValueError:
                pass
        
        # Check for key found
        for pattern in key_patterns:
            match = pattern.search(line)
            if match:
                key = match.group(1).strip()
                ascii_key = match.group(2).strip() if match.lastindex >= 2 and match.group(2) else ""
                
                if ascii_key:
                    key = ascii_key
                
                evidence = f"WiFi key cracked: {essid or bssid or target}"
                if bssid:
                    evidence += f" ({bssid})"
                evidence += f" - Key: {key}"
                if packets > 0:
                    evidence += f" [{packets} packets]"
                
                findings.append(common.create_finding(
                    type_val="wifi_crack",
                    severity="critical",
                    target=target,  # Use the provided target (must be valid IP/hostname)
                    evidence=evidence,
                    agent_id=agent_id,
                    tool="aircrack"
                ))
                break
    
    return findings
