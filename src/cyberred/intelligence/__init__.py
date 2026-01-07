"""Vulnerability Intelligence Layer for Cyber-Red.

This module provides a unified interface for querying vulnerability
intelligence sources including CISA KEV, NVD, ExploitDB, Nuclei, and Metasploit.

Exports:
    IntelligenceSource: Abstract base class for all intelligence sources.
    IntelResult: Dataclass for intelligence query results.
    IntelPriority: Priority ranking constants for result ordering.

Usage:
    from cyberred.intelligence import IntelligenceSource, IntelResult, IntelPriority
"""

from cyberred.intelligence.base import (
    IntelligenceSource,
    IntelPriority,
    IntelResult,
)

__all__ = [
    "IntelligenceSource",
    "IntelPriority",
    "IntelResult",
]
