"""SARIF Export for Cyber-Red (Story 13.6).

Provides SARIF v2.1.0 format export for CI/CD integration with GitHub Security tab
and Azure DevOps.

SARIF (Static Analysis Results Interchange Format) is an OASIS standard for
representing static analysis results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from cyberred.storage.report_generator import ReportData

# Package version - should match pyproject.toml
__version__ = "2.0.0"

# Default template directory
_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# SARIF schema file (bundled)
_SCHEMA_PATH = _TEMPLATE_DIR / "sarif-schema-2.1.0.json"


class SARIFExporter:
    """Export engagement findings to SARIF v2.1.0 format.
    
    SARIF (Static Analysis Results Interchange Format) is an OASIS standard
    that enables integration with GitHub Security tab and Azure DevOps.
    
    Example:
        >>> from cyberred.storage.sarif_exporter import SARIFExporter
        >>> exporter = SARIFExporter()
        >>> sarif_json = exporter.export(report_data)
        >>> with open("findings.sarif", "w") as f:
        ...     f.write(sarif_json)
    """
    
    def __init__(self, template_path: Path | None = None) -> None:
        """Initialize SARIF exporter.
        
        Args:
            template_path: Optional custom Jinja2 template path.
                          If None, uses default sarif.jinja2 template.
                          
        Raises:
            FileNotFoundError: If template file does not exist.
        """
        if template_path is None:
            self.template_path = _TEMPLATE_DIR / "sarif.jinja2"
        else:
            self.template_path = Path(template_path)
        
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")
        
        # Set up Jinja2 environment
        self._env = Environment(
            loader=FileSystemLoader(self.template_path.parent),
            autoescape=False,  # JSON output, not HTML
        )
        self.template = self._env.get_template(self.template_path.name)
    
    def export(
        self,
        report_data: ReportData,
        as_dict: bool = False,
    ) -> str | dict[str, Any]:
        """Export report data to SARIF format.
        
        Args:
            report_data: ReportData containing findings to export.
            as_dict: If True, return dict instead of JSON string.
            
        Returns:
            SARIF output as JSON string or dictionary.
        """
        context = self._prepare_context(report_data)
        
        # Render template
        sarif_json = self.template.render(**context)
        
        if as_dict:
            return json.loads(sarif_json)
        
        # Re-encode to ensure proper Unicode handling (no escaping)
        parsed = json.loads(sarif_json)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    
    def _prepare_context(self, report_data: ReportData) -> dict[str, Any]:
        """Prepare template context from report data.
        
        Args:
            report_data: ReportData containing findings.
            
        Returns:
            Dictionary with template variables.
        """
        findings = report_data.findings
        
        # Generate rules from unique finding types
        rules = self._generate_rules(findings)
        
        # Map findings to SARIF results
        results = [self._map_finding_to_result(f) for f in findings]
        
        return {
            "version": __version__,
            "rules": rules,
            "results": results,
        }
    
    def _map_finding_to_result(self, finding: dict[str, Any]) -> dict[str, Any]:
        """Map a Cyber-Red Finding to a SARIF result object.
        
        Args:
            finding: The Finding dict to map.
            
        Returns:
            SARIF result dictionary.
        """
        # Normalize timestamp - handle datetime objects
        timestamp = finding.get("timestamp", "")
        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()
        elif timestamp is None:
            timestamp = ""
        
        # Normalize severity - handle None
        severity = finding.get("severity") or "medium"
        
        # Normalize type - handle None
        finding_type = finding.get("type") or "unknown"
        
        return {
            "ruleId": finding_type,
            "level": self._map_severity_to_level(severity),
            "message": {
                "text": finding.get("evidence") or f"{finding_type} vulnerability found"
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": finding.get("target") or ""
                        }
                    }
                }
            ],
            "partialFingerprints": {
                "finding_id": finding.get("id") or ""
            },
            "properties": {
                "agent_id": finding.get("agent_id") or "",
                "tool": finding.get("tool") or "",
                "timestamp": timestamp,
                "topic": finding.get("topic") or "",
            }
        }
    
    def _map_severity_to_level(self, severity: str | None) -> str:
        """Map Cyber-Red severity to SARIF level.
        
        SARIF levels: error, warning, note, none
        Cyber-Red severities: critical, high, medium, low, info
        
        Args:
            severity: Cyber-Red severity string (or None).
            
        Returns:
            SARIF level string.
        """
        if severity is None:
            return "warning"
        
        mapping = {
            "critical": "error",
            "high": "error",
            "medium": "warning",
            "low": "note",
            "info": "note",
        }
        return mapping.get(severity.lower(), "warning")
    
    def _generate_rules(self, findings: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate unique SARIF rule definitions from findings.
        
        Args:
            findings: List/tuple of findings.
            
        Returns:
            List of SARIF rule definitions.
        """
        # Group findings by type, track highest severity per type
        type_severities: dict[str, str] = {}
        severity_order = ["info", "low", "medium", "high", "critical"]
        
        for finding in findings:
            finding_type = finding.get("type") or "unknown"
            raw_severity = finding.get("severity") or "medium"
            finding_severity = raw_severity.lower()
            
            current = type_severities.get(finding_type)
            if current is None:
                type_severities[finding_type] = finding_severity
            else:
                # Use higher severity
                try:
                    current_idx = severity_order.index(current)
                    new_idx = severity_order.index(finding_severity)
                    if new_idx > current_idx:
                        type_severities[finding_type] = finding_severity
                except ValueError:
                    # Unknown severity, keep current
                    pass
        
        rules = []
        for rule_type, highest_severity in type_severities.items():
            rules.append({
                "id": rule_type,
                "name": self._type_to_name(rule_type),
                "shortDescription": {
                    "text": f"Detected {rule_type} vulnerability"
                },
                "defaultConfiguration": {
                    "level": self._map_severity_to_level(highest_severity)
                }
            })
        
        return sorted(rules, key=lambda r: r["id"])
    
    def _type_to_name(self, finding_type: str) -> str:
        """Convert finding type to human-readable rule name.
        
        Args:
            finding_type: Finding type string (e.g., "sqli", "xss").
            
        Returns:
            Human-readable name (e.g., "Sqli", "Xss").
        """
        if not finding_type:
            return "Unknown"
        return finding_type.replace("_", " ").replace("-", " ").title()


