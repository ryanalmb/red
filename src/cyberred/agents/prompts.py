"""PromptLibrary class for loading role-specific system prompts.

This module provides a centralized library for loading and caching
role-specific prompts that guide LLM tool selection for agents.

Thread Safety:
    This class uses a threading.Lock to ensure thread-safe cache operations
    when used in multi-threaded agent swarm contexts.
"""

from pathlib import Path
from threading import Lock

import structlog

from .roles import AgentRole

logger = structlog.get_logger(__name__)

# Maximum allowed length for specialty parameter to prevent filesystem errors
MAX_SPECIALTY_LENGTH: int = 64


class PromptLibrary:
    """Library for loading role-specific system prompts with caching.

    Prompts are loaded from markdown files in the prompts directory.
    The library supports specialty-specific prompts (e.g., recon_network.md)
    that take precedence over base role prompts (e.g., recon.md).

    Thread Safety:
        All cache operations are protected by a lock for safe concurrent access.

    Attributes:
        PROMPT_DIR: Path to the directory containing prompt files.
        _cache: In-memory cache of loaded prompts.
        _lock: Threading lock for cache operations.
    """

    PROMPT_DIR: Path = Path(__file__).parent / "prompts"
    _cache: dict[str, str] = {}
    _lock: Lock = Lock()

    @classmethod
    def get(cls, role: AgentRole, specialty: str | None = None) -> str:
        """Load a prompt for the given role and optional specialty.

        Lookup order:
        1. {role}_{specialty}.md (if specialty provided and valid length)
        2. {role}.md
        3. Default generated prompt

        Args:
            role: The agent role to load a prompt for.
            specialty: Optional specialty modifier (e.g., "network", "osint").
                       Truncated if exceeds MAX_SPECIALTY_LENGTH.

        Returns:
            The prompt content as a string.
        """
        # Normalize specialty: treat empty string as None, truncate if too long
        if specialty is not None:
            specialty = specialty.strip() or None
            if specialty and len(specialty) > MAX_SPECIALTY_LENGTH:
                logger.warning(
                    "specialty_truncated",
                    original_length=len(specialty),
                    max_length=MAX_SPECIALTY_LENGTH,
                )
                specialty = specialty[:MAX_SPECIALTY_LENGTH]

        cache_key = cls._cache_key(role, specialty)

        with cls._lock:
            if cache_key in cls._cache:
                logger.debug("prompt_cache_hit", role=role.value, specialty=specialty)
                return cls._cache[cache_key]

            prompt = cls._load_prompt(role, specialty)
            cls._cache[cache_key] = prompt
            return prompt

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the prompt cache to enable hot-reload of prompts.

        Thread-safe: Uses lock to prevent race conditions during cache clear.
        """
        with cls._lock:
            cls._cache.clear()
        logger.debug("prompt_cache_cleared")

    @classmethod
    def _cache_key(cls, role: AgentRole, specialty: str | None) -> str:
        """Create a cache key for the role and specialty combination.

        Args:
            role: The agent role.
            specialty: Optional specialty modifier.

        Returns:
            A unique cache key string.
        """
        if specialty:
            return f"{role.value}_{specialty}"
        return role.value

    @classmethod
    def _load_prompt(cls, role: AgentRole, specialty: str | None) -> str:
        """Load a prompt from disk with fallback chain.

        Args:
            role: The agent role.
            specialty: Optional specialty modifier.

        Returns:
            The loaded prompt content or a default prompt.
        """
        # Try specialty-specific prompt first
        if specialty:
            specialty_path = cls.PROMPT_DIR / f"{role.value}_{specialty}.md"
            if specialty_path.exists():
                logger.debug(
                    "prompt_loaded",
                    role=role.value,
                    specialty=specialty,
                    path=str(specialty_path),
                )
                return specialty_path.read_text(encoding="utf-8")
            else:
                logger.debug(
                    "specialty_prompt_not_found_fallback",
                    role=role.value,
                    specialty=specialty,
                )

        # Try base role prompt
        role_path = cls.PROMPT_DIR / f"{role.value}.md"
        if role_path.exists():
            logger.debug(
                "prompt_loaded",
                role=role.value,
                path=str(role_path),
            )
            return role_path.read_text(encoding="utf-8")

        # Return default prompt
        logger.debug(
            "prompt_default_used",
            role=role.value,
            specialty=specialty,
        )
        return cls._default_prompt(role, specialty)

    @classmethod
    def _default_prompt(cls, role: AgentRole, specialty: str | None) -> str:
        """Generate a functional default prompt for a role.

        Args:
            role: The agent role.
            specialty: Optional specialty modifier.

        Returns:
            A default prompt string with role-specific content.
        """
        specialty_text = f" ({specialty} specialty)" if specialty else ""
        return f"""# {role.name} Specialist{specialty_text}

You are an expert {role.name} agent in a penetration testing swarm.
You have access to the full Kali Linux toolset (1,556+ tools).

## Primary Objectives
- Execute {role.name.lower()} operations as directed
- Coordinate with other agents via stigmergic signals
- Report findings accurately and promptly

## Tool Selection Guidelines
- Select appropriate tools from the 1,556+ available tools
- Consider target environment characteristics
- Prefer tools with structured output for reliable parsing

## Output Expectations
- Report all findings with confidence levels
- Provide structured data for downstream processing
- Flag high-value targets for prioritization

## Coordination
- Publish findings to stigmergic layer immediately
- Subscribe to strategy updates from Director Ensemble
- Avoid redundant operations by checking existing signals
"""
