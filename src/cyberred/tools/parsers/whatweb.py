"""WhatWeb output parser for structured finding extraction."""
import json
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def whatweb_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse whatweb output and return a list of Findings.
    
    Supports JSON format (--log-json) and stdout.
    
    Args:
        stdout: Raw whatweb output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target URL that was scanned
        
    Returns:
        List of Finding objects for detected technologies
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Try JSON parsing
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            for entry in data:
                findings.extend(_parse_whatweb_entry(entry, agent_id, target))
        elif isinstance(data, dict):
            findings.extend(_parse_whatweb_entry(data, agent_id, target))
        return findings
    except json.JSONDecodeError:
        pass
    
    # Try JSON lines
    for line in stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            findings.extend(_parse_whatweb_entry(data, agent_id, target))
        except json.JSONDecodeError:
            continue
    
    return findings


def _parse_whatweb_entry(entry: dict, agent_id: str, target: str) -> List[Finding]:
    """Parse a single whatweb JSON entry."""
    findings: List[Finding] = []
    
    url = entry.get("target", target)
    plugins = entry.get("plugins", {})
    
    for tech_name, tech_info in plugins.items():
        if tech_name in ["IP", "Country", "HTTPServer"]:
            # Skip basic info, focus on technologies
            continue
            
        version = ""
        if isinstance(tech_info, dict):
            version_list = tech_info.get("version", [])
            if version_list:
                version = version_list[0] if isinstance(version_list, list) else str(version_list)
        
        evidence = f"Technology: {tech_name}"
        if version:
            evidence += f" v{version}"
        evidence += f" on {url}"
        
        findings.append(common.create_finding(
            type_val="technology",
            severity="info",
            target=target,
            evidence=evidence,
            agent_id=agent_id,
            tool="whatweb"
        ))
    
    return findings
