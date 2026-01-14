"""RAG Sources Module.

Contains data source integrations for the RAG escalation layer.
Each source module provides an `ingest()` function that fetches and processes
data into the RAG vector store.

Story 6.5: MITRE ATT&CK Source Integration (FR77)
Story 6.6: Atomic Red Team Source Integration (FR77)
Story 6.7: HackTricks Source Integration (FR77)
Story 6.8: PayloadsAllTheThings & LOLBAS/GTFOBins Integration (FR77)
"""
from cyberred.rag.sources.mitre_attack import ingest as mitre_attack_ingest
from cyberred.rag.sources.atomic_red import ingest as atomic_red_ingest
from cyberred.rag.sources.hacktricks import ingest as hacktricks_ingest
from cyberred.rag.sources.payloads import ingest as payloads_ingest
from cyberred.rag.sources.lolbas import ingest as lolbas_ingest

__all__ = [
    "mitre_attack_ingest",
    "atomic_red_ingest",
    "hacktricks_ingest",
    "payloads_ingest",
    "lolbas_ingest",
]
