"""MITRE ATT&CK Source Integration for RAG Layer.

Story 6.5: MITRE ATT&CK Source Integration (FR77)

Downloads and ingests the MITRE ATT&CK Enterprise STIX bundle into the RAG
vector store, enabling agents to query technique details and detection methods.
"""
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from stix2 import parse as stix_parse  # type: ignore[import-untyped]

from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.ingest import IngestionStats, RAGIngestPipeline
from cyberred.rag.store import RAGStore

log = structlog.get_logger()

# Constants
ENTERPRISE_ATTACK_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/"
    "enterprise-attack/enterprise-attack.json"
)
DEFAULT_CACHE_DIR = Path("~/.cyber-red/rag/sources/mitre_attack").expanduser()
CACHE_FILENAME = "enterprise-attack.json"
SOURCE_NAME = "mitre_attack"

# Regex for ATT&CK technique IDs (T#### or T####.###)
TECHNIQUE_ID_PATTERN = re.compile(r"^T\d{4}(\.\d{3})?$")


async def ingest(
    *,
    store: Optional[RAGStore] = None,
    embeddings: Optional[RAGEmbeddings] = None,
    incremental: bool = True,
    url: str = ENTERPRISE_ATTACK_URL,
) -> IngestionStats:
    """Ingest MITRE ATT&CK Enterprise techniques into RAG store.

    Downloads the ATT&CK Enterprise STIX bundle, extracts techniques with
    their mitigations and detection methods, and ingests them into the
    vector store.

    Args:
        store: RAGStore instance. If None, creates default RAGStore().
        embeddings: RAGEmbeddings instance. If None, creates default RAGEmbeddings().
        incremental: If True, skip unchanged documents based on hash.
        url: URL to download the STIX bundle from. Deaults to MITRE GitHub.

    Returns:
        IngestionStats with processing results.

    Example:
        >>> from cyberred.rag.sources import mitre_attack
        >>> stats = await mitre_attack.ingest()
        >>> print(f"Ingested {stats.chunk_count} chunks from {stats.document_count} techniques")
    """
    import asyncio

    # Default instances if not provided (AC: 2 - no-arg call must work)
    if store is None:
        store = RAGStore()
    if embeddings is None:
        embeddings = RAGEmbeddings()

    log.info("mitre_attack_ingest_start", incremental=incremental, url=url)

    # Download and cache the STIX bundle (AC: 3)
    bundle_path = await _download_bundle(url=url)

    # Parse STIX and extract techniques (AC: 4-6)
    # Run CPU-bound parsing in a thread to avoid blocking the event loop
    techniques, mitigations, relationships = await asyncio.to_thread(
        _parse_stix_bundle, bundle_path
    )

    # Link mitigations to techniques
    # This is also CPU-bound but fast; could be threaded if needed, but parsing is the bottleneck
    technique_mitigations = _link_mitigations(techniques, mitigations, relationships)

    # Convert to documents for ingestion (AC: 7)
    documents = _convert_to_documents(techniques, technique_mitigations)

    # Ingest via pipeline
    pipeline = RAGIngestPipeline(store, embeddings)
    stats = await pipeline.process(
        source=SOURCE_NAME,
        documents=documents,
        incremental=incremental,
    )

    log.info(
        "mitre_attack_ingest_complete",
        techniques=len(techniques),
        chunks=stats.chunk_count,
        documents=stats.document_count,
    )

    return stats


