"""HackTricks Source Integration for RAG Layer.

Story 6.7: HackTricks Source Integration (FR77)

Downloads and ingests HackTricks knowledge base into the RAG vector store.
"""
import asyncio
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.ingest import IngestionStats, MarkdownCodeBlockSplitter, RAGIngestPipeline
from cyberred.rag.store import RAGStore
from cyberred.rag.utils import get_tactics_for_techniques

log = structlog.get_logger()

# Constants
HACKTRICKS_REPO_URL = "https://github.com/HackTricks-wiki/hacktricks.git"
DEFAULT_CACHE_DIR = Path("~/.cyber-red/rag/sources/hacktricks").expanduser()

# Regex for ATT&CK technique IDs (T#### or T####.###)
TECHNIQUE_ID_PATTERN = re.compile(r"T\d{4}(?:\.\d{3})?")

# Category mapping from directory structure
# Note: HackTricks content is under src/ directory, so we map based on
# the first meaningful directory after src/
CATEGORY_MAP = {
    "generic-methodologies-and-resources": "methodology",
    "linux-hardening": "linux",
    "windows-hardening": "windows",
    "macos-hardening": "macos",
    "pentesting-web": "web",
    "network-services-pentesting": "network",
    "cloud-security": "cloud",
    "mobile-pentesting": "mobile",
    "forensics": "forensics",
    "crypto-and-stego": "crypto",
    "crypto": "crypto",
    "reversing": "reversing",
    "binary-exploitation": "exploitation",
    "exploiting": "exploitation",
    "hardware-physical-access": "hardware",
    "blockchain": "blockchain",
    "generic-hacking": "general",
}


def validate_technique_id(technique_id: str) -> bool:
    """Validate that a technique ID matches ATT&CK format.
    
    Args:
        technique_id: The technique ID to validate (e.g., T1059 or T1059.001)
        
    Returns:
        True if valid, False otherwise.
    """
    if not technique_id:
        return False
    # Full validation pattern for technique ID
    full_pattern = re.compile(r"^T\d{4}(?:\.\d{3})?$")
    return bool(full_pattern.match(technique_id))


def _extract_category_from_path(path: Path) -> str:
    """Extract category from directory path.
    
    Args:
        path: Relative path from repo root
        
    Returns:
        Category string (methodology, web, linux, etc.)
    """
    # Get directory components
    parts = path.parts
    if not parts:
        return "general"
    
    # HackTricks content is under src/ - skip it to get the meaningful directory
    if parts[0] == "src" and len(parts) > 1:
        category_dir = parts[1]
    else:
        category_dir = parts[0]
    
    return CATEGORY_MAP.get(category_dir, "general")


def _extract_title_from_markdown(markdown: str, path: Path) -> str:
    """Extract title from markdown content.
    
    Args:
        markdown: Markdown content
        path: File path (used as fallback)
        
    Returns:
        Extracted title or filename
    """
    # Look for first H1 header
    lines = markdown.split('\n')
    for line in lines:
        if line.strip().startswith('# '):
            title = line.strip()[2:].strip()
            if title:
                return title
    
    # Fallback to filename without extension
    return path.stem


def _extract_links_from_markdown(markdown: str) -> List[str]:
    """Extract external links from markdown.
    
    Args:
        markdown: Markdown content
        
    Returns:
        List of unique external URLs
    """
    links = []
    
    # Extract markdown links [text](url)
    md_link_pattern = re.compile(r'\[([^\]]+)\]\(([^\)]+)\)')
    for match in md_link_pattern.finditer(markdown):
        url = match.group(2)
        if url.startswith('http://') or url.startswith('https://'):
            links.append(url)
    
    # Extract GitBook embed URLs {% embed url="..." %}
    embed_pattern = re.compile(r'{%\s*embed\s+url=["\']([^"\']+)["\']')
    for match in embed_pattern.finditer(markdown):
        links.append(match.group(1))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_links = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
    
    return unique_links


