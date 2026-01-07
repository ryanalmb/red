"""LaZagne output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def lazagne_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse LaZagne output and return a list of Findings.
    
    Extracts credentials by application category.
    
    Args:
        stdout: Raw LaZagne output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for harvested credentials
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    current_category = ""
    current_app = ""
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Detect category headers (e.g., [+] Browsers, [+] Wifi)
        category_match = re.match(r'\[\+\]\s*(\w+)', line)
        if category_match:
            current_category = category_match.group(1)
            continue
        
        # Detect application headers (e.g., ------------------- Chrome -------------------)
        app_match = re.search(r'-+\s*(\w+)\s*-+', line)
        if app_match:
            current_app = app_match.group(1)
            continue
        
        # Extract credentials
        # Pattern: Username: xxx / Password: xxx
        cred_match = re.search(r'(?:Username|Login|User)\s*:\s*(\S+)', line, re.IGNORECASE)
        if cred_match:
            username = cred_match.group(1)
            
            # Look for password in same or next line
            pass_match = re.search(r'Password\s*:\s*(\S+)', line, re.IGNORECASE)
            password = pass_match.group(1) if pass_match else ""
            
            if username and password:
                app_context = current_app or current_category or "Unknown"
                
                findings.append(common.create_finding(
                    type_val="credential",
                    severity="critical",
                    target=target,
                    evidence=f"[{app_context}] {username}:{password}",
                    agent_id=agent_id,
                    tool="lazagne"
                ))
            continue
        
        # Also match key-value pairs
        kv_match = re.match(r'(\w+)\s*:\s*(.+)', line)
        if kv_match:
            key, value = kv_match.groups()
            key_lower = key.lower()
            
            if key_lower in ['password', 'pwd', 'secret', 'key'] and value.strip():
                app_context = current_app or current_category or "Unknown"
                
                findings.append(common.create_finding(
                    type_val="credential",
                    severity="critical",
                    target=target,
                    evidence=f"[{app_context}] {key}: {value}",
                    agent_id=agent_id,
                    tool="lazagne"
                ))
    
    return findings
