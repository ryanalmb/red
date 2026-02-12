"""Storage module for Cyber-Red.

Provides checkpoint persistence, schema management, and Redis client for
engagement state and stigmergic coordination.
"""

from cyberred.storage.checkpoint import (
    CheckpointManager,
    CheckpointData,
    SCHEMA_VERSION,
    AgentState,
    Finding,
    CheckpointScopeChangedError,
    IncompatibleSchemaError,
)
from cyberred.storage.checkpoint_queue import (
    AsyncCheckpointQueue,
    CheckpointRequest,
)
from cyberred.storage.checkpoint_scheduler import (
    CheckpointScheduler,
    CheckpointTrigger,
    should_trigger_checkpoint,
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
from cyberred.storage.evidence_store import (
    EvidenceStore,
    EvidenceItem,
    EvidenceType,
)
from cyberred.storage.operator_audit import (
    OperatorAction,
    OperatorAuditEntry,
    OperatorAuditLog,
    get_operator_audit_log,
    set_operator_audit_log,
    init_operator_audit_log,
)
from cyberred.storage.report_generator import (
    HTMLReportGenerator,
    MarkdownReportGenerator,
    ReportData,
    SignedReport,
    TimelineEvent,
    embed_screenshot,
    embed_screenshots_in_html,
    save_report,
    save_signed_report,
    sign_report,
    verify_signature,
)
from cyberred.storage.sarif_exporter import (
    SARIFExporter,
    validate_sarif,
)
from cyberred.storage.stix_exporter import (
    STIXExporter,
    validate_stix,
)
from cyberred.storage.csv_excel_exporter import (
    CSVExporter,
    ExcelExporter,
    export_findings_csv,
    export_findings_xlsx,
)

__all__ = [
    # Checkpoint manager
    "CheckpointManager",
    "CheckpointData",
    "SCHEMA_VERSION",
    "AgentState",
    "Finding",
    "CheckpointScopeChangedError",
    "IncompatibleSchemaError",
    # Checkpoint queue (Story 13.3)
    "AsyncCheckpointQueue",
    "CheckpointRequest",
    # Checkpoint scheduler (Story 13.3)
    "CheckpointScheduler",
    "CheckpointTrigger",
    "should_trigger_checkpoint",
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
    # Evidence Store (Story 13.1)
    "EvidenceStore",
    "EvidenceItem",
    "EvidenceType",
    # Operator Audit Log (Story 13.2)
    "OperatorAction",
    "OperatorAuditEntry",
    "OperatorAuditLog",
    "get_operator_audit_log",
    "set_operator_audit_log",
    "init_operator_audit_log",
    # Report Generator (Story 13.4)
    "MarkdownReportGenerator",
    "ReportData",
    "SignedReport",
    "TimelineEvent",
    "save_report",
    "save_signed_report",
    "sign_report",
    "verify_signature",
    # HTML Report Generator (Story 13.5)
    "HTMLReportGenerator",
    "embed_screenshot",
    "embed_screenshots_in_html",
    # SARIF Exporter (Story 13.6)
    "SARIFExporter",
    "validate_sarif",
    # STIX Exporter (Story 13.7)
    "STIXExporter",
    "validate_stix",
    # CSV/Excel Exporter (Story 13.8)
    "CSVExporter",
    "ExcelExporter",
    "export_findings_csv",
    "export_findings_xlsx",
]
