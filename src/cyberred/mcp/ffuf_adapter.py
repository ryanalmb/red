"""
FFUF Adapter - Fast web fuzzer for content and parameter discovery.

FFUF (Fuzz Faster U Fool) is a Go-based web fuzzer used for 
directory brute-forcing, vhost discovery, and parameter fuzzing.
"""
import re
import json
from typing import Dict, List, Any
from cyberred.mcp.base_adapter import BaseToolAdapter, ToolResult


class FfufAdapter(BaseToolAdapter):
    """
    Adapter for FFUF web fuzzer.
    
    Used for: directory/file discovery, vhost enumeration,
    GET/POST parameter fuzzing, and general web fuzzing.
    """
    
    @property
    def tool_name(self) -> str:
        return "ffuf"
    
    @property
    def tool_description(self) -> str:
        return "Fast web fuzzer for content and parameter discovery"
    
    def build_command(self, target: str,
                      wordlist: str = "/usr/share/seclists/Discovery/Web-Content/common.txt",
                      extensions: str = None,
                      filter_codes: str = "404",
                      match_codes: str = None,
                      threads: int = 50,
                      recursion: bool = False,
                      recursion_depth: int = 2,
                      rate: int = 0,
                      timeout: int = 10,
                      json_output: bool = True) -> str:
        """
        Build ffuf command.
        
        Args:
            target: URL with FUZZ keyword (e.g., http://target/FUZZ)
            wordlist: Path to wordlist file
            extensions: Comma-separated extensions to append (e.g., php,txt,html)
            filter_codes: HTTP codes to filter out (comma-separated)
            match_codes: HTTP codes to match (comma-separated)
            threads: Number of concurrent threads
            recursion: Enable recursive scanning
            recursion_depth: How deep to recurse
            rate: Requests per second limit (0 = unlimited)
            timeout: Request timeout in seconds
            json_output: Output results in JSON format
        """
        # Ensure FUZZ keyword exists
        if "FUZZ" not in target.upper():
            target = f"{target.rstrip('/')}/FUZZ"
        
        cmd = f"ffuf -u {target} -w {wordlist}"
        
        if extensions:
            cmd += f" -e .{extensions.replace(',', ',.')}"
        
        if filter_codes:
            cmd += f" -fc {filter_codes}"
        
        if match_codes:
            cmd += f" -mc {match_codes}"
        
        cmd += f" -t {threads}"
        cmd += f" -timeout {timeout}"
        
        if recursion:
            cmd += f" -recursion -recursion-depth {recursion_depth}"
        
        if rate > 0:
            cmd += f" -rate {rate}"
        
        # Output to stdout (not file) for capture
        # Using -json flag sends JSON to stdout
        if json_output:
            cmd += " -of json"
        
        return cmd
    
    def parse_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse ffuf output for discovered content."""
        result = {
            "endpoints": [],
            "total_found": 0,
            "interesting": []
        }
        
        # Try to parse JSON output file if it exists
        try:
            # Check if output contains JSON directly
            if raw_output.strip().startswith("{"):
                data = json.loads(raw_output)
                results = data.get("results", [])
                result["endpoints"] = results
                result["total_found"] = len(results)
            else:
                # Parse line-by-line output
                for line in raw_output.strip().split('\n'):
                    if not line:
                        continue
                    
                    # Pattern: url [Status: 200, Size: 1234, Words: 56, Lines: 12]
                    match = re.match(r"(.+?)\s+\[Status: (\d+), Size: (\d+), Words: (\d+), Lines: (\d+)", line)
                    if match:
                        result["endpoints"].append({
                            "url": match.group(1).strip(),
                            "status": int(match.group(2)),
                            "size": int(match.group(3)),
                            "words": int(match.group(4)),
                            "lines": int(match.group(5))
                        })
                
                result["total_found"] = len(result["endpoints"])
        except json.JSONDecodeError:
            pass
        
        # Identify interesting findings
        for ep in result["endpoints"]:
            status = ep.get("status", 0)
            url = ep.get("url", ep.get("input", {}).get("FUZZ", ""))
            
            # Flag interesting endpoints
            interesting_patterns = [
                "admin", "backup", "config", ".git", ".env",
                "dashboard", "login", "phpmyadmin", "wp-admin",
                "api", "swagger", "graphql", "console"
            ]
            
            if any(p in url.lower() for p in interesting_patterns):
                result["interesting"].append(ep)
            
            # Redirect or authentication endpoints
            if status in [301, 302, 401, 403]:
                result["interesting"].append(ep)
        
        return result
    
    def extract_findings(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract discovery findings."""
        findings = []
        
        # Report interesting endpoints
        for ep in parsed_data.get("interesting", []):
            url = ep.get("url", ep.get("input", {}).get("FUZZ", "unknown"))
            status = ep.get("status", "unknown")
            
            severity = "low"
            if any(p in url.lower() for p in [".git", ".env", "backup", "config"]):
                severity = "high"
            elif any(p in url.lower() for p in ["admin", "dashboard", "phpmyadmin"]):
                severity = "medium"
            
            findings.append({
                "type": "discovery",
                "severity": severity,
                "name": f"Interesting Endpoint Found",
                "description": f"Found: {url} (Status: {status})",
                "url": url,
                "status_code": status,
                "size": ep.get("size")
            })
        
        # Summary finding
        total = parsed_data.get("total_found", 0)
        if total > 0:
            findings.append({
                "type": "discovery_summary",
                "severity": "info",
                "name": "Content Discovery Summary",
                "description": f"Discovered {total} endpoints, {len(parsed_data.get('interesting', []))} flagged as interesting"
            })
        
        return findings
    
    async def directory_scan(self, target: str, wordlist: str = None) -> ToolResult:
        """Standard directory discovery scan."""
        wl = wordlist or "/usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt"
        return await self.execute(target, wordlist=wl)
    
    async def quick_scan(self, target: str) -> ToolResult:
        """Quick scan with common paths only."""
        return await self.execute(
            target,
            wordlist="/usr/share/seclists/Discovery/Web-Content/common.txt",
            threads=100
        )
    
    async def comprehensive_scan(self, target: str) -> ToolResult:
        """Comprehensive scan with recursion and extensions."""
        return await self.execute(
            target,
            wordlist="/usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt",
            extensions="php,html,txt,bak,old,conf",
            recursion=True,
            recursion_depth=3,
            threads=50
        )
    
    async def vhost_scan(self, target: str, domain: str) -> ToolResult:
        """Virtual host enumeration."""
        cmd = f"ffuf -u {target} -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt -H 'Host: FUZZ.{domain}' -fc 404 -s"
        
        result = await self.worker_pool.execute_task(cmd, self.tool_name)
        parsed = self.parse_output(result)
        
        return ToolResult(
            tool_name=self.tool_name,
            success="ERROR:" not in result,
            raw_output=result,
            parsed_data=parsed,
            findings=self.extract_findings(parsed),
            errors=[] if "ERROR:" not in result else [result],
            execution_time=0.0,
            command=cmd
        )
    
    async def parameter_fuzz(self, target: str) -> ToolResult:
        """Fuzz for hidden parameters."""
        # Replace FUZZ in URL or add ?FUZZ=test
        if "?" not in target:
            fuzz_url = f"{target}?FUZZ=test"
        else:
            fuzz_url = target.replace("=", "=FUZZ")
        
        return await self.execute(
            fuzz_url,
            wordlist="/usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt",
            filter_codes="404,500",
            threads=100
        )
