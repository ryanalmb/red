"""Unit Tests for storage/schema.py module.

Tests for SQLAlchemy ORM models, schema creation, foreign key enforcement,
and index creation per story 2-12 acceptance criteria.
"""

import sqlite3
import pytest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError


class TestSchemaModule:
    """Tests for schema module imports and version."""

    def test_schema_module_imports(self):
        """Verify schema module can be imported."""
        from cyberred.storage.schema import (
            Base,
            Engagement,
            Agent,
            Finding,
            Checkpoint,
            AuditEntry,
            CURRENT_SCHEMA_VERSION,
        )
        assert CURRENT_SCHEMA_VERSION == "2.0.0"

    def test_base_is_declarative_base(self):
        """Verify Base is SQLAlchemy declarative base."""
        from cyberred.storage.schema import Base
        from sqlalchemy.orm import DeclarativeBase
        
        assert issubclass(Base, DeclarativeBase)

    def test_enable_foreign_keys_function(self, tmp_path: Path):
        """Verify enable_foreign_keys sets up FK enforcement event listener."""
        from cyberred.storage.schema import enable_foreign_keys, create_all_tables
        from sqlalchemy import create_engine, text
        
        db_path = tmp_path / "test_fk_enable.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        
        # Enable FKs using our helper function
        enable_foreign_keys(engine)
        
        # Create tables
        create_all_tables(engine)
        
        # Verify FK enforcement is active by checking PRAGMA
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys"))
            fk_enabled = result.fetchone()[0]
            assert fk_enabled == 1, "Foreign keys should be enabled"


class TestAllTablesCreated:
    """Test: test_all_tables_created — verify 5 tables exist (AC #3, #7)."""

    @pytest.fixture
    def engine_with_schema(self, tmp_path: Path):
        """Create engine with schema tables."""
        from cyberred.storage.schema import Base, create_all_tables
        
        db_path = tmp_path / "test.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        create_all_tables(engine)
        return engine

    def test_all_tables_created(self, engine_with_schema):
        """Verify all 5 tables are created."""
        from cyberred.storage.schema import (
            Engagement,
            Agent,
            Finding,
            Checkpoint,
            AuditEntry,
        )
        
        inspector = inspect(engine_with_schema)
        tables = inspector.get_table_names()
        
        assert "engagements" in tables
        assert "agents" in tables
        assert "findings" in tables
        assert "checkpoints" in tables
        assert "audit" in tables
        assert len([t for t in tables if not t.startswith("alembic")]) >= 5


class TestForeignKeyEnforcement:
    """Test: test_foreign_key_enforcement — FK violations raise error (AC #4, #7)."""

    @pytest.fixture
    def session_with_schema(self, tmp_path: Path):
        """Create session with schema tables and FK enforcement."""
        from cyberred.storage.schema import Base, create_all_tables
        
        db_path = tmp_path / "test_fk.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        
        # Enable FK enforcement for SQLite
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()
        
        create_all_tables(engine)
        
        # Create new engine with FK enforcement in connect_args
        engine_fk = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False}
        )
        
        # Enable FKs via event listener
        from sqlalchemy import event
        
        @event.listens_for(engine_fk, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        session = Session(engine_fk)
        yield session
        session.close()

    def test_agent_requires_valid_engagement(self, session_with_schema):
        """Verify agent FK to engagement is enforced."""
        from cyberred.storage.schema import Agent
        
        # Try to insert agent with non-existent engagement_id
        agent = Agent(
            agent_id="agent-123",
            engagement_id="nonexistent-engagement",
            agent_type="recon",
            state_json="{}",
        )
        session_with_schema.add(agent)
        
        with pytest.raises(IntegrityError):
            session_with_schema.commit()

    def test_finding_requires_valid_engagement(self, session_with_schema):
        """Verify finding FK to engagement is enforced."""
        from cyberred.storage.schema import Finding
        from datetime import datetime, timezone
        
        finding = Finding(
            finding_id="finding-123",
            engagement_id="nonexistent-engagement",
            finding_json="{}",
            timestamp=datetime.now(timezone.utc),
        )
        session_with_schema.add(finding)
        
        with pytest.raises(IntegrityError):
            session_with_schema.commit()


class TestIndexesCreated:
    """Test: test_indexes_created — required indexes exist (AC #5, #7)."""

    @pytest.fixture
    def engine_with_schema(self, tmp_path: Path):
        """Create engine with schema tables."""
        from cyberred.storage.schema import Base, create_all_tables
        
        db_path = tmp_path / "test_idx.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        create_all_tables(engine)
        return engine

    def test_indexes_created(self, engine_with_schema):
        """Verify required indexes exist."""
        inspector = inspect(engine_with_schema)
        
        # Check agents table indexes
        agent_indexes = {idx["name"] for idx in inspector.get_indexes("agents")}
        assert "idx_agents_engagement" in agent_indexes
        assert "idx_agents_type" in agent_indexes
        
        # Check findings table indexes
        findings_indexes = {idx["name"] for idx in inspector.get_indexes("findings")}
        assert "idx_findings_engagement" in findings_indexes
        assert "idx_findings_agent" in findings_indexes
        assert "idx_findings_timestamp" in findings_indexes
        
        # Check checkpoints table indexes
        checkpoints_indexes = {idx["name"] for idx in inspector.get_indexes("checkpoints")}
        assert "idx_checkpoints_engagement" in checkpoints_indexes
        
        # Check audit table indexes
        audit_indexes = {idx["name"] for idx in inspector.get_indexes("audit")}
        assert "idx_audit_engagement_ts" in audit_indexes


class TestEngagementCascadeDelete:
    """Test: test_engagement_cascade_delete — deleting engagement cascades (AC #4)."""

    @pytest.fixture
    def session_with_data(self, tmp_path: Path):
        """Create session with schema and test data."""
        from cyberred.storage.schema import (
            Base,
            create_all_tables,
            Engagement,
            Agent,
            Finding,
        )
        from datetime import datetime, timezone
        from sqlalchemy import event
        
        db_path = tmp_path / "test_cascade.sqlite"
        engine = create_engine(f"sqlite:///{db_path}")
        
        # Enable FK enforcement
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        create_all_tables(engine)
        session = Session(engine)
        
        # Create engagement
        engagement = Engagement(
            id="eng-123",
            name="Test Engagement",
            scope_hash="abc123",
            state="RUNNING",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(engagement)
        session.commit()
        
        # Create agent linked to engagement
        agent = Agent(
            agent_id="agent-456",
            engagement_id="eng-123",
            agent_type="recon",
            state_json="{}",
        )
        session.add(agent)
        session.commit()
        
        # Create finding linked to engagement
        finding = Finding(
            finding_id="finding-789",
            engagement_id="eng-123",
            agent_id="agent-456",
            finding_json="{}",
            timestamp=datetime.now(timezone.utc),
        )
        session.add(finding)
        session.commit()
        
        yield session
        session.close()

    def test_engagement_cascade_delete(self, session_with_data):
        """Verify deleting engagement cascades to agents and findings."""
        from cyberred.storage.schema import Engagement, Agent, Finding
        
        # Verify data exists
        assert session_with_data.query(Agent).count() == 1
        assert session_with_data.query(Finding).count() == 1
        
        # Delete engagement
        engagement = session_with_data.query(Engagement).filter_by(id="eng-123").first()
        session_with_data.delete(engagement)
        session_with_data.commit()
        
        # Verify cascade
        assert session_with_data.query(Agent).count() == 0
        assert session_with_data.query(Finding).count() == 0