def _extract_technique_ids(content: str) -> List[str]:
    """Extract ATT&CK technique IDs from content.
    
    Args:
        content: Text content
        
    Returns:
        List of unique valid technique IDs
    """
    matches = TECHNIQUE_ID_PATTERN.findall(content)
    
    # Remove duplicates and validate
    unique_ids = []
    seen = set()
    for match in matches:
        if match not in seen and validate_technique_id(match):
            seen.add(match)
            unique_ids.append(match)
    
    return unique_ids


def _parse_markdown_file(
    content: str, 
    path: Path, 
    last_modified: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    """Parse a markdown file into a document dictionary.
    
    Args:
        content: Markdown file content
        path: Relative path from repo root
        last_modified: File modification timestamp (AC: 5)
        
    Returns:
        Document dictionary or None if empty/invalid
    """
    # Skip empty files
    if not content.strip():
        log.warning("hacktricks_empty_file", path=str(path))
        return None
    
    # Extract metadata
    title = _extract_title_from_markdown(content, path)
    category = _extract_category_from_path(path)
    links = _extract_links_from_markdown(content)
    technique_ids = _extract_technique_ids(content)
    
    # Build document text following template format
    doc_text = f"""# {title}
Category: {category}
Path: {path}

{content}
"""
    
    # Build metadata (AC: 5 - includes category and last_modified)
    metadata = {
        "id": str(path),  # Stable ID based on relative path
        "title": title,
        "category": category,
        "path": str(path),
        "last_modified": last_modified.isoformat() if last_modified else None,
    }
    
    # Add optional metadata if present
    if links:
        metadata["links"] = links
    if technique_ids:
        metadata["technique_ids"] = technique_ids
        # Look up tactics for the extracted technique IDs
        tactics = get_tactics_for_techniques(technique_ids)
        if tactics:
            metadata["tactics"] = tactics
    
    return {
        "text": doc_text,
        "metadata": metadata
    }


def _parse_all_markdown_files(markdown_files: List[Path], repo_root: Path) -> List[Dict[str, Any]]:
    """Parse all markdown files and convert to documents (CPU-bound, run in thread).
    
    Args:
        markdown_files: List of markdown file paths
        repo_root: Repository root directory
        
    Returns:
        List of document dictionaries
    """
    documents = []
    
    for md_file in markdown_files:
        try:
            # Read file content
            content = md_file.read_text(encoding='utf-8', errors='ignore')
            
            # Get relative path from repo root
            rel_path = md_file.relative_to(repo_root)
            
            # Get file modification time (AC: 5 - last_modified metadata)
            try:
                mtime = md_file.stat().st_mtime
                last_modified = datetime.fromtimestamp(mtime)
            except OSError:
                last_modified = None
            
            # Parse markdown with last_modified
            doc = _parse_markdown_file(content, rel_path, last_modified=last_modified)
            if doc:
                documents.append(doc)
            
        except Exception as e:
            log.warning("hacktricks_parse_error", file=str(md_file), error=str(e))
            continue
    
    log.info("hacktricks_parsing_complete", documents=len(documents))
    return documents


async def _download_hacktricks(cache_dir: Path, force_refresh: bool = False) -> Path:
    """Download HackTricks repository using git sparse checkout.
    
    Args:
        cache_dir: Cache directory for downloaded content
        force_refresh: If True, re-download even if cached
        
    Returns:
        Path to downloaded repository
        
    Raises:
        RuntimeError: If git clone fails
    """
    repo_dir = cache_dir / "hacktricks"
    
    # Check if already downloaded
    if repo_dir.exists() and not force_refresh:
        log.info("hacktricks_using_cache", path=str(repo_dir))
        return repo_dir
    
    # Clean up if force refresh
    if repo_dir.exists() and force_refresh:
        log.info("hacktricks_force_refresh", path=str(repo_dir))
        await asyncio.to_thread(shutil.rmtree, repo_dir)
    
    # Create cache directory
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    log.info("hacktricks_downloading", url=HACKTRICKS_REPO_URL)
    
    try:
        # Use git sparse checkout for efficiency (matches atomic_red.py pattern)
        await asyncio.to_thread(_git_sparse_checkout, repo_dir)
    except subprocess.CalledProcessError as e:
        log.error(
            "hacktricks_git_clone_failed",
            error=str(e),
            stderr=e.stderr.decode() if e.stderr else None
        )
        raise RuntimeError(f"Failed to clone HackTricks repository: {e}") from e
    
    log.info("hacktricks_download_complete", path=str(repo_dir))
    return repo_dir


def _git_sparse_checkout(repo_dir: Path) -> None:
    """Perform git sparse checkout (blocking operation).
    
    Uses sparse checkout to efficiently download only markdown content,
    following the same pattern as atomic_red.py.
    
    Args:
        repo_dir: Target directory for clone
        
    Raises:
        subprocess.CalledProcessError: If git commands fail
    """
    # Clone with depth 1, sparse checkout, and blob filter for efficiency
    # This avoids downloading the entire repo history and large files
    clone_cmd = [
        "git", "clone",
        "--depth", "1",
        "--filter=blob:none",
        "--sparse",
        HACKTRICKS_REPO_URL,
        str(repo_dir)
    ]
    
    result = subprocess.run(clone_cmd, capture_output=True, check=True)
    log.debug("hacktricks_clone_complete", stdout=result.stdout.decode() if result.stdout else "")
    
    # Configure sparse checkout to only get markdown-heavy directories
    # HackTricks repo structure: content is under src/ directory
    # Excludes .git, images, and other non-essential content
    sparse_cmd = ["git", "sparse-checkout", "set", 
                  "src/pentesting-web",
                  "src/linux-hardening", 
                  "src/windows-hardening",
                  "src/network-services-pentesting",
                  "src/cloud-security",
                  "src/mobile-pentesting",
                  "src/generic-methodologies-and-resources",
                  "src/forensics",
                  "src/crypto-and-stego",
                  "src/reversing",
                  "src/binary-exploitation",
                  "src/macos-hardening",
                  "src/hardware-physical-access",
                  "src/blockchain",
                  "src/generic-hacking"]
    
    result = subprocess.run(sparse_cmd, cwd=repo_dir, capture_output=True, check=True)
    log.debug("hacktricks_sparse_checkout_complete", stdout=result.stdout.decode() if result.stdout else "")


async def ingest(
    *,
    store: Optional[RAGStore] = None,
    embeddings: Optional[RAGEmbeddings] = None,
    incremental: bool = True,
    force_refresh: bool = False,
) -> IngestionStats:
    """Ingest HackTricks knowledge base into RAG store.
    
    Args:
        store: RAGStore instance. Defaults to new instance.
        embeddings: RAGEmbeddings instance. Defaults to new instance.
        incremental: Whether to use incremental ingestion.
        force_refresh: If True, re-download content even if cached.
        
    Returns:
        IngestionStats object.
    """
    # Default parameters for no-arg call support (AC: 2)
    if store is None:
        store = RAGStore()
    if embeddings is None:
        embeddings = RAGEmbeddings()
    
    log.info("hacktricks_ingest_start", incremental=incremental, force_refresh=force_refresh)
    
    # Download HackTricks repo
    cache_dir = DEFAULT_CACHE_DIR
    repo_dir = await _download_hacktricks(cache_dir, force_refresh=force_refresh)
    
    # Find all markdown files
    markdown_files = list(repo_dir.rglob("*.md"))
    log.info("hacktricks_files_found", count=len(markdown_files))
    
    # Parse markdown files using asyncio.to_thread to avoid blocking event loop
    documents = await asyncio.to_thread(_parse_all_markdown_files, markdown_files, repo_dir)
    
    # Ingest into store via existing pipeline
    pipeline = RAGIngestPipeline(store, embeddings)
    
    stats = await pipeline.process(
        source="hacktricks",
        documents=documents,
        incremental=incremental
    )
    
    log.info("hacktricks_ingest_complete", stats=stats)
    return stats
