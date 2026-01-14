"""PayloadsAllTheThings Source Integration for RAG Layer.

Story 6.8: PayloadsAllTheThings & LOLBAS/GTFOBins Integration (FR77)

Downloads and ingests PayloadsAllTheThings payload knowledge base into the RAG vector store.
"""

import asyncio
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.ingest import IngestionStats, RAGIngestPipeline
from cyberred.rag.models import ContentType
from cyberred.rag.store import RAGStore
from cyberred.rag.utils import get_tactics_for_techniques

log = structlog.get_logger()

# Constants
PAYLOADS_REPO_URL = "https://github.com/swisskyrepo/PayloadsAllTheThings"
DEFAULT_CACHE_DIR = Path("~/.cyber-red/rag/sources/payloads").expanduser()

# Regex for ATT&CK technique IDs (T#### or T####.###)
# Use word boundaries to avoid partial matches (e.g., don't match "T9999" inside "T99999")
TECHNIQUE_ID_PATTERN = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")

# Directory-to-category mapping (per Story 6.8 Dev Notes)
CATEGORY_MAP: Dict[str, str] = {
    "SQL Injection": "sqli",
    "XSS Injection": "xss",
    "XXE Injection": "xxe",
    "Server Side Template Injection": "ssti",
    "Command Injection": "command_injection",
    "File Inclusion": "lfi_rfi",
    "SSRF": "ssrf",
    "LDAP Injection": "ldap",
    "NoSQL Injection": "nosql",
    "CORS Misconfiguration": "cors",
    "CSRF Injection": "csrf",
    "Insecure Deserialization": "insecure_deserialization",
    "JWT Vulnerabilities": "jwt",
    "OAuth Misconfiguration": "oauth",
    "Open Redirect": "open_redirect",
    "Path Traversal": "path_traversal",
    "Upload Insecure Files": "upload",
}


def validate_technique_id(technique_id: str) -> bool:
    """Validate that a technique ID matches ATT&CK format."""
    if not technique_id:
        return False
    full_pattern = re.compile(r"^T\d{4}(?:\.\d{3})?$")
    return bool(full_pattern.match(technique_id))


def _extract_category_from_rel_path(rel_path: Path) -> str:
    """Extract payload category from a repo-relative file path.

    PayloadsAllTheThings categorization is derived from the top-level directory
    name (e.g., "SQL Injection" -> "sqli").
    """
    parts = rel_path.parts
    if not parts:
        return "general"
    top = parts[0]
    return CATEGORY_MAP.get(top, "general")




def _extract_technique_ids(content: str) -> List[str]:
    """Extract unique ATT&CK technique IDs from content."""
    matches = TECHNIQUE_ID_PATTERN.findall(content)
    seen = set()
    technique_ids: List[str] = []
    for m in matches:
        if m not in seen and validate_technique_id(m):
            seen.add(m)
            technique_ids.append(m)
    return technique_ids


def _parse_markdown_file(
    content: str,
    path: Path,
    last_modified: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Parse a markdown payload file into a document dictionary."""
    if not content.strip():
        log.warning("payloads_empty_file", path=str(path))
        return None

    category = _extract_category_from_rel_path(path)
    technique_ids = _extract_technique_ids(content)

    doc_text = f"""# PayloadsAllTheThings
Category: {category}
Path: {path}

{content}
"""

    metadata: Dict[str, Any] = {
        "id": str(path),  # Stable id based on relative path
        "category": category,
        "path": str(path),
        "last_modified": last_modified.isoformat() if last_modified else None,
    }
    if technique_ids:
        metadata["technique_ids"] = technique_ids
        # Look up tactics for the extracted technique IDs
        tactics = get_tactics_for_techniques(technique_ids)
        if tactics:
            metadata["tactics"] = tactics

    return {"text": doc_text, "metadata": metadata}


def _parse_all_markdown_files(markdown_files: List[Path], repo_root: Path) -> List[Dict[str, Any]]:
    """Parse all markdown files and convert to documents (CPU-bound)."""
    documents: List[Dict[str, Any]] = []

    for md_file in markdown_files:
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            rel_path = md_file.relative_to(repo_root)

            try:
                mtime = md_file.stat().st_mtime
                last_modified = datetime.fromtimestamp(mtime)
            except OSError:
                last_modified = None

            doc = _parse_markdown_file(content, rel_path, last_modified=last_modified)
            if doc:
                documents.append(doc)
        except Exception as e:
            log.warning("payloads_parse_error", file=str(md_file), error=str(e))
            continue

    log.info("payloads_parsing_complete", documents=len(documents))
    return documents


def _git_sparse_checkout(repo_dir: Path) -> None:
    """Perform git sparse checkout for PayloadsAllTheThings (blocking)."""
    clone_cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--filter=blob:none",
        "--sparse",
        PAYLOADS_REPO_URL,
        str(repo_dir),
    ]
    subprocess.run(clone_cmd, capture_output=True, check=True)

    # Sparse checkout only the key directories we care about.
    # We use the human-readable directory names from CATEGORY_MAP.
    sparse_cmd = ["git", "sparse-checkout", "set", *CATEGORY_MAP.keys()]
    subprocess.run(sparse_cmd, cwd=repo_dir, capture_output=True, check=True)


async def _download_payloads(cache_dir: Path, *, force_refresh: bool = False) -> Path:
    """Download PayloadsAllTheThings repository using git sparse checkout."""
    repo_dir = cache_dir / "payloadsallthethings"

    if repo_dir.exists() and not force_refresh:
        log.info("payloads_using_cache", path=str(repo_dir))
        return repo_dir

    if repo_dir.exists() and force_refresh:
        log.info("payloads_force_refresh", path=str(repo_dir))
        await asyncio.to_thread(shutil.rmtree, repo_dir)

    cache_dir.mkdir(parents=True, exist_ok=True)

    log.info("payloads_downloading", url=PAYLOADS_REPO_URL)
    try:
        await asyncio.to_thread(_git_sparse_checkout, repo_dir)
    except subprocess.CalledProcessError as e:
        log.error(
            "payloads_git_clone_failed",
            error=str(e),
            stderr=e.stderr.decode() if e.stderr else None,
        )
        raise RuntimeError(f"Failed to clone PayloadsAllTheThings repository: {e}") from e

    log.info("payloads_download_complete", path=str(repo_dir))
    return repo_dir


async def ingest(
    *,
    store: Optional[RAGStore] = None,
    embeddings: Optional[RAGEmbeddings] = None,
    incremental: bool = True,
    force_refresh: bool = False,
) -> IngestionStats:
    """Ingest PayloadsAllTheThings content into RAG store."""
    if store is None:
        store = RAGStore()
    if embeddings is None:
        embeddings = RAGEmbeddings()

    log.info("payloads_ingest_start", incremental=incremental, force_refresh=force_refresh)

    cache_dir = DEFAULT_CACHE_DIR
    repo_dir = await _download_payloads(cache_dir, force_refresh=force_refresh)

    markdown_files: List[Path] = []
    for d in CATEGORY_MAP.keys():
        category_dir = repo_dir / d
        if category_dir.exists():
            markdown_files.extend(category_dir.rglob("*.md"))

    log.info("payloads_files_found", count=len(markdown_files))

    documents = await asyncio.to_thread(_parse_all_markdown_files, markdown_files, repo_dir)

    pipeline = RAGIngestPipeline(store, embeddings)
    stats = await pipeline.process(
        source="payloads",
        documents=documents,
        content_type=ContentType.PAYLOAD,
        incremental=incremental,
    )

    log.info("payloads_ingest_complete", stats=stats)
    return stats
