"""Keybindings module for configurable F-key mappings.

Story 9.11: Keyboard Navigation (F-Keys) - Task 2

Provides:
- FKeyMapping dataclass for key bindings
- DEFAULT_FKEY_MAPPINGS constant with UX spec defaults
- load_keybindings() function for YAML config loading
- validate_mapping() function for config validation
- get_mapping_for_key() helper function

Config format (tui.yaml):
```yaml
tui:
  keybindings:
    f1: {action: dashboard, label: Dash}
    f2: {action: config, label: Cfg}
    ...
```
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from cyberred.tui.widgets.fkey_bar import FKeyMapping

logger = logging.getLogger(__name__)

# Re-export FKeyMapping for convenience
__all__ = [
    "FKeyMapping",
    "DEFAULT_FKEY_MAPPINGS",
    "load_keybindings",
    "validate_mapping",
    "get_mapping_for_key",
]

# Re-use DEFAULT_FKEY_MAPPINGS from fkey_bar to avoid duplication
from cyberred.tui.widgets.fkey_bar import DEFAULT_FKEY_MAPPINGS


def validate_mapping(key: str, mapping_data: Any) -> bool:
    """Validate a single keybinding mapping.
    
    Args:
        key: The key being mapped (e.g., "f1").
        mapping_data: The mapping configuration data.
        
    Returns:
        True if mapping is valid, False otherwise.
    """
    if mapping_data is None:
        logger.warning(f"Keybinding {key}: mapping is None")
        return False
    
    if not isinstance(mapping_data, dict):
        logger.warning(f"Keybinding {key}: expected dict, got {type(mapping_data).__name__}")
        return False
    
    if "action" not in mapping_data:
        logger.warning(f"Keybinding {key}: missing required 'action' field")
        return False
    
    if "label" not in mapping_data:
        logger.warning(f"Keybinding {key}: missing required 'label' field")
        return False
    
    return True


def get_mapping_for_key(
    key: str,
    mappings: List[FKeyMapping],
) -> Optional[FKeyMapping]:
    """Get mapping for a specific key.
    
    Args:
        key: The key to look up (e.g., "f1").
        mappings: List of FKeyMapping objects to search.
        
    Returns:
        FKeyMapping if found, None otherwise.
    """
    for mapping in mappings:
        if mapping.key == key:
            return mapping
    return None


def load_keybindings(config_path: Optional[Path]) -> List[FKeyMapping]:
    """Load keybindings from YAML config file.
    
    Loads custom keybindings from config and merges with defaults.
    Custom mappings override defaults. Invalid mappings are logged
    as warnings but don't crash (AC #5).
    
    Args:
        config_path: Path to YAML config file. If None or file doesn't
            exist, returns DEFAULT_FKEY_MAPPINGS.
            
    Returns:
        List of FKeyMapping objects (merged defaults + custom).
    """
    # Return defaults if no config path provided
    if config_path is None:
        return list(DEFAULT_FKEY_MAPPINGS)
    
    # Return defaults if file doesn't exist
    if not config_path.exists():
        logger.debug(f"Config file not found: {config_path}, using defaults")
        return list(DEFAULT_FKEY_MAPPINGS)
    
    # Try to load YAML config
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML in {config_path}: {e}, using defaults")
        return list(DEFAULT_FKEY_MAPPINGS)
    except Exception as e:
        logger.warning(f"Error reading {config_path}: {e}, using defaults")
        return list(DEFAULT_FKEY_MAPPINGS)
    
    # Return defaults if config is empty or invalid
    if not config or not isinstance(config, dict):
        return list(DEFAULT_FKEY_MAPPINGS)
    
    # Return defaults if no tui section
    tui_config = config.get("tui")
    if not tui_config or not isinstance(tui_config, dict):
        return list(DEFAULT_FKEY_MAPPINGS)
    
    # Return defaults if no keybindings section
    keybindings = tui_config.get("keybindings")
    if not keybindings or not isinstance(keybindings, dict):
        return list(DEFAULT_FKEY_MAPPINGS)
    
    # Start with a copy of defaults as a dict for easy merging
    result_dict: Dict[str, FKeyMapping] = {m.key: m for m in DEFAULT_FKEY_MAPPINGS}
    
    # Process custom keybindings
    for key, mapping_data in keybindings.items():
        if not validate_mapping(key, mapping_data):
            # Invalid mapping logged in validate_mapping, skip it
            continue
        
        # Create new mapping and override default
        new_mapping = FKeyMapping(
            key=key,
            action=mapping_data["action"],
            label=mapping_data["label"],
        )
        result_dict[key] = new_mapping
    
    # Convert back to list, maintaining order (f1, f2, ..., f10)
    # Sort by numeric value of key
    def key_sort(mapping: FKeyMapping) -> int:
        try:
            return int(mapping.key[1:])  # Extract number from "f1", "f10", etc.
        except (ValueError, IndexError):
            return 999  # Non-standard keys go last
    
    return sorted(result_dict.values(), key=key_sort)
