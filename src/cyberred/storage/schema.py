"""SQLAlchemy Schema Module for Cyber-Red Engagement Database.

This module defines the SQLAlchemy ORM models for engagement data persistence.
Schema version 2.0.0 adds engagements table and foreign key relationships.

Tables:
    - engagements: Engagement metadata (id, name, scope_hash, state)
    - agents: Agent state snapshots with FK to engagement
    - findings: Discovered findings with FK to engagement and agent
    - checkpoints: Checkpoint history tracking
    - audit: Audit log entries (NOTE: stored in separate audit.sqlite per architecture)

Usage:
    from cyberred.storage.schema import (
        Base,
        Engagement,
        Agent,
        Finding,
        Checkpoint,
        AuditEntry,
        create_all_tables,
        CURRENT_SCHEMA_VERSION,
    )

    engine = create_engine("sqlite:///checkpoint.sqlite")
    create_all_tables(engine)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    String,
    Text,
    DateTime,
    Integer,
    Index,
    ForeignKey,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


# Schema version - bump from 1.0.0 to 2.0.0 for new tables and FKs
CURRENT_SCHEMA_VERSION = "2.0.0"


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    pass


class Metadata(Base):
    """Key-value metadata storage.
    
    Legacy storage for engagement-level metadata (version, id, hashes).
    """
    
    __tablename__ = "metadata"
    
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Engagement(Base):
    """Engagement metadata table.

    Primary entity for an engagement session containing scope, state,
    and temporal information.
    """

    __tablename__ = "engagements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="INITIALIZING"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships (cascade delete to child tables)
    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="engagement", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        "Finding", back_populates="engagement", cascade="all, delete-orphan"
    )
    checkpoints: Mapped[list["Checkpoint"]] = relationship(
        "Checkpoint", back_populates="engagement", cascade="all, delete-orphan"
    )
    audit_entries: Mapped[list["AuditEntry"]] = relationship(
        "AuditEntry", back_populates="engagement", cascade="all, delete-orphan"
    )


class Agent(Base):
    """Agent state snapshots table.

    Stores agent state for checkpoint/resume functionality.
    FK to engagement for referential integrity.
    """

    __tablename__ = "agents"
    __table_args__ = (
        Index("idx_agents_engagement", "engagement_id"),
        Index("idx_agents_type", "agent_type"),
    )

    agent_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    last_action_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    decision_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationship back to engagement
    engagement: Mapped["Engagement"] = relationship(
        "Engagement", back_populates="agents"
    )


class Finding(Base):
    """Findings table for discovered vulnerabilities.

    Stores serialized finding data with FK to engagement and optional FK to agent.
    Agent FK uses SET NULL on delete to preserve findings even if agent is removed.
    """

    __tablename__ = "findings"
    __table_args__ = (
        Index("idx_findings_engagement", "engagement_id"),
        Index("idx_findings_agent", "agent_id"),
        Index("idx_findings_timestamp", "timestamp"),
    )

    finding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("agents.agent_id", ondelete="SET NULL"), nullable=True
    )
    finding_json: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    engagement: Mapped["Engagement"] = relationship(
        "Engagement", back_populates="findings"
    )
    agent: Mapped[Optional["Agent"]] = relationship("Agent")


class Checkpoint(Base):
    """Checkpoint history tracking table.

    Records checkpoint operations for audit and recovery purposes.
    """

    __tablename__ = "checkpoints"
    __table_args__ = (Index("idx_checkpoints_engagement", "engagement_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    checkpoint_path: Mapped[str] = mapped_column(String(512), nullable=False)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationship back to engagement
    engagement: Mapped["Engagement"] = relationship(
        "Engagement", back_populates="checkpoints"
    )


class AuditEntry(Base):
    """Audit log entry table.

    NOTE: Per architecture, audit entries are stored in a SEPARATE audit.sqlite
    file, not in checkpoint.sqlite. This schema defines the structure which
    is created by storage/audit.py.

    Includes HMAC signature for tamper evidence.
    """

    __tablename__ = "audit"
    __table_args__ = (Index("idx_audit_engagement_ts", "engagement_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationship back to engagement
    engagement: Mapped["Engagement"] = relationship(
        "Engagement", back_populates="audit_entries"
    )


def create_all_tables(engine: Engine) -> None:
    """Create all schema tables.

    Args:
        engine: SQLAlchemy engine to create tables on.
    """
    Base.metadata.create_all(engine)


def enable_foreign_keys(engine: Engine) -> None:
    """Enable foreign key enforcement for SQLite engines.

    SQLite has foreign keys disabled by default. This function sets up
    an event listener to enable FKs on every connection.

    Args:
        engine: SQLAlchemy engine to configure.
    """

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
        """Set SQLite pragmas on connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
