"""Shared helpers for resolving LLM credentials from config/environment."""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Tuple


DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def _normalize_secret(value: Any) -> str:
    """Normalize pydantic SecretStr/plain values to a stripped string."""
    if value is None:
        return ""
    if hasattr(value, "get_secret_value"):
        try:
            value = value.get_secret_value()
        except Exception:
            return ""
    text = str(value).strip()
    return text


def resolve_llm_api_key_with_source(
    config: Optional[Mapping[str, Any]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve API key in deterministic order and return (value, source)."""
    cfg = config or {}
    candidates = (
        ("config:nvidia_api_key", _normalize_secret(cfg.get("nvidia_api_key"))),
        ("env:NVIDIA_API_KEY", _normalize_secret(os.environ.get("NVIDIA_API_KEY"))),
        ("env:NVIDIA_NIM_API_KEY", _normalize_secret(os.environ.get("NVIDIA_NIM_API_KEY"))),
        (
            "env:CYBERRED_LLM__NIM_API_KEY",
            _normalize_secret(os.environ.get("CYBERRED_LLM__NIM_API_KEY")),
        ),
        ("config:openai_api_key", _normalize_secret(cfg.get("openai_api_key"))),
        ("env:OPENAI_API_KEY", _normalize_secret(os.environ.get("OPENAI_API_KEY"))),
    )
    for source, value in candidates:
        if value:
            return value, source
    return None, None


def resolve_llm_api_key(config: Optional[Mapping[str, Any]] = None) -> Optional[str]:
    """Resolve API key in deterministic order."""
    key, _ = resolve_llm_api_key_with_source(config=config)
    return key


def resolve_llm_api_base(config: Optional[Mapping[str, Any]] = None) -> str:
    """Resolve API base URL in deterministic order."""
    cfg = config or {}
    candidates = (
        _normalize_secret(cfg.get("nvidia_base_url")),
        _normalize_secret(os.environ.get("NVIDIA_BASE_URL")),
        _normalize_secret(cfg.get("openai_api_base")),
        _normalize_secret(os.environ.get("OPENAI_API_BASE")),
    )
    for value in candidates:
        if value:
            return value
    return DEFAULT_NVIDIA_BASE_URL
