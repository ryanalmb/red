"""Wifite output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def wifite_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse wifite output and return a list of Findings.
    
    Handles colored output and extracts attack results.
    
    Args:
        stdout: Raw wifite output (may contain ANSI codes)
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target network
        
    Returns:
        List of Finding objects for WiFi attacks
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Strip ANSI codes
    clean_output = strip_ansi(stdout)
    
    current_target = ""
    
    for line in clean_output.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Track current target
        target_match = re.search(r'Target:\s*(\S+)', line, re.IGNORECASE)
        if target_match:
            current_target = target_match.group(1)
            continue
        
        # BSSID/ESSID detection
        bssid_match = re.search(r'([0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2})', line, re.IGNORECASE)
        essid_match = re.search(r'(?:ESSID|SSID):\s*"?([^"\n]+)"?', line, re.IGNORECASE)
        
        if bssid_match:
            current_target = bssid_match.group(1)
        if essid_match:
            current_target = essid_match.group(1)
        
        # Successful attack patterns
        success_patterns = [
            (r'Cracked:\s*(.+)', "Cracked"),
            (r'(PMKID)\s+captured', "PMKID captured"),
            (r'(Handshake)\s+captured', "Handshake captured"),
            (r'Key:\s*(.+)', "Key found"),
            (r'Password:\s*(.+)', "Password found"),
        ]
        
        for pattern, attack_type in success_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                result = match.group(1).strip()
                
                evidence = f"WiFi attack success: {attack_type}"
                if current_target:
                    evidence += f" on {current_target}"
                evidence += f" - {result}"
                
                severity = "critical" if "key" in attack_type.lower() or "password" in attack_type.lower() or "cracked" in attack_type.lower() else "high"
                
                findings.append(common.create_finding(
                    type_val="wifi_attack",
                    severity=severity,
                    target=target,
                    evidence=evidence,
                    agent_id=agent_id,
                    tool="wifite"
                ))
                break
    
    return findings
