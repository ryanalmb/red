"""001 - Initial Schema (v2.0.0)

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-01-03

Creates the initial v2.0.0 schema with all 5 tables:
- engagements: Engagement metadata
- agents: Agent state snapshots
- findings: Discovered vulnerabilities
- checkpoints: Checkpoint history
- audit: Audit log entries (stored in separate audit.sqlite per architecture)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all v2.0.0 schema tables."""
    # Create engagements table
    op.create_table(
        "engagements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("scope_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="INITIALIZING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Create agents table with FK to engagements
    op.create_table(
        "agents",
        sa.Column("agent_id", sa.String(36), primary_key=True),
        sa.Column(
            "engagement_id",
            sa.String(36),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("state_json", sa.Text, nullable=False),
        sa.Column("last_action_id", sa.String(36), nullable=True),
        sa.Column("decision_context", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_agents_engagement", "agents", ["engagement_id"])
    op.create_index("idx_agents_type", "agents", ["agent_type"])

    # Create findings table with FK to engagements and agents
    op.create_table(
        "findings",
        sa.Column("finding_id", sa.String(36), primary_key=True),
        sa.Column(
            "engagement_id",
            sa.String(36),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            sa.String(36),
            sa.ForeignKey("agents.agent_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("finding_json", sa.Text, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_findings_engagement", "findings", ["engagement_id"])
    op.create_index("idx_findings_agent", "findings", ["agent_id"])
    op.create_index("idx_findings_timestamp", "findings", ["timestamp"])

    # Create checkpoints table
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "engagement_id",
            sa.String(36),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checkpoint_path", sa.String(512), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_checkpoints_engagement", "checkpoints", ["engagement_id"])

    # Create audit table (NOTE: in production, this is in separate audit.sqlite)
    op.create_table(
        "audit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "engagement_id",
            sa.String(36),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", sa.Text, nullable=True),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
    )
    op.create_index("idx_audit_engagement_ts", "audit", ["engagement_id", "timestamp"])


def downgrade() -> None:
    """Drop all v2.0.0 schema tables."""
    op.drop_table("audit")
    op.drop_table("checkpoints")
    op.drop_table("findings")
    op.drop_table("agents")
    op.drop_table("engagements")
