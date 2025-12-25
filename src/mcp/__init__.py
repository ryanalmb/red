"""
MCP (Model Context Protocol) - Tool Adapters Package

This package contains adapters for security tools that provide
a unified interface for the Cyber-Red platform.

Adapters handle:
- Command construction
- Output parsing
- Result normalization
- Error handling
"""

# Base adapter class
from src.mcp.base_adapter import BaseToolAdapter, ToolResult

# Core tool adapters
from src.mcp.nmap_adapter import NmapAdapter
from src.mcp.generic_adapter import GenericAdapter

# Vulnerability scanning
from src.mcp.nuclei_adapter import NucleiAdapter
from src.mcp.nikto_adapter import NiktoAdapter

# Web application testing
from src.mcp.sqlmap_adapter import SqlmapAdapter
from src.mcp.ffuf_adapter import FfufAdapter

# Credential attacks
from src.mcp.hydra_adapter import HydraAdapter

# Reconnaissance
from src.mcp.recon_adapters import SubfinderAdapter, MasscanAdapter

# Export all adapters
__all__ = [
    # Base
    "BaseToolAdapter",
    "ToolResult",
    
    # Core
    "NmapAdapter",
    "GenericAdapter",
    
    # Vuln Scanning
    "NucleiAdapter",
    "NiktoAdapter",
    
    # Web App
    "SqlmapAdapter",
    "FfufAdapter",
    
    # Credentials
    "HydraAdapter",
    
    # Recon
    "SubfinderAdapter",
    "MasscanAdapter",
]
