"""Cyber-Red Configuration System.

Layered YAML configuration with Pydantic validation (FR46).
Supports system, engagement, and runtime config layers with env var secrets.

Config Layer Priority (highest to lowest):
1. Runtime overrides (in-memory)
2. Engagement config (~/.cyber-red/engagements/{name}.yaml)
3. System config (~/.cyber-red/config.yaml)
4. Defaults (defined in Pydantic models)

Usage:
    from cyberred.core.config import get_settings
    
    settings = get_settings()
    print(settings.redis.host)  # "localhost" (default)
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
import warnings
from pydantic import BaseModel, Field, PositiveInt, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cyberred.core.exceptions import ConfigurationError


# =============================================================================
# Sub-configuration Models (nested sections)
# =============================================================================


class RedisConfig(BaseModel):
    """Redis connection configuration."""

    host: str = "localhost"
    port: PositiveInt = 6379
    sentinel_hosts: List[str] = Field(default_factory=list)
    master_name: str = "mymaster"


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    providers: List[str] = Field(default_factory=list)
    rate_limit: PositiveInt = 30  # RPM
    timeout: PositiveInt = 180  # seconds
    nim_api_key: Optional[SecretStr] = None


class StorageConfig(BaseModel):
    """Storage configuration."""

    base_path: str = "~/.cyber-red"
    max_disk_percent: PositiveInt = 90


class SecurityConfig(BaseModel):
    """Security configuration."""

    pbkdf2_iterations: PositiveInt = 600000
    ca_validity_days: PositiveInt = 365
    cert_validity_days: PositiveInt = 1
    master_password: Optional[SecretStr] = None


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"
    output: str = "stdout"

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()


class MetricsConfig(BaseModel):
    """Metrics configuration."""

    enabled: bool = False
    port: PositiveInt = 9090


class MetasploitConfig(BaseModel):
    """Metasploit RPC configuration."""

    host: str = "127.0.0.1"
    port: PositiveInt = 55553
    pool_size: PositiveInt = 5
    password: Optional[SecretStr] = None


class IntelligenceConfig(BaseModel):
    """Intelligence layer configuration."""

    cache_ttl: PositiveInt = 3600  # 1 hour
    source_timeout: PositiveInt = 5  # seconds
    metasploit: MetasploitConfig = Field(default_factory=MetasploitConfig)
    nvd_api_key: Optional[SecretStr] = None


class NTPConfig(BaseModel):
    """NTP time synchronization configuration."""

    server: str = "pool.ntp.org"
    sync_ttl: PositiveInt = 60  # seconds
    drift_warn_threshold: float = 1.0  # seconds
    drift_error_threshold: float = 5.0  # seconds


class RAGConfig(BaseModel):
    """RAG configuration."""

    store_path: str = "~/.cyber-red/rag/lancedb"
    embedding_model: str = "basel/ATTACK-BERT"
    fallback_model: str = "all-mpnet-base-v2"
    chunk_size: PositiveInt = 512
    update_schedule: str = "weekly"


# =============================================================================
# Main Configuration Models
# =============================================================================


class SystemConfig(BaseModel):
    """System-level configuration (from config.yaml)."""

    redis: RedisConfig = Field(default_factory=RedisConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    intelligence: IntelligenceConfig = Field(default_factory=IntelligenceConfig)
    ntp: NTPConfig = Field(default_factory=NTPConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)


class EngagementConfig(BaseModel):
    """Engagement-specific configuration."""

    name: str = ""
    scope_path: str = ""
    objectives: List[str] = Field(default_factory=list)
    max_agents: PositiveInt = 1000
    auto_pause_hours: PositiveInt = 24


class RuntimeConfig(BaseModel):
    """Runtime overrides (in-memory only)."""

    scope_overrides: Optional[Dict[str, Any]] = None
    rate_limit_override: Optional[PositiveInt] = None
    paused: bool = False


class Settings(BaseSettings):
    """Main settings class with layered configuration support.
    
    Loads configuration from:
    1. Environment variables (CYBERRED_ prefix)
    2. System config file (~/.cyber-red/config.yaml)
    3. Defaults defined in Pydantic models
    """

    model_config = SettingsConfigDict(
        env_prefix="CYBERRED_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Nested configurations
    redis: RedisConfig = Field(default_factory=RedisConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging_config: LoggingConfig = Field(
        default_factory=LoggingConfig, alias="logging"
    )

    @property
    def logging(self) -> LoggingConfig:
        """Alias for logging_config to match YAML key and common usage."""
        return self.logging_config
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    intelligence: IntelligenceConfig = Field(default_factory=IntelligenceConfig)
    ntp: NTPConfig = Field(default_factory=NTPConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)

    # Engagement config (loaded separately)
    engagement: EngagementConfig = Field(default_factory=EngagementConfig)

    # Runtime config (in-memory overrides)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)


# =============================================================================
# Configuration Loading Functions
# =============================================================================


def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Load and parse a YAML file.
    
    Args:
        path: Path to the YAML file.
        
    Returns:
        Parsed YAML content as dictionary.
        
    Raises:
        ConfigurationError: If file cannot be read or parsed.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            return content if content else {}
    except FileNotFoundError:
        raise ConfigurationError(
            config_path=str(path),
            message=f"Configuration file not found: {path}",
        )
    except yaml.YAMLError as e:
        raise ConfigurationError(
            config_path=str(path),
            message=f"Invalid YAML in {path}: {e}",
        )


def load_system_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load system configuration from YAML file.
    
    Args:
        path: Optional path to config file. Defaults to ~/.cyber-red/config.yaml.
        
    Returns:
        System configuration dictionary.
        
    Raises:
        ConfigurationError: If file cannot be loaded.
    """
    if path is None:
        path = Path.home() / ".cyber-red" / "config.yaml"
    
    path = Path(path).expanduser()
    
    if not path.exists():
        # Return empty dict if default config doesn't exist
        return {}
    
    return load_yaml_file(path)


