"""Utility functions for RAG layer.

Provides shared utilities for technique ID validation and tactics lookup.
"""
import re
from typing import Dict, List

# Regex for ATT&CK technique IDs (T#### or T####.###)
TECHNIQUE_ID_PATTERN = re.compile(r"^T\d{4}(\.\d{3})?$")

# Global technique-to-tactics mapping cache
# Populated from MITRE ATT&CK data during ingestion
_TECHNIQUE_TACTICS_CACHE: Dict[str, List[str]] = {}


def validate_technique_id(technique_id: str) -> bool:
    """Validate that a technique ID matches ATT&CK format.
    
    Args:
        technique_id: The technique ID to validate (e.g., T1059 or T1059.001)
        
    Returns:
        True if valid ATT&CK technique ID format, False otherwise.
    
    Examples:
        >>> validate_technique_id("T1059")
        True
        >>> validate_technique_id("T1059.001")
        True
        >>> validate_technique_id("T12")
        False
        >>> validate_technique_id("TXXX")
        False
    """
    if not technique_id:
        return False
    return bool(TECHNIQUE_ID_PATTERN.match(technique_id))


def get_tactics_for_technique(technique_id: str) -> List[str]:
    """Look up ATT&CK tactics for a given technique ID.
    
    Uses cached mapping if available, otherwise returns empty list.
    Parent technique tactics are used for sub-techniques (T####.###).
    
    Args:
        technique_id: ATT&CK technique ID (e.g., T1059 or T1059.001)
        
    Returns:
        List of tactic names (e.g., ["execution", "persistence"])
    """
    if not technique_id:
        return []
    
    # Check cache for exact match
    if technique_id in _TECHNIQUE_TACTICS_CACHE:
        return _TECHNIQUE_TACTICS_CACHE[technique_id].copy()
    
    # For sub-techniques, try parent technique
    if "." in technique_id:
        parent_id = technique_id.split(".")[0]
        if parent_id in _TECHNIQUE_TACTICS_CACHE:
            return _TECHNIQUE_TACTICS_CACHE[parent_id].copy()
    
    return []


def get_tactics_for_techniques(technique_ids: List[str]) -> List[str]:
    """Look up ATT&CK tactics for multiple technique IDs.
    
    Args:
        technique_ids: List of ATT&CK technique IDs
        
    Returns:
        Deduplicated list of tactic names from all techniques
    """
    tactics_set: set[str] = set()
    for tid in technique_ids:
        tactics_set.update(get_tactics_for_technique(tid))
    return sorted(tactics_set)


def set_technique_tactics_cache(mapping: Dict[str, List[str]]) -> None:
    """Set the technique-to-tactics mapping cache.
    
    This should be called after ingesting MITRE ATT&CK data to enable
    tactics lookup for other sources like Atomic Red Team, HackTricks, etc.
    
    Args:
        mapping: Dict mapping technique IDs to lists of tactics
    """
    global _TECHNIQUE_TACTICS_CACHE
    _TECHNIQUE_TACTICS_CACHE = mapping.copy()


def get_technique_tactics_cache() -> Dict[str, List[str]]:
    """Get a deep copy of the current technique-to-tactics cache.
    
    Returns:
        Deep copy of the technique-to-tactics mapping
    """
    return {k: v.copy() for k, v in _TECHNIQUE_TACTICS_CACHE.items()}


def clear_technique_tactics_cache() -> None:
    """Clear the technique-to-tactics cache."""
    global _TECHNIQUE_TACTICS_CACHE
    _TECHNIQUE_TACTICS_CACHE = {}
