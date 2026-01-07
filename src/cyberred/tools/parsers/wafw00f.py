"""Wafw00f output parser for structured finding extraction."""
import json
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def wafw00f_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse wafw00f output and return a list of Findings.
    
    Supports JSON format (-o) and stdout format.
    
    Args:
        stdout: Raw wafw00f output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target URL that was scanned
        
    Returns:
        List of Finding objects for WAF detections
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Try JSON parsing
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            for entry in data:
                url = entry.get("url", target)
                waf = entry.get("firewall", entry.get("waf", ""))
                detected = entry.get("detected", False)
                
                if detected and waf:
                    findings.append(common.create_finding(
                        type_val="waf_detected",
                        severity="info",
                        target=target,
                        evidence=f"WAF Detected: {waf} on {url}",
                        agent_id=agent_id,
                        tool="wafw00f"
                    ))
        return findings
    except json.JSONDecodeError:
        pass
    
    # Parse stdout format
    # Pattern: "is behind [WAF NAME] WAF"
    waf_pattern = re.compile(r'is behind (.+?) WAF', re.IGNORECASE)
    
    for match in waf_pattern.finditer(stdout):
        waf_name = match.group(1).strip()
        findings.append(common.create_finding(
            type_val="waf_detected",
            severity="info",
            target=target,
            evidence=f"WAF Detected: {waf_name}",
            agent_id=agent_id,
            tool="wafw00f"
        ))
    
    # Check for "No WAF detected" message
    if not findings and "no waf" in stdout.lower():
        # No finding to report for no WAF
        pass
    
    return findings
