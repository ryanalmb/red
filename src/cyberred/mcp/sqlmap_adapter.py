"""
SQLMap Adapter - Automatic SQL injection detection and exploitation.

SQLMap is the premier open-source tool for SQL injection testing,
supporting detection and exploitation of all major SQL injection types.
"""
import re
from typing import Dict, List, Any
from cyberred.mcp.base_adapter import BaseToolAdapter, ToolResult


class SqlmapAdapter(BaseToolAdapter):
    """
    Adapter for SQLMap SQL injection testing.
    
    Supports detection and exploitation of: boolean-based, error-based,
    UNION-based, stacked queries, time-based blind, and out-of-band SQLi.
    """
    
    @property
    def tool_name(self) -> str:
        return "sqlmap"
    
    @property
    def tool_description(self) -> str:
        return "Automatic SQL injection and database takeover tool"
    
    def build_command(self, target: str, 
                      forms: bool = False,
                      batch: bool = True,
                      level: int = 3,
                      risk: int = 2,
                      dbs: bool = True,
                      technique: str = None,
                      tamper: str = None,
                      random_agent: bool = True,
                      threads: int = 5) -> str:
        """
        Build sqlmap command.
        
        Args:
            target: URL with potential injection point (use * for injection point)
            forms: Automatically test forms on the page
            batch: Non-interactive mode (auto-answer questions)
            level: Level of tests to perform (1-5)
            risk: Risk of tests to perform (1-3)
            dbs: Enumerate databases
            technique: Specific technique (B,E,U,S,T,Q)
            tamper: Tamper script(s) to use
            random_agent: Use random User-Agent
            threads: Number of concurrent threads
        """
        cmd = f"sqlmap -u '{target}'"
        
        if batch:
            cmd += " --batch"
        
        if forms:
            cmd += " --forms"
        
        cmd += f" --level={level}"
        cmd += f" --risk={risk}"
        cmd += f" --threads={threads}"
        
        if dbs:
            cmd += " --dbs"
        
        if technique:
            cmd += f" --technique={technique}"
        
        if tamper:
            cmd += f" --tamper={tamper}"
        
        if random_agent:
            cmd += " --random-agent"
        
        # Output settings
        cmd += " --output-dir=/tmp/sqlmap"
        
        return cmd
    
    def parse_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse sqlmap output for injection findings."""
        result = {
            "injectable": False,
            "injection_points": [],
            "parameters": [],
            "databases": [],
            "dbms": None,
            "dbms_version": None,
            "os": None,
            "technology": [],
            "waf_detected": False
        }
        
        # Check for vulnerability confirmation
        if any(phrase in raw_output.lower() for phrase in 
               ["is vulnerable", "parameter is vulnerable", "identified the following injection"]):
            result["injectable"] = True
        
        # Extract DBMS
        dbms_match = re.search(r"back-end DBMS: (.+)", raw_output)
        if dbms_match:
            result["dbms"] = dbms_match.group(1).strip()
        
        # Extract injectable parameters
        param_matches = re.findall(r"Parameter: (\w+) \((.*?)\)", raw_output)
        for param, injection_type in param_matches:
            result["parameters"].append({
                "name": param,
                "type": injection_type
            })
        
        # Extract databases
        db_matches = re.findall(r"\[\*\] (.+?) \(database\)", raw_output)
        if not db_matches:
            # Alternative pattern
            db_section = re.search(r"available databases \[\d+\]:\s*((?:\[\*\] .+\n)+)", raw_output)
            if db_section:
                db_matches = re.findall(r"\[\*\] (.+)", db_section.group(1))
        result["databases"] = db_matches
        
        # Check for WAF
        if "WAF" in raw_output or "is protected by" in raw_output.lower():
            result["waf_detected"] = True
        
        # Extract OS
        os_match = re.search(r"operating system: (.+)", raw_output, re.I)
        if os_match:
            result["os"] = os_match.group(1).strip()
        
        # Extract technology
        tech_matches = re.findall(r"web application technology: (.+)", raw_output, re.I)
        result["technology"] = [t.strip() for t in tech_matches]
        
        return result
    
    def extract_findings(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract SQL injection findings."""
        findings = []
        
        if parsed_data.get("injectable"):
            finding = {
                "type": "sqli",
                "severity": "critical",
                "name": "SQL Injection Vulnerability",
                "description": f"SQL injection found via: {', '.join(p['name'] for p in parsed_data['parameters'])}",
                "dbms": parsed_data.get("dbms"),
                "parameters": parsed_data.get("parameters"),
                "databases": parsed_data.get("databases"),
                "waf_detected": parsed_data.get("waf_detected")
            }
            findings.append(finding)
        
        if parsed_data.get("waf_detected"):
            findings.append({
                "type": "waf",
                "severity": "info",
                "name": "WAF Detected",
                "description": "Web Application Firewall detected - may need tamper scripts"
            })
        
        return findings
    
    async def quick_scan(self, target: str) -> ToolResult:
        """Quick detection-only scan with minimal invasiveness."""
        return await self.execute(
            target,
            level=1,
            risk=1,
            dbs=False,
            technique="B"  # Boolean-based only (fast)
        )
    
    async def comprehensive_scan(self, target: str) -> ToolResult:
        """Full scan with all techniques and high level/risk."""
        return await self.execute(
            target,
            level=5,
            risk=3,
            dbs=True
        )
    
    async def dump_database(self, target: str, database: str, table: str = None) -> ToolResult:
        """Dump data from a specific database."""
        cmd = f"sqlmap -u '{target}' --batch --dump -D {database}"
        if table:
            cmd += f" -T {table}"
        cmd += " --output-dir=/tmp/sqlmap"
        
        result = await self.worker_pool.execute_task(cmd, self.tool_name)
        
        return ToolResult(
            tool_name=self.tool_name,
            success="ERROR:" not in result,
            raw_output=result,
            parsed_data={"action": "dump", "database": database},
            findings=[],
            errors=[] if "ERROR:" not in result else [result],
            execution_time=0.0,
            command=cmd
        )
    
    async def get_shell(self, target: str) -> ToolResult:
        """Attempt to get an OS shell through SQL injection."""
        cmd = f"sqlmap -u '{target}' --batch --os-shell --output-dir=/tmp/sqlmap"
        
        result = await self.worker_pool.execute_task(cmd, self.tool_name)
        
        has_shell = "os-shell>" in result.lower()
        
        return ToolResult(
            tool_name=self.tool_name,
            success=has_shell,
            raw_output=result,
            parsed_data={"shell_obtained": has_shell},
            findings=[{
                "type": "shell",
                "severity": "critical",
                "name": "OS Shell via SQLi",
                "description": "Command shell obtained through SQL injection"
            }] if has_shell else [],
            errors=[] if has_shell else ["Shell not obtained"],
            execution_time=0.0,
            command=cmd
        )
