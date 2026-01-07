"""BloodHound/SharpHound output parser for structured finding extraction."""
import json
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def bloodhound_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse BloodHound JSON output and return a list of Findings.
    
    Supports individual JSON files or detection of high-value targets.
    
    Args:
        stdout: Raw BloodHound JSON output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target domain that was scanned
        
    Returns:
        List of Finding objects for AD objects
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Try to parse as JSON
    try:
        data = json.loads(stdout)
        
        # Handle different BloodHound JSON formats
        if isinstance(data, dict):
            # Check for data key (BloodHound v4+ format)
            items = data.get("data", data.get("computers", data.get("users", data.get("groups", []))))
            meta = data.get("meta", {})
            object_type = meta.get("type", "").lower()
            
            if not object_type:
                # Try to infer type from content
                if "users" in data:
                    object_type = "users"
                    items = data["users"]
                elif "computers" in data:
                    object_type = "computers"
                    items = data["computers"]
                elif "groups" in data:
                    object_type = "groups"
                    items = data["groups"]
            
            findings.extend(_parse_bloodhound_items(items, object_type, agent_id, target))
            
        elif isinstance(data, list):
            # Direct list of objects
            for item in data:
                findings.extend(_parse_bloodhound_item(item, agent_id, target))
                
        return findings
    except json.JSONDecodeError:
        pass
    
    # If not JSON, return empty
    return findings


def _parse_bloodhound_items(items: list, object_type: str, agent_id: str, target: str) -> List[Finding]:
    """Parse a list of BloodHound items."""
    findings: List[Finding] = []
    
    for item in items:
        if isinstance(item, dict):
            properties = item.get("Properties", item)
            name = properties.get("name", properties.get("samaccountname", ""))
            
            if not name:
                continue
            
            # Determine severity based on object type and properties
            severity = "info"
            is_high_value = False
            
            # Check for high-value targets
            if object_type in ["groups", "group"]:
                high_value_groups = ["Domain Admins", "Enterprise Admins", "Administrators", "Schema Admins"]
                if any(hv.lower() in name.lower() for hv in high_value_groups):
                    is_high_value = True
                    severity = "high"
            
            if properties.get("highvalue", False) or properties.get("admincount", 0) > 0:
                is_high_value = True
                severity = "high"
            
            evidence = f"AD {object_type.rstrip('s')}: {name}"
            if is_high_value:
                evidence += " [HIGH VALUE]"
            
            findings.append(common.create_finding(
                type_val="ad_object",
                severity=severity,
                target=target,
                evidence=evidence,
                agent_id=agent_id,
                tool="bloodhound"
            ))
    
    return findings


def _parse_bloodhound_item(item: dict, agent_id: str, target: str) -> List[Finding]:
    """Parse a single BloodHound item."""
    findings: List[Finding] = []
    
    properties = item.get("Properties", item)
    name = properties.get("name", properties.get("samaccountname", ""))
    object_type = item.get("ObjectType", properties.get("type", "object"))
    
    if not name:
        return findings
    
    severity = "info"
    if properties.get("highvalue", False) or properties.get("admincount", 0) > 0:
        severity = "high"
    
    evidence = f"AD {object_type}: {name}"
    
    findings.append(common.create_finding(
        type_val="ad_object",
        severity=severity,
        target=target,
        evidence=evidence,
        agent_id=agent_id,
        tool="bloodhound"
    ))
    
    return findings
