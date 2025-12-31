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
from cyberred.mcp.base_adapter import BaseToolAdapter, ToolResult

# Core tool adapters
from cyberred.mcp.nmap_adapter import NmapAdapter
from cyberred.mcp.generic_adapter import GenericAdapter

# Vulnerability scanning
from cyberred.mcp.nuclei_adapter import NucleiAdapter
from cyberred.mcp.nikto_adapter import NiktoAdapter

# Web application testing
from cyberred.mcp.sqlmap_adapter import SqlmapAdapter
from cyberred.mcp.ffuf_adapter import FfufAdapter

# Credential attacks
from cyberred.mcp.hydra_adapter import HydraAdapter

# Reconnaissance
from cyberred.mcp.recon_adapters import SubfinderAdapter, MasscanAdapter

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