async def _download_bundle(
    url: str = ENTERPRISE_ATTACK_URL,
    cache_dir: Optional[Path] = None,
) -> Path:
    """Download ATT&CK Enterprise STIX bundle with caching.

    Uses local file hash check to avoid re-downloading unchanged content.

    Args:
        url: URL to download from.
        cache_dir: Directory to cache the bundle.

    Returns:
        Path to the cached bundle file.
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / CACHE_FILENAME
    hash_path = cache_dir / f"{CACHE_FILENAME}.sha256"

    # Check if we need to download
    needs_download = True
    if cache_path.exists() and hash_path.exists():
        # Verify cached file integrity
        stored_hash = hash_path.read_text().strip()
        current_hash = _compute_file_hash(cache_path)
        if stored_hash == current_hash:
            log.debug("mitre_attack_cache_hit", path=str(cache_path))
            needs_download = False

    if needs_download:
        log.info("mitre_attack_downloading", url=url)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content

        # Write content and hash
        cache_path.write_bytes(content)
        new_hash = hashlib.sha256(content).hexdigest()
        hash_path.write_text(new_hash)
        log.info("mitre_attack_downloaded", size_bytes=len(content))

    return cache_path


def _compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _parse_stix_bundle(
    bundle_path: Path,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse STIX bundle and extract techniques, mitigations, and relationships.

    Args:
        bundle_path: Path to the STIX bundle JSON file.

    Returns:
        Tuple of (techniques, mitigations, relationships) dictionaries.
        - techniques: Dict[stix_id, technique_data]
        - mitigations: Dict[stix_id, mitigation_data]
        - relationships: List of relationship objects
    """
    import json

    with open(bundle_path, "r", encoding="utf-8") as f:
        bundle_data = json.load(f)

    techniques: Dict[str, Dict[str, Any]] = {}
    mitigations: Dict[str, Dict[str, Any]] = {}
    relationships: List[Dict[str, Any]] = []

    objects = bundle_data.get("objects", [])

    for obj in objects:
        obj_type = obj.get("type", "")

        if obj_type == "attack-pattern":
            technique = _extract_technique(obj)
            if technique:
                techniques[obj["id"]] = technique

        elif obj_type == "course-of-action":
            mitigation = _extract_mitigation(obj)
            if mitigation:
                mitigations[obj["id"]] = mitigation

        elif obj_type == "relationship":
            # Only keep 'mitigates' relationships
            if obj.get("relationship_type") == "mitigates":
                relationships.append(obj)

    log.debug(
        "mitre_attack_parsed",
        techniques=len(techniques),
        mitigations=len(mitigations),
        relationships=len(relationships),
    )

    return techniques, mitigations, relationships


