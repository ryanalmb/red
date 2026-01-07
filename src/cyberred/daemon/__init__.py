"""Cyber-Red Daemon Package.

This package contains the background daemon components for Cyber-Red,
including IPC protocol, Unix socket server, session management, and
engagement state machine.

Components:
- ipc: IPC protocol dataclasses and wire format utilities
- server: Unix socket server for TUI/CLI clients (Story 2.3)
- session_manager: Multi-engagement orchestration (Story 2.5)
- state_machine: Engagement lifecycle states (Story 2.4)
"""

from cyberred.daemon.ipc import (
    IPCCommand,
    IPCRequest,
    IPCResponse,
    build_request,
    decode_message,
    encode_message,
)
from cyberred.daemon.session_manager import (
    EngagementContext,
    EngagementSummary,
    SessionManager,
    ShutdownResult,
    validate_engagement_name,
)

__all__ = [
    "IPCCommand",
    "IPCRequest",
    "IPCResponse",
    "build_request",
    "decode_message",
    "encode_message",
    "EngagementContext",
    "EngagementSummary",
    "SessionManager",
    "ShutdownResult",
    "validate_engagement_name",
]

