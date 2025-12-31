"""
Nmap Adapter - Network scanner and port enumerator.

Nmap is the de facto standard for network discovery and 
security auditing. Supports host discovery, port scanning,
service detection, and OS fingerprinting.
"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Any
from cyberred.mcp.base_adapter import BaseToolAdapter, ToolResult


class NmapAdapter(BaseToolAdapter):
    """
    Adapter for Nmap network scanner.
    
    Supports: Host discovery, port scanning, service detection,
    version detection, script scanning, and OS fingerprinting.
    """
    
    @property
    def tool_name(self) -> str:
        return "nmap"
    
    @property
    def tool_description(self) -> str:
        return "Network exploration and security auditing tool"
    
    def build_command(self, target: str,
                      ports: str = "--top-ports 100",
                      scan_type: str = "-sV",
                      scripts: bool = False,
                      timing: int = 5,
                      os_detect: bool = False,
                      aggressive: bool = False,
                      xml_output: bool = True) -> str:
        """
        Build nmap command.
        
        Args:
            target: Target IP, hostname, or CIDR range
            ports: Port specification (e.g., "1-1000", "22,80,443")
            scan_type: Scan type (-sS, -sT, -sV, -sU, etc.)
            scripts: Run default scripts (-sC)
            timing: Timing template (0-5, higher = faster)
            os_detect: Enable OS detection (-O)
            aggressive: Aggressive mode (-A)
            xml_output: Output in XML format for parsing
        """
        cmd = f"nmap {scan_type}"
        
        if ports:
            # --top-ports is its own flag, numeric ranges need -p
            if ports.startswith("--"):
                cmd += f" {ports}"
            else:
                cmd += f" -p {ports}"

        
        if scripts and "-sC" not in scan_type:
            cmd += " -sC"
        
        cmd += f" -T{timing}"
        
        if os_detect:
            cmd += " -O"
        
        if aggressive:
            cmd += " -A"
        
        if xml_output:
            cmd += " -oX -"  # XML output to stdout
        
        cmd += f" {target}"
        
        return cmd
    
    def parse_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse nmap XML output into structured data."""
        result = {
            "hosts": [],
            "total_hosts": 0,
            "ports_scanned": 0
        }
        
        try:
            root = ET.fromstring(raw_output)
            
            # Get scan info
            scan_info = root.find('scaninfo')
            if scan_info is not None:
                result["ports_scanned"] = scan_info.get('numservices', '0')
            
            # Parse each host
            for host_elem in root.findall('host'):
                host_data = self._parse_host(host_elem)
                if host_data:
                    result["hosts"].append(host_data)
            
            result["total_hosts"] = len(result["hosts"])
            
        except ET.ParseError as e:
            self.logger.error(f"XML Parse Error: {e}")
        except Exception as e:
            self.logger.error(f"Parse Error: {e}")
        
        return result
    
    def _parse_host(self, host_elem) -> Dict[str, Any]:
        """Parse a single host element."""
        host_data = {
            "ip": None,
            "hostname": None,
            "status": None,
            "ports": [],
            "os": None
        }
        
        # Get IP address
        address = host_elem.find('address')
        if address is not None:
            host_data["ip"] = address.get('addr')
        
        # Get hostname
        hostnames = host_elem.find('hostnames')
        if hostnames is not None:
            hostname = hostnames.find('hostname')
            if hostname is not None:
                host_data["hostname"] = hostname.get('name')
        
        # Get status
        status = host_elem.find('status')
        if status is not None:
            host_data["status"] = status.get('state')
        
        # Get ports
        ports_elem = host_elem.find('ports')
        if ports_elem is not None:
            for port_elem in ports_elem.findall('port'):
                port_data = self._parse_port(port_elem)
                if port_data:
                    host_data["ports"].append(port_data)
        
        # Get OS
        os_elem = host_elem.find('os')
        if os_elem is not None:
            osmatch = os_elem.find('osmatch')
            if osmatch is not None:
                host_data["os"] = {
                    "name": osmatch.get('name'),
                    "accuracy": osmatch.get('accuracy')
                }
        
        return host_data
    
    def _parse_port(self, port_elem) -> Dict[str, Any]:
        """Parse a single port element."""
        state_elem = port_elem.find('state')
        if state_elem is None or state_elem.get('state') != 'open':
            return None
        
        port_data = {
            "port": int(port_elem.get('portid')),
            "protocol": port_elem.get('protocol'),
            "state": state_elem.get('state'),
            "service": None,
            "version": None,
            "scripts": []
        }
        
        # Get service info
        service_elem = port_elem.find('service')
        if service_elem is not None:
            port_data["service"] = service_elem.get('name')
            port_data["version"] = service_elem.get('version')
            port_data["product"] = service_elem.get('product')
        
        # Get script output
        for script_elem in port_elem.findall('script'):
            port_data["scripts"].append({
                "id": script_elem.get('id'),
                "output": script_elem.get('output')
            })
        
        return port_data
    
    def extract_findings(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract port and service findings from nmap scan."""
        findings = []
        
        for host in parsed_data.get("hosts", []):
            host_ip = host.get("ip", "unknown")
            
            # Add port findings
            for port in host.get("ports", []):
                findings.append({
                    "type": "port_scan",
                    "severity": "info",
                    "name": f"Open Port: {port['port']}/{port['protocol']}",
                    "description": f"{port.get('service', 'unknown')} on {host_ip}:{port['port']}",
                    "host": host_ip,
                    "port": port["port"],
                    "protocol": port["protocol"],
                    "service": port.get("service"),
                    "version": port.get("version"),
                    "ports": [port]  # For compatibility with kill chain
                })
                
                # Flag high-risk services
                high_risk = ["telnet", "ftp", "rsh", "rlogin", "vnc", "rdp", "ms-sql", "mysql", "mongodb"]
                if port.get("service", "").lower() in high_risk:
                    findings.append({
                        "type": "high_risk_service",
                        "severity": "medium",
                        "name": f"High-Risk Service: {port['service']}",
                        "description": f"{port['service']} on {host_ip}:{port['port']} may be vulnerable",
                        "host": host_ip,
                        "port": port["port"]
                    })
            
            # Add OS finding if detected
            if host.get("os"):
                findings.append({
                    "type": "os_detection",
                    "severity": "info",
                    "name": "OS Detected",
                    "description": f"{host['os']['name']} (accuracy: {host['os']['accuracy']}%)",
                    "host": host_ip
                })
        
        return findings
    
    async def quick_scan(self, target: str) -> ToolResult:
        """Quick top 100 ports scan."""
        return await self.execute(
            target,
            ports="--top-ports 100",
            scripts=False,
            timing=5
        )
    
    async def comprehensive_scan(self, target: str) -> ToolResult:
        """Full port scan with scripts and OS detection."""
        return await self.execute(
            target,
            ports="1-65535",
            scripts=True,
            timing=4,
            os_detect=True
        )
    
    async def service_scan(self, target: str, ports: str = None) -> ToolResult:
        """Service version detection scan."""
        return await self.execute(
            target,
            ports=ports or "1-1000",
            scan_type="-sV",
            scripts=True
        )
    
    async def vuln_scan(self, target: str) -> ToolResult:
        """Vulnerability script scan."""
        cmd = f"nmap --script vuln -p 1-1000 -oX - {target}"
        
        result = await self.worker_pool.execute_task(cmd, self.tool_name)
        
        return ToolResult(
            tool_name=self.tool_name,
            success="ERROR:" not in result,
            raw_output=result,
            parsed_data=self.parse_output(result) if "ERROR:" not in result else {},
            findings=self.extract_findings(self.parse_output(result)) if "ERROR:" not in result else [],
            errors=[] if "ERROR:" not in result else [result],
            execution_time=0.0,
            command=cmd
        )
    
    # Legacy method for backward compatibility
    async def scan_target(self, target_ip: str, ports: str = "1-1000") -> List[Dict[str, Any]]:
        """Legacy method - returns list of open ports."""
        result = await self.execute(target_ip, ports=ports)
        
        # Convert to old format
        legacy_results = []
        for finding in result.findings:
            if finding.get("type") == "port_scan":
                legacy_results.append({
                    "ip": finding.get("host"),
                    "port": str(finding.get("port")),
                    "service": finding.get("service", "unknown")
                })
        
        return legacy_results
