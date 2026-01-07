"""LinPEAS output parser for structured finding extraction."""
import re
from typing import List, Tuple
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def linpeas_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse linpeas output and return a list of Findings.
    
    Handles ANSI colored output and extracts privilege escalation vectors.
    
    Args:
        stdout: Raw linpeas output (may contain ANSI codes)
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for privilege escalation vectors
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Strip ANSI codes for parsing
    clean_output = strip_ansi(stdout)
    
    # Track current section for context
    current_section = ""
    
    # Patterns for privilege escalation vectors
    privesc_patterns: List[Tuple[str, str, str]] = [
        # SUID binaries
        (r'(SUID|sgid).*?(/\S+)', "SUID/SGID binary", "high"),
        # Capabilities
        (r'(cap_\w+).*?(/\S+)', "Linux capability", "high"),
        # Writable paths
        (r'(Writable|writable).*?(/\S+)', "Writable path", "medium"),
        # Cron jobs
        (r'(\*/\d+|\d+\s+\*|\*\s+\d+).*?(/\S+)', "Cron job", "medium"),
        # Sudo permissions
        (r'\(ALL\s*:\s*ALL\)\s*(NOPASSWD)?', "Sudo permission", "critical"),
        # Docker/LXC
        (r'(docker|lxc).*?socket', "Container socket", "critical"),
        # Kernel exploits
        (r'CVE-\d{4}-\d+', "Potential kernel exploit", "high"),
    ]
    
    seen_findings = set()
    
    for line in clean_output.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Detect section headers (marked with special characters)
        if line.startswith('=') or line.startswith('#') or line.startswith('[+]'):
            current_section = line
            continue
        
        # Check for 95% or 99% indicators (linpeas high confidence markers)
        is_high_confidence = '95%' in line or '99%' in line or 'PE' in line
        
        for pattern, vector_type, base_severity in privesc_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                # Extract relevant info
                finding_key = f"{vector_type}:{match.group(0)[:50]}"
                
                if finding_key in seen_findings:
                    continue
                seen_findings.add(finding_key)
                
                severity = "critical" if is_high_confidence else base_severity
                
                description = line[:200]  # Truncate long lines
                evidence = f"{vector_type}: {description}"
                
                findings.append(common.create_finding(
                    type_val="privesc_vector",
                    severity=severity,
                    target=target,
                    evidence=evidence,
                    agent_id=agent_id,
                    tool="linpeas"
                ))
                break
    
    return findings
