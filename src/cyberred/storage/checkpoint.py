"""Checkpoint Manager for engagement persistence.

Provides SQLite-based checkpointing for engagement state that persists
across daemon restarts. This is the "cold state" storage mechanism,
contrasting with in-memory "hot state" during pause/resume operations.

Key Features:
- SQLite with WAL mode for concurrent reads
- SHA-256 integrity verification
- Scope hash validation on restore
- Atomic write operations

Usage:
    from cyberred.storage import CheckpointManager
    
    manager = CheckpointManager(base_path=Path("~/.cyber-red"))
    
    # Save checkpoint
    checkpoint_path = await manager.save(engagement_context)
    
    # Load checkpoint
    data = await manager.load(checkpoint_path)
    
    # Verify integrity
    is_valid = manager.verify(checkpoint_path)
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import structlog

from cyberred.core.hashing import calculate_file_hash, calculate_bytes_hash
from cyberred.core.exceptions import CheckpointIntegrityError
from sqlalchemy import create_engine
from cyberred.storage.schema import Base, enable_foreign_keys, CURRENT_SCHEMA_VERSION

log = structlog.get_logger()

# Schema version - now imported from schema module
# CURRENT_SCHEMA_VERSION = "2.0.0" is the authoritative source
SCHEMA_VERSION = CURRENT_SCHEMA_VERSION


@dataclass
class AgentState:
    """Serialized agent state."""
    agent_id: str
    agent_type: str
    state: dict[str, Any]
    last_action_id: Optional[str] = None
    decision_context: Optional[str] = None


@dataclass
class Finding:
    """Serialized finding."""
    finding_id: str
    data: dict[str, Any]
    agent_id: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class CheckpointData:
    """Data structure for checkpoint contents."""
    engagement_id: str
    scope_hash: str
    created_at: datetime
    schema_version: str
    agents: list[AgentState] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


class CheckpointScopeChangedError(CheckpointIntegrityError):
    """Raised when scope file has changed since checkpoint creation.
    
    This is a security-critical check. If the scope has changed,
    the operator must explicitly confirm the restore operation.
    
    Attributes:
        checkpoint_path: Path to the checkpoint file.
        expected_scope_hash: Hash stored in checkpoint.
        actual_scope_hash: Current scope file hash.
    """
    
    def __init__(
        self,
        checkpoint_path: str,
        expected_scope_hash: str,
        actual_scope_hash: str,
        message: Optional[str] = None,
    ) -> None:
        self.expected_scope_hash = expected_scope_hash
        self.actual_scope_hash = actual_scope_hash
        
        if message is None:
            message = (
                f"Scope file has changed since checkpoint was created. "
                f"Expected hash: {expected_scope_hash[:16]}..., "
                f"Actual hash: {actual_scope_hash[:16]}..."
            )
        
        super().__init__(
            checkpoint_path=checkpoint_path,
            verification_type="scope",
            message=message,
        )


class IncompatibleSchemaError(CheckpointIntegrityError):
    """Raised when checkpoint schema version is newer than current code.
    
    This prevents loading checkpoints created by newer versions of the
    software that may have incompatible schema changes.
    
    Attributes:
        checkpoint_version: Version in the checkpoint file.
        current_version: Version supported by this code.
    """
    
    def __init__(
        self,
        checkpoint_path: str,
        checkpoint_version: str,
        current_version: str,
        message: Optional[str] = None,
    ) -> None:
        self.checkpoint_version = checkpoint_version
        self.current_version = current_version
        
        if message is None:
            message = (
                f"Checkpoint was created with schema version {checkpoint_version}, "
                f"but current code only supports up to {current_version}. "
                f"Please upgrade your Cyber-Red installation."
            )
        
        super().__init__(
            checkpoint_path=checkpoint_path,
            verification_type="schema_version",
            message=message,
        )


class CheckpointJSONEncoder(json.JSONEncoder):
    """Robust JSON encoder for agent states."""
    
    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime,)):
            return o.isoformat()
        if isinstance(o, (set, frozenset)):
            return list(o)
        if isinstance(o, bytes):
            return o.hex()
        return super().default(o)


class CheckpointManager:
    """Manages checkpoint persistence for engagements.
    
    Checkpoints are stored in SQLite databases with WAL mode enabled
    for concurrent read access. Each engagement has its own checkpoint
    file at: {base_path}/engagements/{id}/checkpoint.sqlite
    
    Attributes:
        base_path: Root path for engagement storage.
    """
    
    def __init__(self, base_path: Path) -> None:
        """Initialize CheckpointManager.
        
        Args:
            base_path: Root path for storage (e.g., ~/.cyber-red).
        """
        self._base_path = Path(base_path).expanduser()
        self._engagements_dir = self._base_path / "engagements"
    
    @property
    def base_path(self) -> Path:
        """Root storage path."""
        return self._base_path
    
    def _get_checkpoint_path(self, engagement_id: str) -> Path:
        """Get checkpoint file path for an engagement.
        
        Args:
            engagement_id: Engagement identifier.
            
        Returns:
            Path to checkpoint.sqlite file.
        """
        return self._engagements_dir / engagement_id / "checkpoint.sqlite"
    
    def _create_connection(self, db_path: Path) -> sqlite3.Connection:
        """Create SQLite connection with WAL mode.
        
        Args:
            db_path: Path to database file.
            
        Returns:
            SQLite connection with WAL mode enabled.
        """
        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_schema(self, db_path: Path) -> None:
        """Initialize database schema using SQLAlchemy.
        
        Args:
            db_path: Path to database file.
        """
        engine = create_engine(f"sqlite:///{db_path}")
        enable_foreign_keys(engine)
        Base.metadata.create_all(engine)
        engine.dispose()
    
    def _set_metadata(
        self,
        conn: sqlite3.Connection,
        key: str,
        value: str,
    ) -> None:
        """Set metadata value.
        
        Args:
            conn: SQLite connection.
            key: Metadata key.
            value: Metadata value.
        """
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
    
    def _get_metadata(
        self,
        conn: sqlite3.Connection,
        key: str,
    ) -> Optional[str]:
        """Get metadata value.
        
        Args:
            conn: SQLite connection.
            key: Metadata key.
            
        Returns:
            Metadata value or None if not found.
        """
        cursor = conn.execute(
            "SELECT value FROM metadata WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        return row["value"] if row else None
    
    def _calculate_content_signature(
        self,
        engagement_id: str,
        scope_hash: str,
        created_at: str,
        agents: list[AgentState],
        findings: list[Finding],
    ) -> str:
        """Calculate a deterministic signature based on checkpoint content.
        
        This uses logical content hashing rather than file binary hashing,
        which is more robust for SQLite databases.
        """
        # Sort lists to ensure determinism
        agents_sorted = sorted(agents, key=lambda x: x.agent_id)
        findings_sorted = sorted(findings, key=lambda x: x.finding_id)
        
        data = {
            "engagement_id": engagement_id,
            "scope_hash": scope_hash,
            "created_at": created_at,
            "agents": [
                {
                    "id": a.agent_id,
                    "type": a.agent_type,
                    "state": a.state,
                    # We serialize context to JSON string to match DB storage
                    "context": json.dumps(a.decision_context, sort_keys=True, cls=CheckpointJSONEncoder), 
                    "action": a.last_action_id
                } for a in agents_sorted
            ],
            "findings": [
                {
                    "id": f.finding_id,
                    "json": json.dumps(f.data, sort_keys=True, cls=CheckpointJSONEncoder),
                    "agent": f.agent_id,
                    "ts": f.timestamp.isoformat() if f.timestamp else created_at
                } for f in findings_sorted
            ]
        }
        
        # Calculate SHA-256 of canonical JSON representation
        json_bytes = json.dumps(data, sort_keys=True, cls=CheckpointJSONEncoder).encode("utf-8")
        import hashlib
        return hashlib.sha256(json_bytes).hexdigest()

    async def save(
        self,
        engagement_id: str,
        scope_path: Optional[Path] = None,
        agents: Optional[list[AgentState]] = None,
        findings: Optional[list[Finding]] = None,
    ) -> Path:
        """Save engagement state to checkpoint atomically.
        
        Creates new checkpoint in temp file, writes data, signs it,
        and atomically renames to final path to prevent data loss.
        """
        agents = agents or []
        findings = findings or []
        
        final_path = self._get_checkpoint_path(engagement_id)
        # Write to temp file first to ensure atomicity
        temp_path = final_path.with_suffix(".sqlite.tmp")
        
        # Ensure parent dir exists
        final_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove old temp file if exists
        if temp_path.exists():
            temp_path.unlink()
        
        conn = None
        try:
            # Initialize schema first using SQLAlchemy
            self._initialize_schema(temp_path)
            
            # Open connection for data insertion
            conn = self._create_connection(temp_path)
            
            # Calculate scope hash
            scope_hash = ""
            if scope_path and Path(scope_path).exists():
                scope_hash = calculate_file_hash(scope_path)
            
            # Store metadata
            created_at = datetime.now(timezone.utc).isoformat()
            self._set_metadata(conn, "engagement_id", engagement_id)
            self._set_metadata(conn, "scope_hash", scope_hash)
            self._set_metadata(conn, "created_at", created_at)
            self._set_metadata(conn, "schema_version", SCHEMA_VERSION)
            
            # Store engagement record (required for FKs)
            conn.execute(
                """
                INSERT INTO engagements
                (id, name, scope_hash, state, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    engagement_id,
                    f"Engagement {engagement_id}", # Default name
                    scope_hash,
                    "RUNNING", # Default state
                    created_at,
                    created_at
                )
            )
            
            # Store agents
            for agent in agents:
                conn.execute(
                    """
                    INSERT INTO agents 
                    (agent_id, engagement_id, agent_type, state_json, last_action_id, decision_context, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        agent.agent_id,
                        engagement_id,
                        agent.agent_type,
                        json.dumps(agent.state, cls=CheckpointJSONEncoder),
                        agent.last_action_id,
                        json.dumps(agent.decision_context, cls=CheckpointJSONEncoder), # Fix: Serialize dict
                        created_at,
                    ),
                )
            
            # Store findings
            for finding in findings:
                timestamp = finding.timestamp.isoformat() if finding.timestamp else created_at
                conn.execute(
                    """
                    INSERT INTO findings
                    (finding_id, engagement_id, finding_json, agent_id, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        finding.finding_id,
                        engagement_id,
                        json.dumps(finding.data, cls=CheckpointJSONEncoder),
                        finding.agent_id,
                        timestamp,
                    ),
                )
            
            # Calculate logical signature
            signature = self._calculate_content_signature(
                engagement_id, scope_hash, created_at, agents, findings
            )
            self._set_metadata(conn, "signature", signature)
            
            conn.commit()
            conn.close()
            
            # Atomic move
            temp_path.replace(final_path)
            
            log.info(
                "checkpoint_saved",
                engagement_id=engagement_id,
                checkpoint_path=str(final_path),
                agent_count=len(agents),
                finding_count=len(findings),
            )
            
            return final_path
            
        except Exception:
            if conn:
                conn.close()
            if temp_path.exists():
                temp_path.unlink()
            raise

    async def load(
        self,
        checkpoint_path: Path,
        scope_path: Optional[Path] = None,
        verify_scope: bool = True,
    ) -> CheckpointData:
        """Load checkpoint data from file.
        
        Verifies integrity signature before loading.
        Optionally verifies scope hash matches current scope file.
        """
        checkpoint_path = Path(checkpoint_path)
        
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        
        conn = self._create_connection(checkpoint_path)
        try:
            # 1. Load all data first
            engagement_id = self._get_metadata(conn, "engagement_id") or ""
            scope_hash = self._get_metadata(conn, "scope_hash") or ""
            created_at_str = self._get_metadata(conn, "created_at") or ""
            schema_version = self._get_metadata(conn, "schema_version") or ""
            signature = self._get_metadata(conn, "signature") or ""
            
            # Version checking (Task 10)
            if schema_version:
                # Parse version components
                try:
                    stored_major, stored_minor, stored_patch = map(int, schema_version.split("."))
                    current_major, current_minor, current_patch = map(int, SCHEMA_VERSION.split("."))
                    
                    # If checkpoint version is newer than current, raise error
                    stored_tuple = (stored_major, stored_minor, stored_patch)
                    current_tuple = (current_major, current_minor, current_patch)
                    
                    if stored_tuple > current_tuple:
                        raise IncompatibleSchemaError(
                            checkpoint_path=str(checkpoint_path),
                            checkpoint_version=schema_version,
                            current_version=SCHEMA_VERSION,
                        )
                    
                    # Log version info
                    if stored_tuple < current_tuple:
                        log.info(
                            "checkpoint_schema_upgrade_available",
                            stored_version=schema_version,
                            current_version=SCHEMA_VERSION,
                            checkpoint_path=str(checkpoint_path),
                        )
                except ValueError:
                    log.warning(
                        "checkpoint_invalid_schema_version",
                        schema_version=schema_version,
                        checkpoint_path=str(checkpoint_path),
                    )
            
            created_at = datetime.fromisoformat(created_at_str) if created_at_str else datetime.now(timezone.utc)
            
            # Load agents
            agents = []
            cursor = conn.execute("SELECT * FROM agents")
            for row in cursor:
                # Handle possible JSON/String mismatch for decision_context if old data (shouldn't exist in cold run)
                # Ensure we handle the text from DB
                d_context = row["decision_context"]
                if isinstance(d_context, str):
                    d_context = json.loads(d_context)
                    
                agents.append(AgentState(
                    agent_id=row["agent_id"],
                    agent_type=row["agent_type"],
                    state=json.loads(row["state_json"]),
                    last_action_id=row["last_action_id"],
                    decision_context=d_context,
                ))
            
            # Load findings
            findings = []
            cursor = conn.execute("SELECT * FROM findings")
            for row in cursor:
                findings.append(Finding(
                    finding_id=row["finding_id"],
                    data=json.loads(row["finding_json"]),
                    agent_id=row["agent_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
                ))

            # 2. Verify Integrity (Content-based)
            calculated_sig = self._calculate_content_signature(
                engagement_id, scope_hash, created_at_str, agents, findings
            )
            
            if signature != calculated_sig:
                log.warning(
                    "checkpoint_signature_mismatch",
                    path=str(checkpoint_path),
                    stored=signature,
                    calculated=calculated_sig,
                )
                raise CheckpointIntegrityError(
                    checkpoint_path=str(checkpoint_path),
                    verification_type="signature",
                    message="Checkpoint signature mismatch - file content modified",
                )
            
            # 3. Verify Scope
            if verify_scope and scope_path and scope_hash:
                current_scope_path = Path(scope_path)
                if current_scope_path.exists():
                    current_hash = calculate_file_hash(current_scope_path)
                    if current_hash != scope_hash:
                        raise CheckpointScopeChangedError(
                            checkpoint_path=str(checkpoint_path),
                            expected_scope_hash=scope_hash,
                            actual_scope_hash=current_hash,
                        )
            
            log.info(
                "checkpoint_loaded",
                engagement_id=engagement_id,
                checkpoint_path=str(checkpoint_path),
                agent_count=len(agents),
                finding_count=len(findings),
            )
            
            return CheckpointData(
                engagement_id=engagement_id,
                scope_hash=scope_hash,
                created_at=created_at,
                schema_version=schema_version,
                agents=agents,
                findings=findings,
            )
            
        finally:
            conn.close()

    def verify(self, checkpoint_path: Path) -> bool:
        """Verify checkpoint file integrity.
        
        Loads data and recalculates signature to verify content integrity.
        """
        try:
            # We reuse load logic but catch errors
            # To avoid implementing logic twice, we just call load() 
            # and ignore result. This essentially performs the verification.
            # However, we need to pass a fake scope path to skip scope verification
            # if we only want signature verification.
            # Or we can split verify logic.
            # For simplicity: Load without scope verify.
            # Using asyncio.run here is blocking, but this method is sync.
            # Actually load is async. We can't call async from sync easily without loop.
            
            # Re-implement minimal sync verification logic
            checkpoint_path = Path(checkpoint_path)
            if not checkpoint_path.exists():
                return False
                
            conn = self._create_connection(checkpoint_path)
            try:
                engagement_id = self._get_metadata(conn, "engagement_id")
                scope_hash = self._get_metadata(conn, "scope_hash")
                created_at_str = self._get_metadata(conn, "created_at")
                signature = self._get_metadata(conn, "signature")
                
                if not all([engagement_id, created_at_str, signature]): # scope_hash can be empty
                    return False
                    
                # Agents
                agents = []
                cursor = conn.execute("SELECT * FROM agents")
                for row in cursor:
                    d_context = row["decision_context"]
                    if isinstance(d_context, str):
                        d_context = json.loads(d_context)
                    agents.append(AgentState(
                        agent_id=row["agent_id"],
                        agent_type=row["agent_type"],
                        state=json.loads(row["state_json"]),
                        last_action_id=row["last_action_id"],
                        decision_context=d_context,
                    ))
                
                # Findings
                findings = []
                cursor = conn.execute("SELECT * FROM findings")
                for row in cursor:
                    findings.append(Finding(
                        finding_id=row["finding_id"],
                        data=json.loads(row["finding_json"]),
                        agent_id=row["agent_id"],
                        timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
                    ))
                    
                calc_sig = self._calculate_content_signature(
                    engagement_id, scope_hash, created_at_str, agents, findings
                )
                
                return signature == calc_sig
                
            finally:
                conn.close()
                
        except Exception as e:
            log.warning("checkpoint_verify_error", error=str(e))
            return False
    
    async def delete(self, engagement_id: str) -> bool:
        """Delete checkpoint for an engagement.
        
        Args:
            engagement_id: Engagement identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        checkpoint_path = self._get_checkpoint_path(engagement_id)
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            log.info("checkpoint_deleted", engagement_id=engagement_id, path=str(checkpoint_path))
            return True
        return False

    def list_checkpoints(self) -> list[tuple[str, Path]]:
        """List all available checkpoints.
        
        Returns:
            List of (engagement_id, checkpoint_path) tuples.
        """
        checkpoints = []
        
        if not self._engagements_dir.exists():
            return checkpoints
        
        for engagement_dir in self._engagements_dir.iterdir():
            if engagement_dir.is_dir():
                checkpoint_path = engagement_dir / "checkpoint.sqlite"
                if checkpoint_path.exists():
                    checkpoints.append((engagement_dir.name, checkpoint_path))
        
        return checkpoints
