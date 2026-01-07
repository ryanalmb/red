"""WinPEAS output parser for structured finding extraction."""
import re
from typing import List, Tuple
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def winpeas_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse winpeas output and return a list of Findings.
    
    Handles ANSI colored output and extracts Windows privilege escalation vectors.
    
    Args:
        stdout: Raw winpeas output (may contain ANSI codes)
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for Windows privilege escalation vectors
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Strip ANSI codes for parsing
    clean_output = strip_ansi(stdout)
    
    # Patterns for Windows privilege escalation vectors
    privesc_patterns: List[Tuple[str, str, str]] = [
        # Unquoted service paths
        (r'Unquoted.*?service.*?path', "Unquoted service path", "high"),
        # Weak service permissions
        (r'(SERVICE_ALL_ACCESS|SERVICE_CHANGE_CONFIG)', "Weak service permissions", "high"),
        # Writable service binary paths
        (r'Writable.*?service', "Writable service binary", "high"),
        # AlwaysInstallElevated
        (r'AlwaysInstallElevated', "AlwaysInstallElevated enabled", "critical"),
        # Stored credentials
        (r'(Cached.*?credential|Credential.*?Manager)', "Stored credentials", "high"),
        # AutoLogon credentials
        (r'AutoLogon.*?password', "AutoLogon credentials", "critical"),
        # Registry permissions
        (r'Registry.*?(writable|permissions)', "Registry permissions", "medium"),
        # DLL hijacking
        (r'(DLL\s+hijack|missing\s+dll)', "DLL hijacking", "high"),
        # Token impersonation
        (r'(SeImpersonate|SeAssignPrimaryToken)', "Token impersonation", "high"),
        # UAC bypass
        (r'UAC.*?(bypass|disabled)', "UAC vulnerability", "high"),
    ]
    
    seen_findings = set()
    
    for line in clean_output.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Check for high confidence markers
        is_high_confidence = any(marker in line for marker in ['[!]', '[+]', 'VULNERABLE', 'EXPLOITABLE'])
        
        for pattern, vector_type, base_severity in privesc_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                finding_key = f"{vector_type}:{line[:50]}"
                
                if finding_key in seen_findings:
                    continue
                seen_findings.add(finding_key)
                
                severity = "critical" if is_high_confidence else base_severity
                
                description = line[:200]
                evidence = f"{vector_type}: {description}"
                
                findings.append(common.create_finding(
                    type_val="privesc_vector",
                    severity=severity,
                    target=target,
                    evidence=evidence,
                    agent_id=agent_id,
                    tool="winpeas"
                ))
                break
    
    return findings
