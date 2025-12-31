"""
Nikto Adapter - Web server scanner.

Nikto is a comprehensive web server scanner that checks for
dangerous files, outdated software, and server misconfigurations.
"""
import re
from typing import Dict, List, Any
from cyberred.mcp.base_adapter import BaseToolAdapter, ToolResult


class NiktoAdapter(BaseToolAdapter):
    """
    Adapter for Nikto web server scanner.
    
    Checks for over 6700 potentially dangerous files/programs,
    outdated versions, and version-specific problems.
    """
    
    @property
    def tool_name(self) -> str:
        return "nikto"
    
    @property
    def tool_description(self) -> str:
        return "Web server scanner for dangerous files and misconfigurations"
    
    def build_command(self, target: str,
                      port: int = None,
                      ssl: bool = None,
                      tuning: str = None,
                      max_time: str = "30m",
                      no_404: bool = True,
                      plugins: str = None,
                      output_format: str = "csv") -> str:
        """
        Build nikto command.
        
        Args:
            target: Target host or URL
            port: Target port
            ssl: Force SSL mode
            tuning: Scan tuning (1-9, a-c)
                   1: Interesting File / Seen in logs
                   2: Misconfiguration / Default File
                   3: Information Disclosure
                   4: Injection (XSS/Script/HTML)
                   5: Remote File Retrieval - Inside Web Root
                   6: Denial of Service
                   7: Remote File Retrieval - Server Wide
                   8: Command Execution / Remote Shell
                   9: SQL Injection
                   a: Authentication Bypass
                   b: Software Identification
                   c: Remote Source Inclusion
            max_time: Maximum scan duration
            no_404: Disable 404 guessing
            plugins: Specific plugins to use
            output_format: Output format (csv, htm, txt, xml)
        """
        cmd = f"nikto -h {target}"
        
        if port:
            cmd += f" -p {port}"
        
        if ssl is True:
            cmd += " -ssl"
        elif ssl is False:
            cmd += " -nossl"
        
        if tuning:
            cmd += f" -Tuning {tuning}"
        
        if max_time:
            cmd += f" -maxtime {max_time}"
        
        if no_404:
            cmd += " -no404"
        
        if plugins:
            cmd += f" -Plugins {plugins}"
        
        # Don't output to file - let stdout be captured
        # The parse_output method handles text format
        
        return cmd
    
    def parse_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse nikto output for findings."""
        result = {
            "target": None,
            "port": None,
            "ssl": False,
            "server": None,
            "findings": [],
            "osvdb_entries": [],
            "interesting_headers": []
        }
        
        # Extract target info
        target_match = re.search(r"\+ Target IP:\s+(\S+)", raw_output)
        if target_match:
            result["target"] = target_match.group(1)
        
        port_match = re.search(r"\+ Target Port:\s+(\d+)", raw_output)
        if port_match:
            result["port"] = port_match.group(1)
        
        server_match = re.search(r"\+ Server:\s+(.+)", raw_output)
        if server_match:
            result["server"] = server_match.group(1).strip()
        
        if "SSL" in raw_output and ("enabled" in raw_output.lower() or "TLS" in raw_output):
            result["ssl"] = True
        
        # Extract findings (lines starting with +)
        for line in raw_output.split('\n'):
            line = line.strip()
            if not line or not line.startswith('+'):
                continue
            
            # Skip info lines
            skip_patterns = ["Target IP:", "Target Port:", "Target Hostname:", 
                           "Start Time:", "End Time:", "host(s) tested", "Server:"]
            if any(p in line for p in skip_patterns):
                continue
            
            # Extract OSVDB references
            osvdb_match = re.search(r"OSVDB-(\d+)", line)
            if osvdb_match:
                result["osvdb_entries"].append(osvdb_match.group(1))
            
            # Clean up the finding
            finding_text = line.lstrip('+ ').strip()
            if finding_text:
                result["findings"].append(finding_text)
        
        # Check for interesting headers
        header_patterns = [
            (r"X-Powered-By:\s*(.+)", "X-Powered-By"),
            (r"X-AspNet-Version:\s*(.+)", "X-AspNet-Version"),
            (r"Server:\s*(.+)", "Server"),
        ]
        
        for pattern, header_name in header_patterns:
            match = re.search(pattern, raw_output)
            if match:
                result["interesting_headers"].append({
                    "name": header_name,
                    "value": match.group(1).strip()
                })
        
        return result
    
    def extract_findings(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract security findings from nikto scan."""
        findings = []
        
        for finding in parsed_data.get("findings", []):
            severity = "info"
            finding_lower = finding.lower()
            
            # Determine severity based on content
            if any(kw in finding_lower for kw in ["rce", "remote code", "shell", "command execution"]):
                severity = "critical"
            elif any(kw in finding_lower for kw in ["sqli", "injection", "xss", "traversal", "file inclusion"]):
                severity = "high"
            elif any(kw in finding_lower for kw in ["disclosure", "sensitive", "password", "backup"]):
                severity = "high"
            elif any(kw in finding_lower for kw in ["outdated", "vulnerable", "default"]):
                severity = "medium"
            elif any(kw in finding_lower for kw in ["header", "missing", "ssl", "cookie"]):
                severity = "low"
            
            findings.append({
                "type": "web_vulnerability",
                "severity": severity,
                "name": "Nikto Finding",
                "description": finding,
                "source": "nikto"
            })
        
        # Add server info as finding if detected
        if parsed_data.get("server"):
            findings.append({
                "type": "fingerprint",
                "severity": "info",
                "name": "Web Server Identified",
                "description": f"Server: {parsed_data['server']}"
            })
        
        return findings
    
    async def quick_scan(self, target: str) -> ToolResult:
        """Quick scan with basic checks only."""
        return await self.execute(
            target,
            tuning="23b",  # Misconfig, Info Disclosure, Software ID
            max_time="5m"
        )
    
    async def comprehensive_scan(self, target: str) -> ToolResult:
        """Comprehensive scan with all tuning options."""
        return await self.execute(
            target,
            tuning="123456789abc",
            max_time="60m"
        )
    
    async def injection_scan(self, target: str) -> ToolResult:
        """Focus on injection vulnerabilities."""
        return await self.execute(
            target,
            tuning="489",  # XSS, Command Exec, SQLi
            max_time="15m"
        )
