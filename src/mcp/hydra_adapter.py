"""
Hydra Adapter - Network login cracker.

Hydra is a fast and flexible network login cracker supporting
numerous protocols including SSH, FTP, HTTP, SMB, and more.
"""
import re
from typing import Dict, List, Any
from src.mcp.base_adapter import BaseToolAdapter, ToolResult


class HydraAdapter(BaseToolAdapter):
    """
    Adapter for Hydra password cracking.
    
    Supports 50+ protocols including: ssh, ftp, telnet, http-get, http-post,
    https-get, https-post, smb, mysql, postgres, mssql, vnc, rdp, and more.
    """
    
    @property
    def tool_name(self) -> str:
        return "hydra"
    
    @property
    def tool_description(self) -> str:
        return "Fast network login cracker supporting 50+ protocols"
    
    def build_command(self, target: str,
                      service: str = "ssh",
                      username: str = None,
                      username_file: str = None,
                      password_file: str = "/usr/share/wordlists/rockyou.txt",
                      port: int = None,
                      tasks: int = 16,
                      timeout: int = 30,
                      exit_on_first: bool = True,
                      verbose: bool = True) -> str:
        """
        Build hydra command.
        
        Args:
            target: Target host/IP
            service: Protocol/service to attack
            username: Single username to test
            username_file: File with usernames (one per line)
            password_file: File with passwords (one per line)
            port: Service port (uses default if not specified)
            tasks: Number of parallel connections
            timeout: Wait time for response
            exit_on_first: Stop on first valid credential
            verbose: Verbose output
        """
        cmd = "hydra"
        
        # User specification
        if username:
            cmd += f" -l {username}"
        elif username_file:
            cmd += f" -L {username_file}"
        else:
            # Use common usernames
            cmd += " -L /usr/share/seclists/Usernames/top-usernames-shortlist.txt"
        
        # Password specification
        cmd += f" -P {password_file}"
        
        # Performance options
        cmd += f" -t {tasks}"
        cmd += f" -w {timeout}"
        
        if exit_on_first:
            cmd += " -f"
        
        if verbose:
            cmd += " -V"
        
        # Target and service
        if port:
            cmd += f" -s {port}"
        
        cmd += f" {target} {service}"
        
        return cmd
    
    def parse_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse hydra output for cracked credentials."""
        result = {
            "success": False,
            "credentials": [],
            "attempts": 0,
            "service": None,
            "host": None
        }
        
        # Find cracked credentials
        # Pattern: [22][ssh] host: 192.168.1.1   login: admin   password: admin123
        cred_pattern = r"\[(\d+)\]\[(\w+)\] host: (\S+)(?:\s+login: (\S+))?\s+password: (\S+)"
        matches = re.findall(cred_pattern, raw_output)
        
        for match in matches:
            port, service, host, username, password = match
            result["credentials"].append({
                "port": port,
                "service": service,
                "host": host,
                "username": username or "unknown",
                "password": password
            })
            result["success"] = True
            result["service"] = service
            result["host"] = host
        
        # Also try simpler pattern
        simple_pattern = r"(?:login|host):\s*(\S+)\s+password:\s*(\S+)"
        for match in re.findall(simple_pattern, raw_output, re.I):
            if match not in [(c["username"], c["password"]) for c in result["credentials"]]:
                result["credentials"].append({
                    "username": match[0],
                    "password": match[1]
                })
                result["success"] = True
        
        # Count attempts
        attempts_match = re.search(r"(\d+) valid password", raw_output)
        if attempts_match:
            result["attempts"] = int(attempts_match.group(1))
        
        return result
    
    def extract_findings(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract credential findings."""
        findings = []
        
        for cred in parsed_data.get("credentials", []):
            findings.append({
                "type": "credential",
                "severity": "critical",
                "name": f"Valid Credentials Found ({cred.get('service', 'unknown')})",
                "description": f"Username: {cred.get('username')}, Password: {cred.get('password')}",
                "host": cred.get("host"),
                "port": cred.get("port"),
                "service": cred.get("service"),
                "username": cred.get("username"),
                "password": cred.get("password")
            })
        
        return findings
    
    async def ssh_brute(self, target: str, username: str = None) -> ToolResult:
        """Brute force SSH login."""
        return await self.execute(
            target,
            service="ssh",
            username=username,
            port=22
        )
    
    async def ftp_brute(self, target: str, username: str = None) -> ToolResult:
        """Brute force FTP login."""
        return await self.execute(
            target,
            service="ftp",
            username=username,
            port=21
        )
    
    async def http_form_brute(self, target: str, 
                              form_path: str,
                              username_field: str,
                              password_field: str,
                              fail_message: str,
                              username: str = None) -> ToolResult:
        """Brute force HTTP form login."""
        form_spec = f"{form_path}:{username_field}=^USER^&{password_field}=^PASS^:F={fail_message}"
        cmd = f"hydra -l {username or 'admin'} -P /usr/share/wordlists/rockyou.txt {target} http-post-form '{form_spec}' -t 16 -f"
        
        result = await self.worker_pool.execute_task(cmd, self.tool_name)
        parsed = self.parse_output(result)
        
        return ToolResult(
            tool_name=self.tool_name,
            success=parsed.get("success", False),
            raw_output=result,
            parsed_data=parsed,
            findings=self.extract_findings(parsed),
            errors=[] if "ERROR:" not in result else [result],
            execution_time=0.0,
            command=cmd
        )
    
    async def smb_brute(self, target: str, username: str = None) -> ToolResult:
        """Brute force SMB login."""
        return await self.execute(
            target,
            service="smb",
            username=username,
            port=445
        )
    
    async def mysql_brute(self, target: str, username: str = "root") -> ToolResult:
        """Brute force MySQL login."""
        return await self.execute(
            target,
            service="mysql",
            username=username,
            port=3306
        )
    
    async def quick_scan(self, target: str) -> ToolResult:
        """Quick scan with common credentials only."""
        # Use a smaller password list
        return await self.execute(
            target,
            service="ssh",
            password_file="/usr/share/seclists/Passwords/Common-Credentials/top-20-common-SSH-passwords.txt",
            tasks=32,
            timeout=15
        )