def _extract_technique(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract technique data from STIX attack-pattern object.

    Args:
        obj: STIX attack-pattern object.

    Returns:
        Technique data dictionary or None if invalid.
    """
    # Get ATT&CK ID from external references
    attack_id = None
    source_url = None
    external_refs = obj.get("external_references", [])

    for ref in external_refs:
        if ref.get("source_name") == "mitre-attack":
            ext_id = ref.get("external_id", "")
            if TECHNIQUE_ID_PATTERN.match(ext_id):
                attack_id = ext_id
                source_url = ref.get("url")
                break

    if not attack_id:
        return None

    # Check if revoked or deprecated
    if obj.get("revoked", False) or obj.get("x_mitre_deprecated", False):
        return None

    # Extract fields (AC: 4)
    name = obj.get("name", "")
    description = obj.get("description", "")

    # Tactics from kill chain phases (AC: 4)
    tactics: List[str] = []
    for phase in obj.get("kill_chain_phases", []):
        if phase.get("kill_chain_name") == "mitre-attack":
            tactics.append(phase.get("phase_name", ""))

    # Platforms (AC: 4)
    platforms = obj.get("x_mitre_platforms", [])

    # Detection (AC: 5)
    detection = obj.get("x_mitre_detection", "")

    # Sub-technique handling (AC: 6)
    is_subtechnique = obj.get("x_mitre_is_subtechnique", False)

    # Parent technique linkage (AC: 6)
    parent_technique_id = None
    if is_subtechnique:
        # Prefer x_mitre_parent_technique_ref when present
        parent_ref = obj.get("x_mitre_parent_technique_ref")
        if parent_ref:
            # Will be resolved later via STIX ID lookup
            parent_technique_id = parent_ref
        elif "." in attack_id:
            # Fallback: derive from T####.### → T####
            parent_technique_id = attack_id.split(".")[0]

    return {
        "stix_id": obj["id"],
        "attack_id": attack_id,
        "name": name,
        "description": description,
        "tactics": tactics,
        "platforms": platforms,
        "detection": detection,
        "is_subtechnique": is_subtechnique,
        "parent_technique_id": parent_technique_id,
        "source_url": source_url,
    }


def _extract_mitigation(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract mitigation data from STIX course-of-action object.

    Args:
        obj: STIX course-of-action object.

    Returns:
        Mitigation data dictionary or None if invalid.
    """
    # Check if revoked or deprecated
    if obj.get("revoked", False) or obj.get("x_mitre_deprecated", False):
        return None

    # Get mitigation ID
    mitigation_id = None
    external_refs = obj.get("external_references", [])
    for ref in external_refs:
        if ref.get("source_name") == "mitre-attack":
            mitigation_id = ref.get("external_id")
            break

    return {
        "stix_id": obj["id"],
        "mitigation_id": mitigation_id,
        "name": obj.get("name", ""),
        "description": obj.get("description", ""),
    }


def _link_mitigations(
    techniques: Dict[str, Dict[str, Any]],
    mitigations: Dict[str, Dict[str, Any]],
    relationships: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Link mitigations to techniques via STIX relationships.

    Args:
        techniques: Dict of technique STIX IDs to technique data.
        mitigations: Dict of mitigation STIX IDs to mitigation data.
        relationships: List of 'mitigates' relationship objects.

    Returns:
        Dict mapping technique STIX IDs to lists of mitigation data.
    """
    technique_mitigations: Dict[str, List[Dict[str, Any]]] = {}

    for rel in relationships:
        source_ref = rel.get("source_ref", "")  # course-of-action (mitigation)
        target_ref = rel.get("target_ref", "")  # attack-pattern (technique)

        if source_ref in mitigations and target_ref in techniques:
            if target_ref not in technique_mitigations:
                technique_mitigations[target_ref] = []
            technique_mitigations[target_ref].append(mitigations[source_ref])

    return technique_mitigations


def _resolve_parent_technique_ids(
    techniques: Dict[str, Dict[str, Any]],
) -> None:
    """Resolve parent technique STIX refs to ATT&CK IDs in-place.

    Args:
        techniques: Dict of techniques to update in-place.
    """
    # Build STIX ID to ATT&CK ID mapping
    stix_to_attack: Dict[str, str] = {}
    for stix_id, tech in techniques.items():
        stix_to_attack[stix_id] = tech["attack_id"]

    # Resolve parent refs
    for tech in techniques.values():
        parent_ref = tech.get("parent_technique_id")
        if parent_ref and parent_ref in stix_to_attack:
            tech["parent_technique_id"] = stix_to_attack[parent_ref]


def _convert_to_documents(
    techniques: Dict[str, Dict[str, Any]],
    technique_mitigations: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Convert techniques to documents for RAG ingestion.

    Args:
        techniques: Dict of technique STIX IDs to technique data.
        technique_mitigations: Dict mapping technique STIX IDs to mitigations.

    Returns:
        List of document dicts with {text, metadata} for ingestion.
    """
    # Resolve parent technique IDs first
    _resolve_parent_technique_ids(techniques)

    documents: List[Dict[str, Any]] = []

    for stix_id, tech in techniques.items():
        attack_id = tech["attack_id"]
        mitigations = technique_mitigations.get(stix_id, [])

        # Build document text (AC: 7 - improves embeddings/search quality)
        text_parts = [f"Technique {attack_id}: {tech['name']}"]

        if tech["description"]:
            text_parts.append(f"\n\nDescription:\n{tech['description']}")

        if tech["tactics"]:
            tactics_str = ", ".join(tech["tactics"])
            text_parts.append(f"\n\nTactics: {tactics_str}")

        if tech["platforms"]:
            platforms_str = ", ".join(tech["platforms"])
            text_parts.append(f"\n\nPlatforms: {platforms_str}")

        if tech["detection"]:
            text_parts.append(f"\n\nDetection:\n{tech['detection']}")

        if mitigations:
            mit_parts = []
            for mit in mitigations:
                mit_text = f"- {mit['name']}"
                if mit["description"]:
                    mit_text += f": {mit['description']}"
                mit_parts.append(mit_text)
            text_parts.append(f"\n\nMitigations:\n" + "\n".join(mit_parts))

        if tech["is_subtechnique"] and tech["parent_technique_id"]:
            text_parts.append(f"\n\nParent Technique: {tech['parent_technique_id']}")

        text = "".join(text_parts)

        # Build metadata (AC: 7)
        metadata: Dict[str, Any] = {
            "id": attack_id,  # Stable ID for chunk generation
            "technique_ids": [attack_id],  # Required by story
            "name": tech["name"],
            "tactics": tech["tactics"],
            "platforms": tech["platforms"],
            "is_subtechnique": tech["is_subtechnique"],
            "source_url": tech.get("source_url"),
        }

        if tech["parent_technique_id"]:
            metadata["parent_technique_id"] = tech["parent_technique_id"]

        documents.append({"text": text, "metadata": metadata})

    log.debug("mitre_attack_documents_created", count=len(documents))

    return documents