def validate_sarif(sarif_output: str | dict[str, Any]) -> bool:
    """Validate SARIF output against official schema.
    
    Args:
        sarif_output: SARIF JSON string or dict.
        
    Returns:
        True if valid.
        
    Raises:
        jsonschema.ValidationError: If invalid.
    """
    import jsonschema
    
    if isinstance(sarif_output, str):
        sarif_output = json.loads(sarif_output)
    
    # Load bundled schema
    schema = _get_sarif_schema()
    jsonschema.validate(sarif_output, schema)
    return True


def _get_sarif_schema() -> dict[str, Any]:
    """Load SARIF 2.1.0 schema from bundled file.
    
    Returns:
        JSON schema dictionary.
    """
    if _SCHEMA_PATH.exists():
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Fallback: minimal schema for validation (defensive code)
    return {  # pragma: no cover
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["version", "runs"],
        "properties": {
            "$schema": {"type": "string"},
            "version": {"type": "string", "const": "2.1.0"},
            "runs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["tool", "results"],
                    "properties": {
                        "tool": {
                            "type": "object",
                            "required": ["driver"],
                            "properties": {
                                "driver": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {
                                        "name": {"type": "string"},
                                        "version": {"type": "string"},
                                        "informationUri": {"type": "string"},
                                        "rules": {"type": "array"}
                                    }
                                }
                            }
                        },
                        "results": {"type": "array"}
                    }
                }
            }
        }
    }
