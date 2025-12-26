"""
Nuclei Adapter - Vulnerability scanner using community templates.

Nuclei is a fast, customizable vulnerability scanner based on 
community-maintained templates for detecting security issues.
"""
import json
from typing import Dict, List, Any
from src.mcp.base_adapter import BaseToolAdapter, ToolResult


class NucleiAdapter(BaseToolAdapter):
    """
    Adapter for the Nuclei vulnerability scanner.
    
    Nuclei uses YAML-based templates to detect vulnerabilities,
    misconfigurations, exposed panels, and more.
    """
    
    @property
    def tool_name(self) -> str:
        return "nuclei"
    
    @property
    def tool_description(self) -> str:
        return "Fast, template-based vulnerability scanner"
    
    def build_command(self, target: str, templates: str = None, 
                      severity: str = "critical,high,medium",
                      rate_limit: int = 150,
                      timeout_per_template: int = 10,
                      json_output: bool = True,
                      tags: str = None) -> str:
        """
        Build nuclei command.
        
        Args:
            target: URL or host to scan
            templates: Specific template path or ID
            severity: Comma-separated severity filter
            rate_limit: Requests per second limit
            timeout_per_template: Timeout per template in seconds
            json_output: Output in JSON format
            tags: Template tags to include
        """
        cmd = f"nuclei -u {target}"
        
        if severity:
            cmd += f" -severity {severity}"
        
        if templates:
            cmd += f" -t {templates}"
        
        if tags:
            cmd += f" -tags {tags}"
        
        cmd += f" -rate-limit {rate_limit}"
        cmd += f" -timeout {timeout_per_template}"
        
        if json_output:
            cmd += " -jsonl -silent"
        
        return cmd
    
    def parse_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse JSON lines output from nuclei."""
        vulnerabilities = []
        
        for line in raw_output.strip().split('\n'):
            if not line:
                continue
            try:
                vuln = json.loads(line)
                vulnerabilities.append(vuln)
            except json.JSONDecodeError:
                # Skip non-JSON lines (status messages, etc.)
                continue
        
        return {
            "vulnerabilities": vulnerabilities,
            "total_count": len(vulnerabilities)
        }
    
    def extract_findings(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract vulnerability findings from nuclei output."""
        findings = []
        
        for vuln in parsed_data.get("vulnerabilities", []):
            info = vuln.get("info", {})
            
            finding = {
                "type": "vulnerability",
                "severity": info.get("severity", "unknown"),
                "name": info.get("name", "Unknown Vulnerability"),
                "description": info.get("description", ""),
                "template_id": vuln.get("template-id", ""),
                "matched_at": vuln.get("matched-at", ""),
                "matcher_name": vuln.get("matcher-name", ""),
                "extracted_results": vuln.get("extracted-results", []),
                "curl_command": vuln.get("curl-command", ""),
                "reference": info.get("reference", []),
                "tags": info.get("tags", []),
                "classification": {
                    "cve_id": info.get("classification", {}).get("cve-id", []),
                    "cwe_id": info.get("classification", {}).get("cwe-id", []),
                    "cvss_score": info.get("classification", {}).get("cvss-score", None)
                }
            }
            findings.append(finding)
        
        return findings
    
    async def quick_scan(self, target: str) -> ToolResult:
        """Run a quick scan with only critical and high severity templates."""
        return await self.execute(
            target,
            severity="critical,high",
            rate_limit=200,
            timeout_per_template=5
        )
    
    async def comprehensive_scan(self, target: str) -> ToolResult:
        """Run comprehensive scan with all severities."""
        return await self.execute(
            target,
            severity="critical,high,medium,low,info",
            rate_limit=100,
            timeout_per_template=15
        )
    
    async def scan_by_tags(self, target: str, tags: str) -> ToolResult:
        """
        Scan using specific template tags.
        
        Common tags: cve, oast, sqli, xss, rce, lfi, ssrf, exposure, 
                    wordpress, joomla, drupal, apache, nginx
        """
        return await self.execute(target, tags=tags)
    
    async def cve_scan(self, target: str) -> ToolResult:
        """Scan for known CVEs only."""
        return await self.execute(target, tags="cve", severity="critical,high")
