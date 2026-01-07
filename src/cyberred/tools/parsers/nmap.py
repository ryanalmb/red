import structlog
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers.common import create_finding

log = structlog.get_logger()

def nmap_parser(
    stdout: str, 
    stderr: str, 
    exit_code: int, 
    agent_id: str, 
    target: str
) -> List[Finding]:
    """Parse nmap XML or grepable output to structured findings.
    
    Auto-detects format: tries XML first, falls back to grepable (-oG).
    
    Args:
        stdout: Nmap output (XML from -oX or grepable from -oG)
        stderr: Nmap stderr (usually empty)
        exit_code: Process exit code
        agent_id: UUID of agent running the tool
        target: Target IP/hostname
        
    Returns:
        List of Finding objects for open ports, host status, OS, scripts
    """
    findings: List[Finding] = []
    
    # Auto-detect format and parse
    if _is_grepable_format(stdout):
        return _parse_grepable(stdout, agent_id, target)
    
    # Try XML parsing
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(stdout)
    except ET.ParseError:
        log.warning("nmap_xml_parse_failed", target=target)
        return []
    
    # Parse each host
    for host in root.findall('host'):
        # Extract host address (override target if found)
        addr_elem = host.find('address')
        host_addr = addr_elem.get('addr', target) if addr_elem is not None else target
        
        # Host status finding
        status_elem = host.find('status')
        if status_elem is not None:
            state = status_elem.get('state', 'unknown')
            findings.append(create_finding(
                type_val="host_status",
                severity="info",
                target=host_addr,
                evidence=f"Host is {state}",
                agent_id=agent_id,
                tool="nmap"
            ))
            
        # OS detection finding
        os_elem = host.find('os')
        if os_elem is not None:
             match = os_elem.find('osmatch')
             if match is not None:
                 name = match.get('name', 'unknown')
                 accuracy = match.get('accuracy', '')
                 evidence = f"OS Match: {name}"
                 if accuracy:
                     evidence += f" ({accuracy}%)"
                 
                 findings.append(create_finding(
                     type_val="os_detection",
                     severity="info",
                     target=host_addr,
                     evidence=evidence,
                     agent_id=agent_id,
                     tool="nmap"
                 ))
                 
        # Host Script findings
        # Direct script children (rare/older nmap)
        for script in host.findall('script'):
            _create_script_finding(script, host_addr, agent_id, findings)
            
        # Hostscript children (standard nmap)
        for script in host.findall('hostscript/script'):
            _create_script_finding(script, host_addr, agent_id, findings)
        
        # Port findings
        for port in host.findall('.//port'):
            state_elem = port.find('state')
            if state_elem is None or state_elem.get('state') != 'open':
                continue
                
            portid = port.get('portid', '')
            protocol = port.get('protocol', 'tcp')
            
            service_elem = port.find('service')
            service = service_elem.get('name', '') if service_elem is not None else ''
            product = service_elem.get('product', '') if service_elem is not None else ''
            version = service_elem.get('version', '') if service_elem is not None else ''
            
            evidence = f"{portid}/{protocol} open {service}"
            if product:
                evidence += f" {product}"
            if version:
                evidence += f" {version}"
                
            # Clean up extra spaces
            evidence = evidence.strip()
            
            findings.append(create_finding(
                type_val="open_port",
                severity="info",
                target=host_addr,
                evidence=evidence,
                agent_id=agent_id,
                tool="nmap"
            ))
            
            # Port Script findings
            for script in port.findall('script'):
                _create_script_finding(script, host_addr, agent_id, findings)
            
    log.info("nmap_parsed", target=target, findings_count=len(findings))
    return findings





def _create_script_finding(
    script_elem,
    target: str,
    agent_id: str,
    findings: List[Finding]
) -> None:
    """Helper to extract script info and create finding."""
    script_id = script_elem.get('id', 'unknown')
    output = script_elem.get('output', '')
    evidence = f"Script: {script_id}\nOutput: {output}"
    
    findings.append(create_finding(
        type_val="nse_script",
        severity="info",
        target=target,
        evidence=evidence,
        agent_id=agent_id,
        tool="nmap"
    ))


def _is_grepable_format(stdout: str) -> bool:
    """Check if output is nmap grepable format (-oG).
    
    Grepable format starts with '# Nmap' and contains 'Host:' lines.
    """
    if not stdout:
        return False
    lines = stdout.strip().split('\n')
    # Check for grepable signature: starts with '# Nmap' and has Host: lines
    has_nmap_header = any(line.startswith('# Nmap') for line in lines[:3])
    has_host_line = any(line.startswith('Host:') for line in lines)
    return has_nmap_header and has_host_line


def _parse_grepable(stdout: str, agent_id: str, target: str) -> List[Finding]:
    """Parse nmap grepable (-oG) format output.
    
    Format:
    # Nmap 7.94 scan initiated ...
    Host: 192.168.1.1 ()	Status: Up
    Host: 192.168.1.1 ()	Ports: 22/open/tcp//ssh//OpenSSH 8.9/, 80/open/tcp//http//
    # Nmap done at ...
    """
    findings: List[Finding] = []
    
    for line in stdout.strip().split('\n'):
        if not line.startswith('Host:'):
            continue
            
        # Extract host IP
        host_match = re.match(r'Host:\s+(\S+)', line)
        if not host_match:
            continue
        host_addr = host_match.group(1)
        
        # Check for Status line
        if 'Status:' in line:
            status_match = re.search(r'Status:\s+(\S+)', line)
            if status_match:
                state = status_match.group(1).lower()
                findings.append(create_finding(
                    type_val="host_status",
                    severity="info",
                    target=host_addr,
                    evidence=f"Host is {state}",
                    agent_id=agent_id,
                    tool="nmap"
                ))
        
        # Check for Ports line
        if 'Ports:' in line:
            ports_match = re.search(r'Ports:\s*(.+?)(?:\t|$)', line)
            if ports_match:
                ports_str = ports_match.group(1)
                # Parse each port: portid/state/proto/owner/service/rpcinfo/version/
                for port_entry in ports_str.split(','):
                    port_entry = port_entry.strip()
                    if not port_entry:
                        continue
                    # Format: port/state/proto/owner/service/rpcinfo/version/
                    parts = port_entry.split('/')
                    if len(parts) < 3:
                        continue
                    
                    portid = parts[0].strip()
                    state = parts[1].strip()
                    proto = parts[2].strip()
                    service = parts[4].strip() if len(parts) > 4 else ''
                    version = parts[6].strip() if len(parts) > 6 else ''
                    
                    if state != 'open':
                        continue
                    
                    evidence = f"{portid}/{proto} open {service}"
                    if version:
                        evidence += f" {version}"
                    evidence = evidence.strip()
                    
                    findings.append(create_finding(
                        type_val="open_port",
                        severity="info",
                        target=host_addr,
                        evidence=evidence,
                        agent_id=agent_id,
                        tool="nmap"
                    ))
    
    log.info("nmap_grepable_parsed", target=target, findings_count=len(findings))
    return findings

