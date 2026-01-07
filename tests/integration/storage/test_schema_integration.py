"""Integration Tests for Storage Schema.

Tests for full engagement lifecycle and audit trail integrity
per story 2-12 acceptance criteria.
"""

import pytest
import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

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


@pytest.fixture
def engagement_db(tmp_path: Path):
    """Create a fully configured engagement database."""
    db_path = tmp_path / "engagement.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    
    # Enable FK enforcement
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    
    create_all_tables(engine)
    
    session = Session(engine)
    yield session, db_path
    session.close()


@pytest.mark.integration
class TestSchemaIntegration:
    """Integration tests for the schema module."""

    def test_full_engagement_lifecycle_with_schema(self, engagement_db):
        """Test: test_full_engagement_lifecycle_with_schema — complete CRUD cycle."""
        session, db_path = engagement_db
        
        # 1. Create Engagement (INITIALIZING -> RUNNING)
        engagement = Engagement(
            id="eng-integration-001",
            name="Integration Test Engagement",
            scope_hash=hashlib.sha256(b"192.168.1.0/24").hexdigest(),
            state="INITIALIZING",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(engagement)
        session.commit()
        
        # Verify engagement created
        loaded = session.query(Engagement).filter_by(id="eng-integration-001").first()
        assert loaded is not None
        assert loaded.state == "INITIALIZING"
        
        # 2. Update state to RUNNING
        loaded.state = "RUNNING"
        loaded.updated_at = datetime.now(timezone.utc)
        session.commit()
        
        # 3. Create agents
        for i in range(3):
            agent = Agent(
                agent_id=f"agent-{i:03d}",
                engagement_id="eng-integration-001",
                agent_type=["recon", "exploit", "postex"][i],
                state_json=f'{{"iteration": {i}}}',
            )
            session.add(agent)
        session.commit()
        
        # Verify agents
        agents = session.query(Agent).filter_by(engagement_id="eng-integration-001").all()
        assert len(agents) == 3
        
        # 4. Create findings
        for i in range(5):
            finding = Finding(
                finding_id=f"find-{i:03d}",
                engagement_id="eng-integration-001",
                agent_id=f"agent-{i % 3:03d}",
                finding_json=f'{{"type": "vuln-{i}"}}',
                timestamp=datetime.now(timezone.utc),
            )
            session.add(finding)
        session.commit()
        
        # Verify findings
        findings = session.query(Finding).filter_by(engagement_id="eng-integration-001").all()
        assert len(findings) == 5
        
        # 5. Record a checkpoint
        checkpoint = Checkpoint(
            engagement_id="eng-integration-001",
            checkpoint_path=str(db_path),
            signature=hashlib.sha256(b"checkpoint-content").hexdigest(),
            created_at=datetime.now(timezone.utc),
        )
        session.add(checkpoint)
        session.commit()
        
        # 6. Pause engagement
        loaded = session.query(Engagement).filter_by(id="eng-integration-001").first()
        loaded.state = "PAUSED"
        loaded.updated_at = datetime.now(timezone.utc)
        session.commit()
        
        # 7. Resume and complete
        loaded.state = "COMPLETED"
        loaded.updated_at = datetime.now(timezone.utc)
        session.commit()
        
        # Verify final state
        final = session.query(Engagement).filter_by(id="eng-integration-001").first()
        assert final.state == "COMPLETED"
        assert len(final.agents) == 3
        assert len(final.findings) == 5
        assert len(final.checkpoints) == 1
        
        # 8. Delete engagement (should cascade)
        session.delete(final)
        session.commit()
        
        # Verify cascade
        assert session.query(Engagement).count() == 0
        assert session.query(Agent).count() == 0
        assert session.query(Finding).count() == 0
        assert session.query(Checkpoint).count() == 0

    def test_audit_trail_integrity(self, engagement_db):
        """Test: test_audit_trail_integrity — verify HMAC signatures."""
        session, _ = engagement_db
        
        # Create engagement for audit entries
        engagement = Engagement(
            id="eng-audit-test",
            name="Audit Test",
            scope_hash="testhash",
            state="RUNNING",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(engagement)
        session.commit()
        
        # Define a secret key for HMAC (in production this would be from config)
        secret_key = b"test-hmac-secret-key"
        
        # Create audit entries with HMAC signatures
        events = [
            ("engagement_start", '{"config": "/path/to/config.yaml"}', "operator-1"),
            ("auth_request", '{"target": "192.168.1.5", "action": "exploit"}', "system"),
            ("auth_response", '{"approved": true}', "operator-1"),
            ("finding_discovered", '{"type": "sqli", "severity": "high"}', "system"),
            ("engagement_pause", '{"reason": "manual"}', "operator-1"),
        ]
        
        for event_type, event_data, actor in events:
            # Create message to sign
            msg = f"{event_type}:{event_data}:{actor}"
            signature = hmac.new(secret_key, msg.encode(), hashlib.sha256).hexdigest()
            
            entry = AuditEntry(
                engagement_id="eng-audit-test",
                event_type=event_type,
                event_data=event_data,
                actor=actor,
                timestamp=datetime.now(timezone.utc),
                signature=signature,
            )
            session.add(entry)
        
        session.commit()
        
        # Verify all entries were created
        entries = session.query(AuditEntry).filter_by(
            engagement_id="eng-audit-test"
        ).order_by(AuditEntry.id).all()
        
        assert len(entries) == 5
        
        # Verify each signature
        for entry in entries:
            msg = f"{entry.event_type}:{entry.event_data}:{entry.actor}"
            expected_sig = hmac.new(secret_key, msg.encode(), hashlib.sha256).hexdigest()
            assert entry.signature == expected_sig, f"Signature mismatch for {entry.event_type}"
        
        # Test tamper detection - modify data and verify signature fails
        tampered_entry = entries[2]  # auth_response
        original_data = tampered_entry.event_data
        tampered_data = '{"approved": false}'  # Tampered!
        
        # Compute what the signature SHOULD be for tampered data
        tampered_msg = f"{tampered_entry.event_type}:{tampered_data}:{tampered_entry.actor}"
        tampered_sig = hmac.new(secret_key, tampered_msg.encode(), hashlib.sha256).hexdigest()
        
        # Original signature should NOT match tampered data
        assert tampered_entry.signature != tampered_sig, "Tamper detection failed"
