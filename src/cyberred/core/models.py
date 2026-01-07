"""Core Data Models for Cyber-Red.

This module defines the standardized dataclasses for Finding, AgentAction,
and ToolResult. These models are used across all components for consistent
data structures.

Models:
    Finding: Vulnerability discovery with 10 fields including HMAC signature.
    AgentAction: Agent action record with decision_context for emergence tracing.
    ToolResult: Tool execution result (expected/tool errors, not exceptions).

Usage:
    from cyberred.core.models import Finding, AgentAction, ToolResult

    finding = Finding(
        id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
        type="sqli",
        severity="critical",
        target="192.168.1.100",
        evidence="Vulnerable parameter...",
        agent_id="ghost-42",
        timestamp="2025-12-27T23:30:00Z",
        tool="sqlmap",
        topic="findings:a1b2c3:sqli",
        signature="hmac-sig"
    )
"""

from __future__ import annotations

import json
import uuid
import re
import ipaddress
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Union


# Valid severity levels per architecture specification
VALID_SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})


def _validate_uuid(value: Optional[str], field_name: str) -> None:
    """Validate that the string is a valid UUID."""
    if value is None:
        return
    try:
        uuid.UUID(value)
    except ValueError:
        raise ValueError(f"Invalid UUID format for field '{field_name}': '{value}'")


def _validate_timestamp(value: str, field_name: str) -> None:
    """Validate that the string is a valid ISO 8601 timestamp."""
    try:
        # Handle 'Z' suffix manually since Python < 3.11 fromisoformat had limited Z support
        # but standardized replacement is safer for compatibility
        ts = value.replace("Z", "+00:00")
        datetime.fromisoformat(ts)
    except ValueError:
        raise ValueError(f"Invalid ISO 8601 timestamp for field '{field_name}': '{value}'")


def _validate_target(value: str, field_name: str) -> None:
    """Validate that the value is a valid IP address, URL, or hostname."""
    if not value or not value.strip():
        raise ValueError(f"Field '{field_name}' cannot be empty")
    
    # Basic whitespace check
    if re.search(r'\s', value):
        raise ValueError(f"Field '{field_name}' cannot contain whitespace")
    
    # Check if it's a valid IP address
    try:
        ipaddress.ip_address(value)
        return
    except ValueError:
        pass

    # Check if it's a valid URL (must have scheme and netloc, no spaces)
    # Simple regex: Scheme + :// + non-whitespace characters
    if re.match(r'^(https?|ftp|ssh|ws)://\S+$', value):
        return

    # Check if it's a valid hostname/domain
    # Simple regex for hostname (dots allowed, alphanumeric, hyphens)
    if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$', value):
        return
        
    raise ValueError(
        f"Invalid target format for field '{field_name}': '{value}'. "
        "Must be a valid IP address, URL, or hostname."
    )


@dataclass
class Finding:
    """Vulnerability finding with 10 required fields.

    All stigmergic messages use flat JSON with these fields.
    The signature field (HMAC-SHA256) mitigates Agent-in-the-Middle attacks.

    Attributes:
        id: UUID format identifier.
        type: Finding type ("sqli", "xss", "open_port", etc.).
        severity: One of "critical", "high", "medium", "low", "info".
        target: IP address or URL.
        evidence: Raw tool output or screenshot path.
        agent_id: Originating agent identifier.
        timestamp: ISO 8601 formatted timestamp.
        tool: Tool that produced finding ("nmap", "sqlmap", etc.).
        topic: Redis channel for routing (e.g., "findings:a1b2c3:sqli").
        signature: HMAC-SHA256 for message integrity.
    """

    id: str
    type: str
    severity: str
    target: str
    evidence: str
    agent_id: str
    timestamp: str
    tool: str
    topic: str
    signature: str

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        # Severity Validation
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{self.severity}'. "
                f"Must be one of: {', '.join(sorted(VALID_SEVERITIES))}"
            )
        
        # Format Validation
        _validate_uuid(self.id, "id")
        _validate_uuid(self.agent_id, "agent_id")
        _validate_timestamp(self.timestamp, "timestamp")
        _validate_target(self.target, "target")

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: Union[str, dict]) -> Finding:
        """Deserialize from JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)


@dataclass
class AgentAction:
    """Agent action record with decision_context for emergence tracing.

    The decision_context field is CRITICAL for NFR37 emergence validation.
    Every agent action must log which stigmergic signals influenced the decision.

    Attributes:
        id: UUID format identifier.
        agent_id: Acting agent identifier.
        action_type: Type of action ("scan", "exploit", "enumerate", etc.).
        target: Target of action.
        timestamp: ISO 8601 formatted timestamp.
        decision_context: List of IDs of stigmergic signals that influenced action.
        result_finding_id: ID of resulting finding, if any.
    """

    id: str
    agent_id: str
    action_type: str
    target: str
    timestamp: str
    decision_context: List[str] = field(default_factory=list)
    result_finding_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        _validate_uuid(self.id, "id")
        _validate_uuid(self.agent_id, "agent_id")
        _validate_timestamp(self.timestamp, "timestamp")
        _validate_target(self.target, "target")
        if self.result_finding_id is not None:
             _validate_uuid(self.result_finding_id, "result_finding_id")

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: Union[str, dict]) -> AgentAction:
        """Deserialize from JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)


@dataclass
class ToolResult:
    """Tool execution result.

    Used for expected/tool errors (success=True/False).
    Critical/system errors use exceptions instead.

    Attributes:
        success: Whether tool execution succeeded.
        stdout: Standard output from tool.
        stderr: Standard error from tool.
        exit_code: Process exit code.
        duration_ms: Execution duration in milliseconds.
        error_type: Optional error classification. Valid values:
            - None: Success (no error)
            - "TIMEOUT": Execution exceeded time limit
            - "NON_ZERO_EXIT": Command returned non-zero exit code
            - "CONTAINER_CRASHED": Container became unresponsive
            - "EXECUTION_EXCEPTION": Unexpected exception during execution
            - "POOL_EXHAUSTED": No containers available in pool
    """

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error_type: Optional[str] = None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: Union[str, dict]) -> ToolResult:
        """Deserialize from JSON string or dict.
        
        Handles backwards compatibility for JSON without error_type field.
        """
        if isinstance(data, str):
            data = json.loads(data)
        # Handle backwards compatibility - add error_type if missing
        if "error_type" not in data:
            data["error_type"] = None
        return cls(**data)
