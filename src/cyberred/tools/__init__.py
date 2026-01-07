"""Cyber-Red Tools Package - Scope Validator and Tool Execution Components.

This package contains the tool execution layer components including:
- ScopeValidator: Hard-gate deterministic scope validation (FR20, FR21)
- ScopeConfig: Configuration dataclass for scope definitions

Safety-Critical Components:
- Scope validation is FAIL-CLOSED (deny on any error)
- All validations are logged to audit trail
- Reserved IP ranges are ALWAYS blocked
"""

from cyberred.tools.scope import ScopeValidator, ScopeConfig
from cyberred.tools.container_pool import ContainerPool, MockContainer, ContainerContext, RealContainer
from cyberred.tools.kali_executor import KaliExecutor, kali_execute, initialize_executor
from cyberred.tools.manifest import ManifestLoader, ToolManifest
from cyberred.tools.output import OutputProcessor, ProcessedOutput

__all__ = ["ScopeValidator", "ScopeConfig", "ContainerPool", "MockContainer", "ContainerContext", "RealContainer", "KaliExecutor", "kali_execute", "initialize_executor", "ManifestLoader", "ToolManifest", "OutputProcessor", "ProcessedOutput"]

