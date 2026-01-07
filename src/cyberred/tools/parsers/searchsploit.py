"""Searchsploit output parser for structured finding extraction."""
import json
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def searchsploit_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse searchsploit output and return a list of Findings.
    
    Supports JSON format (-j) and stdout format.
    
    Args:
        stdout: Raw searchsploit output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The search term used
        
    Returns:
        List of Finding objects for exploit references
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Try JSON parsing first
    try:
        data = json.loads(stdout)
        exploits = data.get("RESULTS_EXPLOIT", [])
        
        for exploit in exploits:
            edb_id = exploit.get("EDB-ID", "")
            title = exploit.get("Title", "")
            path = exploit.get("Path", "")
            platform = exploit.get("Platform", "")
            
            evidence = f"EDB-{edb_id}: {title}"
            if platform:
                evidence += f" [{platform}]"
            
            findings.append(common.create_finding(
                type_val="exploit_ref",
                severity="info",
                target=target,
                evidence=evidence,
                agent_id=agent_id,
                tool="searchsploit"
            ))
        
        return findings
    except json.JSONDecodeError:
        pass
    
    # Parse stdout format
    # Pattern: Exploit Title | Path
    # Skip header lines
    in_results = False
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Detect results section
        if '---' in line and 'Exploit Title' not in line:
            in_results = True
            continue
        
        if not in_results:
            continue
        
        # Parse result line
        # Format: Title | exploits/platform/xxxxx.xx
        parts = line.split('|')
        if len(parts) >= 2:
            title = parts[0].strip()
            path = parts[1].strip()
            
            # Extract platform from path
            platform = ""
            path_match = re.search(r'exploits/(\w+)/', path)
            if path_match:
                platform = path_match.group(1)
            
            # Extract EDB ID from path
            edb_match = re.search(r'(\d+)\.\w+$', path)
            edb_id = edb_match.group(1) if edb_match else ""
            
            evidence = f"EDB-{edb_id}: {title}" if edb_id else title
            if platform:
                evidence += f" [{platform}]"
            
            findings.append(common.create_finding(
                type_val="exploit_ref",
                severity="info",
                target=target,
                evidence=evidence,
                agent_id=agent_id,
                tool="searchsploit"
            ))
    
    return findings
