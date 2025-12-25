"""
Subfinder Adapter - Fast subdomain discovery tool.

Subfinder is a subdomain discovery tool that uses passive sources
to discover subdomains without sending traffic to the target.
"""
import re
from typing import Dict, List, Any
from src.mcp.base_adapter import BaseToolAdapter, ToolResult


class SubfinderAdapter(BaseToolAdapter):
    """
    Adapter for Subfinder subdomain enumeration.
    
    Uses passive sources (search engines, DNS datasets, certificate
    transparency logs) to discover subdomains without active scanning.
    """
    
    @property
    def tool_name(self) -> str:
        return "subfinder"
    
    @property
    def tool_description(self) -> str:
        return "Passive subdomain discovery tool"
    
    def build_command(self, target: str,
                      recursive: bool = False,
                      threads: int = 30,
                      timeout_minutes: int = 10,
                      all_sources: bool = True,
                      silent: bool = True,
                      json_output: bool = False) -> str:
        """
        Build subfinder command.
        
        Args:
            target: Domain to enumerate
            recursive: Recursively enumerate subdomains
            threads: Number of concurrent goroutines
            timeout_minutes: Timeout for enumeration
            all_sources: Use all available sources
            silent: Show only subdomains in output
            json_output: Output in JSON format
        """
        # Clean domain
        domain = target.replace("http://", "").replace("https://", "").split("/")[0]
        
        cmd = f"subfinder -d {domain}"
        
        cmd += f" -t {threads}"
        cmd += f" -timeout {timeout_minutes}"
        
        if recursive:
            cmd += " -recursive"
        
        if all_sources:
            cmd += " -all"
        
        if silent:
            cmd += " -silent"
        
        if json_output:
            cmd += " -json -o /tmp/subfinder_output.json"
        
        return cmd
    
    def parse_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse subfinder output for discovered subdomains."""
        result = {
            "subdomains": [],
            "count": 0,
            "unique_prefixes": set()
        }
        
        for line in raw_output.strip().split('\n'):
            subdomain = line.strip()
            if subdomain and '.' in subdomain:
                result["subdomains"].append(subdomain)
                
                # Extract subdomain prefix
                parts = subdomain.split('.')
                if len(parts) > 2:
                    result["unique_prefixes"].add(parts[0])
        
        result["count"] = len(result["subdomains"])
        result["unique_prefixes"] = list(result["unique_prefixes"])
        
        return result
    
    def extract_findings(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract subdomain findings."""
        findings = []
        
        subdomains = parsed_data.get("subdomains", [])
        count = parsed_data.get("count", 0)
        
        if count > 0:
            # Summary finding
            findings.append({
                "type": "recon",
                "severity": "info",
                "name": "Subdomains Discovered",
                "description": f"Found {count} subdomains",
                "subdomains": subdomains[:20],  # First 20 in finding
                "total": count
            })
            
            # Flag interesting subdomains
            interesting_keywords = [
                "admin", "staging", "dev", "test", "api", "internal",
                "vpn", "mail", "ftp", "ssh", "rdp", "db", "database",
                "jenkins", "gitlab", "jira", "confluence", "backup"
            ]
            
            for subdomain in subdomains:
                subdomain_lower = subdomain.lower()
                for keyword in interesting_keywords:
                    if keyword in subdomain_lower:
                        findings.append({
                            "type": "recon",
                            "severity": "medium",
                            "name": f"Interesting Subdomain: {keyword}",
                            "description": f"Found potentially sensitive subdomain: {subdomain}",
                            "subdomain": subdomain,
                            "keyword": keyword
                        })
                        break  # Only add once per subdomain
        
        return findings
    
    async def quick_scan(self, target: str) -> ToolResult:
        """Quick subdomain enumeration."""
        return await self.execute(
            target,
            all_sources=False,
            timeout_minutes=5
        )
    
    async def comprehensive_scan(self, target: str) -> ToolResult:
        """Comprehensive subdomain enumeration with recursion."""
        return await self.execute(
            target,
            recursive=True,
            all_sources=True,
            timeout_minutes=30
        )


class MasscanAdapter(BaseToolAdapter):
    """
    Adapter for Masscan port scanner.
    
    Masscan is the fastest port scanner, capable of scanning
    the entire internet in under 6 minutes.
    """
    
    @property
    def tool_name(self) -> str:
        return "masscan"
    
    @property
    def tool_description(self) -> str:
        return "Ultra-fast port scanner for large-scale reconnaissance"
    
    def build_command(self, target: str,
                      ports: str = "1-65535",
                      rate: int = 10000,
                      wait_time: int = 5,
                      banners: bool = False) -> str:
        """
        Build masscan command.
        
        Args:
            target: IP address, CIDR range, or hostname
            ports: Port specification (e.g., "1-1000", "22,80,443")
            rate: Packets per second
            wait_time: Seconds to wait for responses after sending
            banners: Grab service banners
        """
        cmd = f"masscan {target} -p {ports} --rate {rate} --wait {wait_time}"
        
        if banners:
            cmd += " --banners"
        
        # Output format
        cmd += " -oG -"  # Greppable output to stdout
        
        return cmd
    
    def parse_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse masscan greppable output."""
        result = {
            "hosts": {},
            "total_open_ports": 0
        }
        
        # Pattern: Host: 192.168.1.1 ()	Ports: 22/open/tcp//ssh//
        for line in raw_output.split('\n'):
            if "Host:" not in line:
                continue
            
            host_match = re.search(r"Host:\s+(\S+)", line)
            ports_match = re.search(r"Ports:\s+(.+)", line)
            
            if host_match:
                host = host_match.group(1)
                if host not in result["hosts"]:
                    result["hosts"][host] = []
                
                if ports_match:
                    ports_str = ports_match.group(1)
                    # Parse each port entry
                    for port_entry in ports_str.split(','):
                        parts = port_entry.strip().split('/')
                        if len(parts) >= 4:
                            result["hosts"][host].append({
                                "port": parts[0],
                                "state": parts[1],
                                "protocol": parts[2],
                                "service": parts[4] if len(parts) > 4 else ""
                            })
                            result["total_open_ports"] += 1
        
        return result
    
    def extract_findings(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract port discovery findings."""
        findings = []
        
        for host, ports in parsed_data.get("hosts", {}).items():
            findings.append({
                "type": "port_scan",
                "severity": "info",
                "name": f"Open Ports on {host}",
                "description": f"Found {len(ports)} open ports",
                "host": host,
                "ports": ports
            })
            
            # Flag high-risk ports
            high_risk_ports = ["21", "22", "23", "3389", "5900", "6379", "27017", "3306", "1433"]
            for port_info in ports:
                if port_info["port"] in high_risk_ports:
                    findings.append({
                        "type": "port_scan",
                        "severity": "medium",
                        "name": f"High-Risk Port Open",
                        "description": f"{host}:{port_info['port']} ({port_info.get('service', 'unknown')})",
                        "host": host,
                        "port": port_info["port"]
                    })
        
        return findings
    
    async def quick_scan(self, target: str) -> ToolResult:
        """Quick scan of common ports."""
        return await self.execute(
            target,
            ports="21,22,23,25,80,110,111,135,139,143,443,445,993,995,1723,3306,3389,5900,8080",
            rate=50000
        )
    
    async def comprehensive_scan(self, target: str) -> ToolResult:
        """Full port scan."""
        return await self.execute(
            target,
            ports="1-65535",
            rate=10000,
            banners=True
        )
