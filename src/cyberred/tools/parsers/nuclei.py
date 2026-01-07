import json
import re
from typing import List

import structlog

from cyberred.core.models import Finding
from cyberred.tools.parsers.common import create_finding

log = structlog.get_logger()

# Pattern for matching CVE IDs (e.g., CVE-2021-44228)
CVE_PATTERN = re.compile(r"CVE-\d{4}-\d+", re.IGNORECASE)

def nuclei_parser(
    stdout: str, 
    stderr: str, 
    exit_code: int, 
    agent_id: str, 
    target: str
) -> List[Finding]:
    """Parse nuclei JSON or plain text output to structured findings.
    
    Args:
        stdout: Nuclei output (JSON from -j or plain text)
        stderr: Nuclei stderr (usually status messages)
        exit_code: Process exit code
        agent_id: UUID of agent running the tool
        target: Target IP/hostname
        
    Returns:
        List of Finding objects for each template match
    """
    findings: List[Finding] = []
    
    if not stdout.strip():
        return findings
        
    if _is_json_format(stdout):
        return _parse_json(stdout, agent_id, target)
    else:
        return _parse_plain_text(stdout, agent_id, target)


def _is_json_format(stdout: str) -> bool:
    """Check if output is nuclei JSON format."""
    first_line = stdout.strip().split('\n')[0]
    return first_line.startswith('{') and first_line.endswith('}')


def _parse_json(stdout: str, agent_id: str, target: str) -> List[Finding]:
    """Parse JSON Lines format output."""
    findings: List[Finding] = []
    
    for line in stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
            
        try:
            # Task 2: Basic JSON parsing
            data = json.loads(line)
        except json.JSONDecodeError:
            log.warning("nuclei_json_parse_failed", line=line[:100])
            continue
            
        # Task 3: Extract template ID and severity
        template_id = data.get('template-id', 'unknown')
        info = data.get('info', {})
        severity = info.get('severity', 'info').lower()
        if severity == "unknown":
            severity = "info"
            
        # Task 4: Extract CVE information
        cve_id = ""
        classification = info.get('classification', {})
        if classification:
            cve_id = str(classification.get('cve-id', '') or '')
            
        if not cve_id:
            metadata = info.get('metadata', {})
            cve_id = str(metadata.get('cve-id', '') or '')
            
        # Task 6: Classify finding type
        tags = info.get('tags', [])
        finding_type = _classify_finding_type(cve_id, tags)
        
        # Task 8: Extract CVSS
        cvss_score = ""
        if classification:
            cvss = classification.get('cvss-score')
            if cvss is not None:
                cvss_score = str(cvss)
            
        matched_at = data.get('matched-at', target)
        
        # Build evidence
        evidence_parts = [f"Template: {template_id}"]
        if cve_id:
            evidence_parts.append(f"CVE: {cve_id}")
        if cvss_score:
            evidence_parts.append(f"CVSS: {cvss_score}")
            
        evidence_parts.append(f"URL: {matched_at}")
        
        extracted = data.get('extracted-results', [])
        if extracted:
            evidence_parts.append(f"Extracted: {', '.join(extracted)}")
            
        evidence = " | ".join(evidence_parts)
        
        findings.append(create_finding(
            type_val=finding_type,
            severity=severity,
            target=target,
            evidence=evidence,
            agent_id=agent_id,
            tool="nuclei"
        ))
            
    return findings


def _parse_plain_text(stdout: str, agent_id: str, target: str) -> List[Finding]:
    """Parse plain text output format."""
    findings: List[Finding] = []
    # [timestamp] [template-id] [protocol] [severity] url [extra]
    regex = re.compile(r"^\[(.*?)\] \[(.*?)\] \[(.*?)\] \[(.*?)\] (\S+)(?: \[(.*)\])?")
    
    for line in stdout.strip().split('\n'):
        match = regex.match(line.strip())
        if not match:
            continue
            
        timestamp, template_id, protocol, severity, url, extra = match.groups()
        
        evidence = f"Template: {template_id} | URL: {url}"
        if extra:
             evidence += f" | Extracted: {extra}"
             
        # Use regex for more accurate CVE detection in plain text
        finding_type = "cve" if CVE_PATTERN.search(template_id) else "vulnerability"
             
        findings.append(create_finding(
            type_val=finding_type,
            severity=severity.lower(),
            target=target,
            evidence=evidence,
            agent_id=agent_id,
            tool="nuclei"
        ))
    
    log.info("nuclei_parsed", target=target, findings_count=len(findings), format="plain_text")
    return findings


def _classify_finding_type(cve_id: str, tags: List[str]) -> str:
    """Classify finding type based on CVE presence and tags."""
    if cve_id:
        return "cve"
    
    # Check tags for classification
    tag_set = set(t.lower() for t in tags)
    
    if 'exposure' in tag_set or 'exposed' in tag_set:
        return "exposure"
    if 'misconfig' in tag_set or 'misconfiguration' in tag_set:
        return "misconfiguration"
    
    # Default to vulnerability for other security findings
    return "vulnerability"



