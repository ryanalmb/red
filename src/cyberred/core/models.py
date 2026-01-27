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

import ipaddress
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

# Valid severity levels per architecture specification
VALID_SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})


def _validate_uuid(value: str | None, field_name: str) -> None:
    """Validate that the string is a valid UUID."""
    if value is None:
        return
    try:
        uuid.UUID(value)
    except ValueError:
        raise ValueError(
            f"Invalid UUID format for field '{field_name}': '{value}'"
        ) from None


def _validate_timestamp(value: str, field_name: str) -> None:
    """Validate that the string is a valid ISO 8601 timestamp."""
    try:
        # Handle 'Z' suffix manually since Python < 3.11 fromisoformat had limited Z support
        # but standardized replacement is safer for compatibility
        ts = value.replace("Z", "+00:00")
        datetime.fromisoformat(ts)
    except ValueError:
        raise ValueError(
            f"Invalid ISO 8601 timestamp for field '{field_name}': '{value}'"
        ) from None


def _validate_target(value: str, field_name: str) -> None:
    """Validate that the value is a valid IP address, URL, or hostname."""
    if not value or not value.strip():
        raise ValueError(f"Field '{field_name}' cannot be empty")

    # Basic whitespace check
    if re.search(r"\s", value):
        raise ValueError(f"Field '{field_name}' cannot contain whitespace")

    # Check if it's a valid IP address or CIDR
    try:
        ipaddress.ip_address(value)
        return
    except ValueError:
        pass
    
    try:
        ipaddress.ip_network(value, strict=False)
        return
    except ValueError:
        pass

    # Check if it's a valid URL (must have scheme and netloc, no spaces)
    # Simple regex: Scheme + :// + non-whitespace characters
    if re.match(r"^(https?|ftp|ssh|ws)://\S+$", value):
        return

    # Check if it's a valid hostname/domain
    # Simple regex for hostname (dots allowed, alphanumeric, hyphens)
    if re.match(
        r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$",
        value,
    ):
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
    def from_json(cls, data: str | dict) -> Finding:
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
    decision_context: list[str] = field(default_factory=list)
    result_finding_id: str | None = None

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
    def from_json(cls, data: str | dict) -> AgentAction:
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
    error_type: str | None = None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | dict) -> ToolResult:
        """Deserialize from JSON string or dict.

        Handles backwards compatibility for JSON without error_type field.
        """
        if isinstance(data, str):
            data = json.loads(data)
        # Handle backwards compatibility - add error_type if missing
        if "error_type" not in data:
            data["error_type"] = None
        return cls(**data)


@dataclass
class ToolSelectionContext:
    """Context for LLM tool selection.

    Provides all necessary context for an LLM to intelligently select
    the most appropriate tool for a given objective.

    Attributes:
        objective: What the agent is trying to achieve.
        target_info: Known information about target (ports, services, OS).
        available_tools: List of tools available for selection.
        phase: Current kill chain phase (recon, exploit, postex, etc.).
        constraints: Stealth requirements, timeouts, etc.
        previous_results: Results from previously executed tools.
    """

    objective: str
    target_info: dict[str, Any]
    available_tools: list[str]
    phase: str
    constraints: list[str] = field(default_factory=list)
    previous_results: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | dict) -> ToolSelectionContext:
        """Deserialize from JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)


@dataclass
class ToolSelection:
    """Result of LLM tool selection.

    Represents the outcome of an LLM-driven tool selection decision,
    including the command and rationale.

    Attributes:
        tool_name: Selected tool name (e.g., "nmap").
        command: Complete command string ready for execution.
        rationale: LLM's reasoning for the selection.
        expected_output_type: Expected output format (json, xml, text, etc.).
        confidence: Selection confidence (0.0-1.0).
        priority: Execution priority (1-10, higher = more important).
        alternatives: Other tools considered.
        selection_id: UUID for decision_context tracking (NFR37).
    """

    tool_name: str
    command: str
    rationale: str
    expected_output_type: str
    confidence: float = 0.8
    priority: int = 5
    alternatives: list[str] = field(default_factory=list)
    selection_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")
        if not 1 <= self.priority <= 10:
            raise ValueError(f"priority must be between 1 and 10, got {self.priority}")

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | dict) -> ToolSelection:
        """Deserialize from JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)


@dataclass
class Target:
    """Target entity for engagement scope and discovery.

    Attributes:
        value: Target value (IP, URL, SSID, Domain).
        type: Target type ("network", "webapp", "wireless", "domain").
        discovered_at: Timestamp of discovery (if applicable).
    """

    value: str
    type: str
    discovered_at: str | None = None

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if self.type not in {"network", "webapp", "wireless", "domain"}:
            raise ValueError(f"Invalid target type: {self.type}")
        _validate_target(self.value, "value")

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | dict) -> Target:
        """Deserialize from JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)


@dataclass
class Scope:
    """Engagement scope definition.

    Attributes:
        networks: List of network CIDRs/IPs.
        webapps: List of web application URLs.
        wireless: List of wireless SSIDs/BSSIDs.
        domains: List of AD domains.
        exclusions: List of excluded targets.
    """

    networks: list[str] = field(default_factory=list)
    webapps: list[str] = field(default_factory=list)
    wireless: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str | dict) -> Scope:
        """Deserialize from JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)