def load_engagement_config(name: str, base_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load engagement-specific configuration.
    
    Args:
        name: Engagement name (used as filename).
        base_path: Optional base path. Defaults to ~/.cyber-red/engagements/.
        
    Returns:
        Engagement configuration dictionary.
        
    Raises:
        ConfigurationError: If file cannot be loaded.
    """
    if base_path is None:
        base_path = Path.home() / ".cyber-red" / "engagements"
    
    base_path = Path(base_path).expanduser()
    config_path = base_path / f"{name}.yaml"
    
    if not config_path.exists():
        return {}
    
    return load_yaml_file(config_path)


def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge multiple configuration dictionaries.
    
    Later configs override earlier ones.
    
    Args:
        *configs: Configuration dictionaries to merge.
        
    Returns:
        Merged configuration dictionary.
    """
    result: Dict[str, Any] = {}
    
    for config in configs:
        for key, value in config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge_configs(result[key], value)
            else:
                result[key] = value
    
    return result


def create_settings(
    system_config_path: Optional[Path] = None,
    engagement_name: Optional[str] = None,
    engagement_base_path: Optional[Path] = None,
    runtime_overrides: Optional[Dict[str, Any]] = None,
) -> Settings:
    """Create a Settings instance with layered configuration.
    
    Args:
        system_config_path: Optional path to system config file.
        engagement_name: Optional engagement name to load engagement config.
        engagement_base_path: Optional base path for engagement configs.
            Defaults to the engagements/ subdirectory next to system config.
        runtime_overrides: Optional runtime overrides dictionary.
        
    Returns:
        Configured Settings instance.
        
    Raises:
        ConfigurationError: If configuration is invalid.
    """
    # Determine config base directory
    if system_config_path:
        config_base = Path(system_config_path).expanduser().parent
    else:
        config_base = Path.home() / ".cyber-red"
    
    # Load .env file for secrets
    env_path = config_base / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    # Load system config
    system_config = load_system_config(system_config_path)
    
    # Load engagement config if specified
    engagement_config = {}
    if engagement_name:
        # Use provided engagement_base_path or derive from config_base
        if engagement_base_path is None:
            engagement_base_path = config_base / "engagements"
        engagement_config = load_engagement_config(engagement_name, engagement_base_path)
    
    # Merge configs (system < engagement < runtime)
    merged = merge_configs(system_config, engagement_config)
    if runtime_overrides:
        merged = merge_configs(merged, runtime_overrides)
    
    # Create Settings from merged config
    try:
        return Settings(**merged)
    except Exception as e:
        raise ConfigurationError(
            config_path=str(system_config_path or "~/.cyber-red/config.yaml"),
            message=f"Configuration validation failed: {e}",
        ) from e


# =============================================================================
# Singleton Settings Access
# =============================================================================


class _SettingsHolder:
    """Thread-safe singleton holder for Settings instance.
    
    Also manages config file watcher for hot reload support (Story 2.13).
    """
    
    _instance: Optional[Settings] = None
    _lock: threading.Lock = threading.Lock()
    _watcher: Optional["ConfigWatcher"] = None  # Forward reference
    _last_reload: Optional[float] = None
    _pending_unsafe_changes: list[str] = []
    _system_config_path: Optional[Path] = None
    
    @classmethod
    def get(cls, force_reload: bool = False, **kwargs: Any) -> Settings:
        """Get or create the Settings singleton.
        
        Args:
            force_reload: If True, recreate settings even if already loaded.
            **kwargs: Arguments passed to create_settings().
            
        Returns:
            Settings instance.
        """
        if cls._instance is None or force_reload:
            with cls._lock:
                # Double-check locking
                if cls._instance is None or force_reload:  # pragma: no cover
                    cls._instance = create_settings(**kwargs)
                    # Track system config path for hot reload
                    if "system_config_path" in kwargs and kwargs["system_config_path"]:
                        cls._system_config_path = Path(kwargs["system_config_path"])
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        with cls._lock:
            if cls._watcher is not None:
                cls._watcher.stop()
                cls._watcher = None
            cls._instance = None
            cls._last_reload = None
            cls._pending_unsafe_changes = []
            cls._system_config_path = None
    
    @classmethod
    def start_watching(cls, config_path: Path) -> None:
        """Start watching config file for changes.
        
        Args:
            config_path: Path to the config file to watch.
        """
        # Import here to avoid circular import
        from cyberred.core.config_watcher import ConfigWatcher
        
        if cls._watcher is not None:
            cls._watcher.stop()
        
        cls._system_config_path = config_path
        cls._watcher = ConfigWatcher(
            config_path=config_path,
            callback=cls._handle_config_change,
            debounce_seconds=1.0,
        )
        cls._watcher.start()
    
    @classmethod
    def stop_watching(cls) -> None:
        """Stop watching config file."""
        if cls._watcher is not None:
            cls._watcher.stop()
            cls._watcher = None
    
    @classmethod
    def _handle_config_change(cls, path: Path) -> None:
        """Handle config file change event.
        
        Loads new config, checks if changes are safe, and applies
        if all changes can be hot-reloaded.
        
        Args:
            path: Path to the changed config file.
        """
        import structlog
        log = structlog.get_logger()
        
        with cls._lock:
            if cls._instance is None:
                return
            
            try:
                # Load new config
                new_settings = create_settings(system_config_path=path)
            except Exception as e:
                log.error(
                    "config_reload_validation_failed",
                    path=str(path),
                    error=str(e),
                )
                return
            
            # Check what changed
            changes = diff_configs(cls._instance, new_settings)
            
            if not changes:
                log.debug("config_reload_no_changes", path=str(path))
                return
            
            # Check if all changes are safe
            all_safe, unsafe_paths = is_safe_config_change(
                cls._instance, new_settings
            )
            
            if all_safe:
                # Apply the reload
                cls._instance = new_settings
                cls._last_reload = time.time()
                cls._pending_unsafe_changes = []
                
                log.info(
                    "config_reloaded",
                    changed_paths=list(changes.keys()),
                )
            else:
                # Don't apply, but track the pending unsafe changes
                cls._pending_unsafe_changes = unsafe_paths
                
                log.warning(
                    "config_reload_blocked",
                    unsafe_paths=unsafe_paths,
                    message="Restart daemon to apply these changes",
                )


def get_reload_status() -> dict[str, Any]:
    """Get the current hot reload status.
    
    Returns:
        Dict with:
        - last_reload: ISO timestamp of last successful reload or None
        - pending_unsafe_changes: List of config paths awaiting restart
        - watch_active: Whether file watching is active
    """
    import datetime
    
    last_reload_dt = None
    if _SettingsHolder._last_reload is not None:
        last_reload_dt = datetime.datetime.fromtimestamp(
            _SettingsHolder._last_reload, tz=datetime.timezone.utc
        ).isoformat()
    
    return {
        "last_reload": last_reload_dt,
        "pending_unsafe_changes": list(_SettingsHolder._pending_unsafe_changes),
        "watch_active": _SettingsHolder._watcher is not None 
            and _SettingsHolder._watcher.is_running,
    }


def get_settings(
    force_reload: bool = False,
    system_config_path: Optional[Path] = None,
    engagement_name: Optional[str] = None,
    engagement_base_path: Optional[Path] = None,
    runtime_overrides: Optional[Dict[str, Any]] = None,
) -> Settings:
    """Get the global Settings singleton.
    
    Thread-safe accessor for the application settings.
    Settings are loaded once and cached for subsequent calls.
    
    Args:
        force_reload: If True, reload settings from files.
        system_config_path: Optional path to system config file.
        engagement_name: Optional engagement name to load.
        engagement_base_path: Optional base path for engagement configs.
        runtime_overrides: Optional runtime overrides.
        
    Returns:
        Settings instance.
        
    Examples:
        >>> # Get singleton
        >>> settings = get_settings()
        
        >>> # Force reload with new config
        >>> settings = get_settings(force_reload=True, runtime_overrides={"paused": True})
    """
    if not force_reload and _SettingsHolder._instance is not None:
        # Check if arguments were provided that would be ignored
        args_provided = any([
            system_config_path is not None,
            engagement_name is not None,
            engagement_base_path is not None,
            runtime_overrides is not None,
        ])
        if args_provided:
            warnings.warn(
                "Arguments provided to get_settings() are ignored because "
                "singleton is already initialized. Use force_reload=True "
                "to apply new configuration.",
                RuntimeWarning,
                stacklevel=2,
            )

    return _SettingsHolder.get(
        force_reload=force_reload,
        system_config_path=system_config_path,
        engagement_name=engagement_name,
        engagement_base_path=engagement_base_path,
        runtime_overrides=runtime_overrides,
    )


def reset_settings() -> None:
    """Reset the settings singleton (for testing)."""
    _SettingsHolder.reset()


# =============================================================================
# Hot Reload Support (Story 2.13)
# =============================================================================

# Config paths that are safe to hot-reload without daemon restart
# These affect runtime behavior but don't require resource re-initialization
HOT_RELOAD_SAFE_PATHS: frozenset[str] = frozenset({
    # Timeouts
    "llm.timeout",
    "intelligence.source_timeout",
    "intelligence.metasploit.pool_size",
    # Rate limits
    "llm.rate_limit",
    # Cache TTLs
    "intelligence.cache_ttl",
    "ntp.sync_ttl",
    # Thresholds
    "ntp.drift_warn_threshold",
    "ntp.drift_error_threshold",
    # Logging
    "logging.level",
    "logging.format",
    "logging.output",
    "logging_config.level",
    "logging_config.format",
    "logging_config.output",
    # Engagement-specific
    "engagement.max_agents",
    "engagement.auto_pause_hours",
})


def diff_configs(old: Settings, new: Settings) -> dict[str, tuple[Any, Any]]:
    """Compare two Settings instances and return changed paths.
    
    Recursively compares nested Pydantic models and returns a dict of
    {path: (old_value, new_value)} for all changed values.
    
    Args:
        old: Original settings instance.
        new: New settings instance to compare.
        
    Returns:
        Dict mapping config paths to (old_value, new_value) tuples.
        Only includes paths where values differ.
        
    Example:
        >>> old = Settings()
        >>> new = Settings(llm=LLMConfig(timeout=300))
        >>> diff = diff_configs(old, new)
        >>> diff  # {'llm.timeout': (180, 300)}
    """
    changes: dict[str, tuple[Any, Any]] = {}
    
    def _compare(old_obj: Any, new_obj: Any, prefix: str = "") -> None:
        """Recursively compare objects and record differences."""
        if isinstance(old_obj, BaseModel) and isinstance(new_obj, BaseModel):
            # Compare Pydantic models field by field
            for field_name in old_obj.model_fields:
                old_value = getattr(old_obj, field_name)
                new_value = getattr(new_obj, field_name)
                path = f"{prefix}.{field_name}" if prefix else field_name
                _compare(old_value, new_value, path)
        else:
            # Compare scalar or non-model values
            if old_obj != new_obj:
                changes[prefix] = (old_obj, new_obj)
    
    _compare(old, new)
    return changes


def is_safe_config_change(
    old: Settings,
    new: Settings,
) -> tuple[bool, list[str]]:
    """Check if config changes are safe for hot reload.
    
    Compares two settings instances and determines if all changes
    are in the HOT_RELOAD_SAFE_PATHS set.
    
    Args:
        old: Original settings instance.
        new: New settings instance to compare.
        
    Returns:
        Tuple of (all_safe, unsafe_paths):
        - all_safe: True if all changes are safe to hot-reload.
        - unsafe_paths: List of paths that require daemon restart.
        
    Example:
        >>> old = Settings()
        >>> new = Settings(llm=LLMConfig(timeout=300))  # Safe change
        >>> all_safe, unsafe = is_safe_config_change(old, new)
        >>> all_safe  # True
        >>> unsafe   # []
    """
    changes = diff_configs(old, new)
    
    if not changes:
        return True, []
    
    unsafe_paths: list[str] = []
    
    for path in changes:
        if path not in HOT_RELOAD_SAFE_PATHS:
            unsafe_paths.append(path)
    
    return len(unsafe_paths) == 0, unsafe_paths

