import json
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common

def ffuf_parser(
    stdout: str,
    stderr: str = "",
    exit_code: int | str = 0,
    agent_id: str = "",
    target: str = "",
    error_type: str | None = None,
) -> List[Finding]:
    """
    Parses ffuf JSON output and returns a list of Findings.
    """
    # Backward compatibility for legacy signature: (stdout, agent_id, target)
    if not agent_id and not target and isinstance(exit_code, str):
        agent_id = stderr
        target = exit_code
        stderr = ""
        exit_code = 0

    findings: List[Finding] = []
    
    try:
        data = json.loads(stdout)
        results = data.get("results", [])
    except json.JSONDecodeError:
        # If not valid JSON, return empty list or handle error
        return []
        
    for result in results:
        # Basic extraction for now to pass Task 3 test
        input_data = result.get("input", {})
        keyword = list(input_data.keys())[0] if input_data else "FUZZ"
        payload = input_data.get(keyword, "")
        
        
        # Determine type
        # For now, just "file" or "directory" based on slash, but mostly just create finding
        # Task 4 will refine this, but we need something for common.create_finding
        url = result.get("url", target)
        if url.endswith("/"):
            finding_type = "directory"
        else:
            finding_type = "file"
        
        # Build evidence
        url = result.get("url", target)
        status = result.get("status", 0)
        size = result.get("length", 0)
        evidence = f"[{status}] {url} (Size: {size})"
        
        finding = common.create_finding(
            type_val=finding_type,
            severity="info",
            target=target,
            evidence=evidence,
            agent_id=agent_id,
            tool="ffuf"
        )
        findings.append(finding)
        
    return findings
