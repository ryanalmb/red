"""IPC Protocol for TUI-Daemon Communication.

This module defines the IPC protocol dataclasses and utilities for
communication between TUI/CLI clients and the Cyber-Red daemon over
Unix sockets.

Message Format:
- Serialization: JSON
- Delimiter: Newline (\\n) for message framing
- Encoding: UTF-8

Usage:
    from cyberred.daemon.ipc import (
        IPCRequest, IPCResponse, IPCCommand,
        build_request, encode_message, decode_message
    )

    # Build a request
    request = build_request(IPCCommand.SESSIONS_LIST)

    # Encode for wire transmission
    wire_data = encode_message(request)

    # Decode from wire
    decoded = decode_message(wire_data)
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Optional
import json
import uuid


MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB limit to prevent DoS


class IPCCommand(StrEnum):
    """IPC command constants.

    All valid IPC commands that can be sent from TUI/CLI to daemon.
    Uses StrEnum for type safety and built-in validation.
    """

    SESSIONS_LIST = "sessions.list"
    ENGAGEMENT_START = "engagement.start"  # params: {config_path: str, ignore_warnings: bool}
    ENGAGEMENT_ATTACH = "engagement.attach"
    ENGAGEMENT_DETACH = "engagement.detach"
    ENGAGEMENT_PAUSE = "engagement.pause"
    ENGAGEMENT_RESUME = "engagement.resume"
    ENGAGEMENT_STOP = "engagement.stop"
    DAEMON_STOP = "daemon.stop"
    DAEMON_CONFIG_RELOAD = "daemon.config.reload"  # Story 2.13: Trigger manual config reload


@dataclass
class IPCRequest:
    """IPC request from TUI/CLI to daemon.

    Attributes:
        command: The IPC command (e.g., 'sessions.list', 'engagement.start').
        params: Command parameters as key-value pairs.
        request_id: UUID for request/response correlation.
    """

    command: str
    params: dict[str, Any]
    request_id: str

    def __post_init__(self) -> None:
        """Validate request fields after initialization."""
        if not self.command:
            raise ValueError("IPCRequest.command must not be empty")
        if not self.request_id:
            raise ValueError("IPCRequest.request_id must not be empty")

    def to_json(self) -> str:
        """Serialize request to JSON string.

        Returns:
            JSON string representation of the request.
        """
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "IPCRequest":
        """Deserialize request from JSON string.

        Args:
            data: JSON string to parse.

        Returns:
            IPCRequest instance.

        Raises:
            json.JSONDecodeError: If JSON is invalid.
            TypeError: If JSON is not an object or fields are missing.
        """
        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            raise TypeError("JSON data must be a dictionary object")
            
        # Forward compatibility: Filter out unknown fields
        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in parsed.items() if k in known_fields}
        
        return cls(**filtered)


@dataclass
class IPCResponse:
    """IPC response from daemon to TUI/CLI.

    Attributes:
        status: Response status ('ok' or 'error').
        data: Response payload (None if error).
        error: Error message (None if success).
        request_id: Matching request ID for correlation.
    """

    status: str
    request_id: str
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate response fields after initialization."""
        if self.status not in ("ok", "error"):
            raise ValueError(f"IPCResponse.status must be 'ok' or 'error', got '{self.status}'")
        if not self.request_id:
            raise ValueError("IPCResponse.request_id must not be empty")

    def to_json(self) -> str:
        """Serialize response to JSON string.

        Returns:
            JSON string representation of the response.
        """
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "IPCResponse":
        """Deserialize response from JSON string.

        Args:
            data: JSON string to parse.

        Returns:
            IPCResponse instance.

        Raises:
            json.JSONDecodeError: If JSON is invalid.
            TypeError: If JSON is not an object or fields are missing.
        """
        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            raise TypeError("JSON data must be a dictionary object")

        # Forward compatibility: Filter out unknown fields
        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in parsed.items() if k in known_fields}

        return cls(**filtered)

    @classmethod
    def create_ok(cls, data: dict[str, Any], request_id: str) -> "IPCResponse":
        """Create a success response.

        Args:
            data: Response payload.
            request_id: Matching request ID.

        Returns:
            IPCResponse with status='ok'.
        """
        return cls(status="ok", data=data, error=None, request_id=request_id)

    @classmethod
    def create_error(cls, message: str, request_id: str) -> "IPCResponse":
        """Create an error response.

        Args:
            message: Error message.
            request_id: Matching request ID.

        Returns:
            IPCResponse with status='error'.
        """
        return cls(status="error", data=None, error=message, request_id=request_id)


def build_request(command: str, **params: Any) -> IPCRequest:
    """Build an IPC request with auto-generated request_id.

    Args:
        command: IPC command string (must be valid IPCCommand value).
        **params: Command parameters as keyword arguments.

    Returns:
        IPCRequest instance with unique request_id.

    Raises:
        ValueError: If command is not a valid IPCCommand value.
    """
    try:
        # Validate against enum values
        IPCCommand(command)
    except ValueError:
        valid_commands = [c.value for c in IPCCommand]
        raise ValueError(
            f"Invalid IPC command: '{command}'. "
            f"Valid commands: {valid_commands}"
        ) from None

    return IPCRequest(
        command=command,
        params=params,
        request_id=str(uuid.uuid4()),
    )


def encode_message(msg: IPCRequest | IPCResponse) -> bytes:
    """Encode message to wire format (JSON + newline, UTF-8).

    Args:
        msg: IPCRequest or IPCResponse to encode.

    Returns:
        UTF-8 encoded bytes with newline delimiter.
    """
    return (msg.to_json() + "\n").encode("utf-8")


def decode_message(data: bytes) -> IPCRequest | IPCResponse:
    """Decode message from wire format.

    Args:
        data: UTF-8 encoded bytes (JSON with optional newline).

    Returns:
        IPCRequest if 'command' field present, otherwise IPCResponse.

    Raises:
        IPCProtocolError: If message cannot be decoded or exceeds size limit.
    """
    from cyberred.core.exceptions import IPCProtocolError

    if len(data) > MAX_MESSAGE_SIZE:
        raise IPCProtocolError(
            f"Message size {len(data)} exceeds limit of {MAX_MESSAGE_SIZE} bytes"
        )

    try:
        text = data.decode("utf-8").strip()
        parsed = json.loads(text)

        if "command" in parsed:
            return IPCRequest.from_json(text)
        return IPCResponse.from_json(text)

    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise IPCProtocolError(f"Failed to decode IPC message: {e}") from e
    except (TypeError, KeyError) as e:
        raise IPCProtocolError(f"Invalid IPC message structure: {e}") from e
    except ValueError as e:
        raise IPCProtocolError(f"IPC message validation failed: {e}") from e
