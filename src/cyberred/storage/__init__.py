"""Storage module for Cyber-Red.

Provides checkpoint persistence, schema management, and Redis client for
engagement state and stigmergic coordination.
"""

from cyberred.storage.checkpoint import (
    CheckpointManager,
    CheckpointData,
    SCHEMA_VERSION,
)
from cyberred.storage.schema import (
    Base,
    Engagement,
    Agent,
    Finding,
    Checkpoint,
    AuditEntry,
    create_all_tables,
    enable_foreign_keys,
    CURRENT_SCHEMA_VERSION,
)
from cyberred.storage.redis_client import (
    RedisClient,
    PubSubSubscription,
    HealthStatus,
)

__all__ = [
    # Checkpoint manager
    "CheckpointManager",
    "CheckpointData",
    "SCHEMA_VERSION",
    # Schema models
    "Base",
    "Engagement",
    "Agent",
    "Finding",
    "Checkpoint",
    "AuditEntry",
    "create_all_tables",
    "enable_foreign_keys",
    "CURRENT_SCHEMA_VERSION",
    # Redis client
    "RedisClient",
    "PubSubSubscription",
    "HealthStatus",
]
