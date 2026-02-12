"""Core module for Cyber-Red.

Exports the core components: exceptions, data models, and configuration.
"""

from cyberred.core.exceptions import (
    CyberRedError,
    ScopeViolationError,
    KillSwitchTriggered,
    ConfigurationError,
    CheckpointIntegrityError,
    DecryptionError,
    IntegrityError,
    # LLM Exceptions (Story 3.5)
    LLMError,
    LLMProviderUnavailable,
    LLMRateLimitExceeded,
    LLMTimeoutError,
    LLMResponseError,
    # Tool Selection Exceptions (Story 7.1.v2)
    ToolSelectionError,
)
from cyberred.core.models import (
    Finding,
    AgentAction,
    ToolResult,
    ToolSelectionContext,
    ToolSelection,
)
from cyberred.core.config import (
    get_settings,
    reset_settings,
    Settings,
    SystemConfig,
    EngagementConfig,
    RuntimeConfig,
    RedisConfig,
    LLMConfig,
    StorageConfig,
    SecurityConfig,
    LoggingConfig,
    MetricsConfig,
    IntelligenceConfig,
    RAGConfig,
)
from cyberred.core.time import (
    TrustedTime,
    now,
    sign_timestamp,
    verify_timestamp_signature,
)
from cyberred.core.keystore import (
    Keystore,
    derive_key,
    encrypt,
    decrypt,
    generate_salt,
)
from cyberred.core.ca_store import CAStore
from cyberred.core.killswitch import KillSwitch
from cyberred.core.events import EventBus, ChannelNameError
from cyberred.core.sharding import (
    ShardedTopic,
    ShardedEventBus,
    ShardAggregator,
    AggregatedBatch,
    DEFAULT_SHARD_COUNT,
    AGGREGATOR_BATCH_MS,
)

__all__ = [
    # Exceptions
    "CyberRedError",
    "ScopeViolationError",
    "KillSwitchTriggered",
    "ConfigurationError",
    "CheckpointIntegrityError",
    "DecryptionError",
    "IntegrityError",
    # LLM Exceptions (Story 3.5)
    "LLMError",
    "LLMProviderUnavailable",
    "LLMRateLimitExceeded",
    "LLMTimeoutError",
    "LLMResponseError",
    # Tool Selection Exceptions (Story 7.1.v2)
    "ToolSelectionError",
    # Data Models
    "Finding",
    "AgentAction",
    "ToolResult",
    "ToolSelectionContext",
    "ToolSelection",
    # Configuration
    "get_settings",
    "reset_settings",
    "Settings",
    "SystemConfig",
    "EngagementConfig",
    "RuntimeConfig",
    "RedisConfig",
    "LLMConfig",
    "StorageConfig",
    "SecurityConfig",
    "LoggingConfig",
    "MetricsConfig",
    "IntelligenceConfig",
    "RAGConfig",
    # Time (NTP synchronization)
    "TrustedTime",
    "now",
    "sign_timestamp",
    "verify_timestamp_signature",
    # Keystore (PBKDF2 + AES-256-GCM)
    "Keystore",
    "derive_key",
    "encrypt",
    "decrypt",
    "generate_salt",
    # CA Store (Certificate Authority)
    "CAStore",
    # Kill Switch (Safety-Critical)
    "KillSwitch",
    # Event Bus (Pub/Sub)
    "EventBus",
    "ChannelNameError",
    # Sharding (Story 7.13)
    "ShardedTopic",
    "ShardedEventBus",
    "ShardAggregator",
    "AggregatedBatch",
    "DEFAULT_SHARD_COUNT",
    "AGGREGATOR_BATCH_MS",
]
