"""TUI Screens for Cyber-Red.

Story 9.10: Drop Box Status Panel
- DropBoxScreen: Full-screen view for drop box status (F6)

Story 9.11: Keyboard Navigation (F-Keys)
- KillSwitchConfirmScreen: F10 kill switch confirmation modal
- HelpScreen: ? key help overlay

Story 10.1: Authorization Request Modal
- AuthorizationScreen: Enhanced HITL authorization modal with Y/N/M/S keybindings

Story 10.5: Runtime Scope Adjustment
- ScopeEditorScreen: Full-screen scope editor with add/remove, countdown, undo

Story 11.2: Exfiltrated Data Browser
- DataBrowserScreen: Full-screen data browser with categories, search, preview (F9)
"""
from .dropbox import DropBoxScreen
from .kill_confirm import KillSwitchConfirmScreen
from .help import HelpScreen
from .authorization import (
    AuthorizationScreen,
    AuthorizationRequest,
    AuthorizationResponse,
    AuthorizationType,
    AuthorizationDecision,
    RiskLevel,
    SwarmSnapshot,
)
from .scope_editor import (
    ScopeEditorScreen,
    ScopeChange,
    ScopeSnapshot as ScopeConfigSnapshot,
    ScopeUpdatedEvent,
    ScopeChangeManager,
    validate_cidr,
    validate_hostname,
    validate_port_range,
    is_production_range,
)
from .data_browser import DataBrowserScreen

__all__ = [
    "DropBoxScreen",
    "KillSwitchConfirmScreen",
    "HelpScreen",
    "AuthorizationScreen",
    "AuthorizationRequest",
    "AuthorizationResponse",
    "AuthorizationType",
    "AuthorizationDecision",
    "RiskLevel",
    "SwarmSnapshot",
    # Story 10.5
    "ScopeEditorScreen",
    "ScopeChange",
    "ScopeConfigSnapshot",
    "ScopeUpdatedEvent",
    "ScopeChangeManager",
    "validate_cidr",
    "validate_hostname",
    "validate_port_range",
    "is_production_range",
    # Story 11.2
    "DataBrowserScreen",
]
