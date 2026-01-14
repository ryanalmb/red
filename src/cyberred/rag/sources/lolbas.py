"""LOLBAS + GTFOBins Source Integration for RAG Layer.

Story 6.8: PayloadsAllTheThings & LOLBAS/GTFOBins Integration (FR77)

This module ingests:
- LOLBAS (Windows living-off-the-land binaries) YAML files
- GTFOBins (Linux living-off-the-land binaries) markdown files with YAML frontmatter

Both are stored as ContentType.CHEATSHEET.
"""

import asyncio
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog
import yaml

from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.ingest import IngestionStats, RAGIngestPipeline
from cyberred.rag.models import ContentType
from cyberred.rag.store import RAGStore
from cyberred.rag.utils import get_tactics_for_techniques

log = structlog.get_logger()

LOLBAS_REPO_URL = "https://github.com/LOLBAS-Project/LOLBAS"
GTFOBINS_REPO_URL = "https://github.com/GTFOBins/GTFOBins.github.io"

DEFAULT_LOLBAS_CACHE_DIR = Path("~/.cyber-red/rag/sources/lolbas").expanduser()
DEFAULT_GTFOBINS_CACHE_DIR = Path("~/.cyber-red/rag/sources/gtfobins").expanduser()

TECHNIQUE_ID_PATTERN = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")

# GTFOBins function -> ATT&CK mapping (from Story 6.8 dev notes)
GTFOBINS_ATTACK_MAP: Dict[str, List[str]] = {
    "shell": ["T1059.004"],
    "reverse-shell": ["T1059.004", "T1571"],
    "file-upload": ["T1048"],
    "file-download": ["T1105"],
    "sudo": ["T1548.003"],
    "suid": ["T1548.001"],
    "capabilities": ["T1548"],
    "limited-suid": ["T1548.001"],
    "bind-shell": ["T1059.004"],
    "file-write": ["T1565.001"],
    "file-read": ["T1005"],
    "library-load": ["T1574.006"],
    "command": ["T1059"],
}


def validate_technique_id(technique_id: str) -> bool:
    if not technique_id:
        return False
    return bool(re.compile(r"^T\d{4}(?:\.\d{3})?$").match(technique_id))


def _extract_technique_ids(text: str) -> List[str]:
    matches = TECHNIQUE_ID_PATTERN.findall(text or "")
    out: List[str] = []
    seen = set()
    for m in matches:
        if m not in seen and validate_technique_id(m):
            seen.add(m)
            out.append(m)
    return out


def _git_sparse_checkout(repo_url: str, repo_dir: Path, sparse_paths: List[str]) -> None:
    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--filter=blob:none",
        "--sparse",
        repo_url,
        str(repo_dir),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    if sparse_paths:
        subprocess.run(
            ["git", "sparse-checkout", "set", *sparse_paths],
            cwd=repo_dir,
            capture_output=True,
            check=True,
        )


async def _download_lolbas(cache_dir: Path, *, force_refresh: bool = False) -> Path:
    repo_dir = cache_dir / "lolbas"
    if repo_dir.exists() and not force_refresh:
        log.info("lolbas_using_cache", path=str(repo_dir))
        return repo_dir
    if repo_dir.exists() and force_refresh:
        log.info("lolbas_force_refresh", path=str(repo_dir))
        await asyncio.to_thread(shutil.rmtree, repo_dir)

    cache_dir.mkdir(parents=True, exist_ok=True)
    sparse_paths = [
        "yml/OSBinaries",
        "yml/OSLibraries",
        "yml/OSScripts",
        "yml/OtherMSBinaries",
    ]
    log.info("lolbas_downloading", url=LOLBAS_REPO_URL)
    try:
        await asyncio.to_thread(_git_sparse_checkout, LOLBAS_REPO_URL, repo_dir, sparse_paths)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to clone LOLBAS repository: {e}") from e

    log.info("lolbas_download_complete", path=str(repo_dir))
    return repo_dir


async def _download_gtfobins(cache_dir: Path, *, force_refresh: bool = False) -> Path:
    repo_dir = cache_dir / "gtfobins"
    if repo_dir.exists() and not force_refresh:
        log.info("gtfobins_using_cache", path=str(repo_dir))
        return repo_dir
    if repo_dir.exists() and force_refresh:
        log.info("gtfobins_force_refresh", path=str(repo_dir))
        await asyncio.to_thread(shutil.rmtree, repo_dir)

    cache_dir.mkdir(parents=True, exist_ok=True)
    sparse_paths = ["_gtfobins"]
    log.info("gtfobins_downloading", url=GTFOBINS_REPO_URL)
    try:
        await asyncio.to_thread(_git_sparse_checkout, GTFOBINS_REPO_URL, repo_dir, sparse_paths)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to clone GTFOBins repository: {e}") from e

    log.info("gtfobins_download_complete", path=str(repo_dir))
    return repo_dir


def _parse_lolbas_yaml(
    yaml_text: str,
    rel_path: Path,
    last_modified: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    if not (yaml_text or "").strip():
        return None

    try:
        data = yaml.safe_load(yaml_text)
    except Exception as e:
        log.warning("lolbas_yaml_parse_error", file=str(rel_path), error=str(e))
        return None

    if not isinstance(data, dict):
        return None

    name = data.get("Name") or rel_path.stem
    description = data.get("Description") or ""
    commands = data.get("Commands") or []
    full_paths = data.get("Full_Path") or []
    detection = data.get("Detection") or []

    # Gather technique IDs from MitreID fields in commands
    technique_ids: List[str] = []
    for c in commands if isinstance(commands, list) else []:
        if isinstance(c, dict) and c.get("MitreID"):
            technique_ids.extend(_extract_technique_ids(str(c.get("MitreID"))))

    # Fallback technique IDs from whole file
    if not technique_ids:
        technique_ids = _extract_technique_ids(yaml_text)

    # Create a readable document text
    text_lines: List[str] = [f"# LOLBAS: {name}", "", description.strip(), ""]

    if isinstance(commands, list) and commands:
        text_lines.append("## Commands")
        for c in commands:
            if not isinstance(c, dict):
                continue
            cmd = c.get("Command")
            cmd_desc = c.get("Description")
            if cmd:
                text_lines.append(f"- `{cmd}`")
            if cmd_desc:
                text_lines.append(f"  - {cmd_desc}")

    metadata: Dict[str, Any] = {
        "id": f"lolbas:{rel_path}",
        "source": "lolbas",
        "path": str(rel_path),
        "name": name,
        "platform": "windows",
        "description": description,
        "commands": commands,
        "full_path": full_paths,
        "detection": detection,
        "last_modified": last_modified.isoformat() if last_modified else None,
    }
    if technique_ids:
        unique_techniques = sorted(set(technique_ids))
        metadata["technique_ids"] = unique_techniques
        # Look up tactics for the extracted technique IDs
        tactics = get_tactics_for_techniques(unique_techniques)
        if tactics:
            metadata["tactics"] = tactics

    return {"text": "\n".join([l for l in text_lines if l is not None]), "metadata": metadata}


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_gtfobins_frontmatter(md_text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Parse YAML frontmatter from GTFOBins markdown.

    Returns: (frontmatter_dict_or_none, body_text)
    """
    if not (md_text or "").lstrip().startswith("---"):
        return None, md_text

    m = _FRONTMATTER_RE.match(md_text)
    if not m:
        return None, md_text

    fm_raw, body = m.group(1), m.group(2)
    try:
        fm = yaml.safe_load(fm_raw) or {}
    except Exception:
        return None, md_text

    if not isinstance(fm, dict):
        return None, md_text

    return fm, body


def _gtfobins_techniques_from_functions(functions: Any) -> List[str]:
    technique_ids: List[str] = []
    if not isinstance(functions, dict):
        return technique_ids

    for func_name in functions.keys():
        mapped = GTFOBINS_ATTACK_MAP.get(func_name, [])
        technique_ids.extend(mapped)

    # dedup while preserving order
    out: List[str] = []
    seen = set()
    for tid in technique_ids:
        if tid not in seen and validate_technique_id(tid):
            seen.add(tid)
            out.append(tid)
    return out


def _parse_gtfobins_markdown(
    md_text: str,
    rel_path: Path,
    last_modified: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    if not (md_text or "").strip():
        return None

    fm, body = _parse_gtfobins_frontmatter(md_text)
    binary_name = rel_path.stem

    functions = (fm or {}).get("functions") if isinstance(fm, dict) else None
    technique_ids = _gtfobins_techniques_from_functions(functions)

    # Also extract any explicit technique IDs from the body
    technique_ids.extend(_extract_technique_ids(md_text))
    technique_ids = sorted(set([t for t in technique_ids if validate_technique_id(t)]))

    text = f"""# GTFOBins: {binary_name}
Platform: Linux
Path: {rel_path}

{body.strip()}
"""

    metadata: Dict[str, Any] = {
        "id": f"gtfobins:{rel_path}",
        "source": "gtfobins",
        "path": str(rel_path),
        "binary": binary_name,
        "platform": "linux",
        "functions": list(functions.keys()) if isinstance(functions, dict) else [],
        "last_modified": last_modified.isoformat() if last_modified else None,
    }
    if technique_ids:
        metadata["technique_ids"] = technique_ids
        # Look up tactics for the extracted technique IDs
        tactics = get_tactics_for_techniques(technique_ids)
        if tactics:
            metadata["tactics"] = tactics

    return {"text": text, "metadata": metadata}


def _collect_lolbas_documents(repo_dir: Path) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    base = repo_dir
    for rel in [
        Path("yml/OSBinaries"),
        Path("yml/OSLibraries"),
        Path("yml/OSScripts"),
        Path("yml/OtherMSBinaries"),
    ]:
        d = base / rel
        if not d.exists():
            continue
        for yml_file in d.rglob("*.yml"):
            try:
                text = yml_file.read_text(encoding="utf-8", errors="ignore")
                rel_path = yml_file.relative_to(base)
                
                # Extract last_modified timestamp
                try:
                    mtime = yml_file.stat().st_mtime
                    last_modified = datetime.fromtimestamp(mtime)
                except OSError:
                    last_modified = None
                
                doc = _parse_lolbas_yaml(text, rel_path, last_modified=last_modified)
                if doc:
                    docs.append(doc)
            except Exception as e:
                log.warning("lolbas_file_read_error", file=str(yml_file), error=str(e))

    return docs


def _collect_gtfobins_documents(repo_dir: Path) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    base = repo_dir
    root = base / "_gtfobins"
    if not root.exists():
        return docs

    for md_file in root.rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8", errors="ignore")
            rel_path = md_file.relative_to(base)
            
            # Extract last_modified timestamp
            try:
                mtime = md_file.stat().st_mtime
                last_modified = datetime.fromtimestamp(mtime)
            except OSError:
                last_modified = None
            
            doc = _parse_gtfobins_markdown(text, rel_path, last_modified=last_modified)
            if doc:
                docs.append(doc)
        except Exception as e:
            log.warning("gtfobins_file_read_error", file=str(md_file), error=str(e))

    return docs


async def ingest(
    *,
    store: Optional[RAGStore] = None,
    embeddings: Optional[RAGEmbeddings] = None,
    incremental: bool = True,
    force_refresh: bool = False,
) -> IngestionStats:
    """Ingest LOLBAS + GTFOBins into the RAG store."""
    if store is None:
        store = RAGStore()
    if embeddings is None:
        embeddings = RAGEmbeddings()

    log.info("lolbas_ingest_start", incremental=incremental, force_refresh=force_refresh)

    lolbas_repo = await _download_lolbas(DEFAULT_LOLBAS_CACHE_DIR, force_refresh=force_refresh)
    gtfobins_repo = await _download_gtfobins(DEFAULT_GTFOBINS_CACHE_DIR, force_refresh=force_refresh)

    lol_docs = await asyncio.to_thread(_collect_lolbas_documents, lolbas_repo)
    gtf_docs = await asyncio.to_thread(_collect_gtfobins_documents, gtfobins_repo)
    documents = lol_docs + gtf_docs

    log.info("lolbas_documents_collected", lolbas_count=len(lol_docs), gtfobins_count=len(gtf_docs))

    pipeline = RAGIngestPipeline(store, embeddings)
    stats = await pipeline.process(
        source="lolbas",
        documents=documents,
        content_type=ContentType.CHEATSHEET,
        incremental=incremental,
    )

    log.info("lolbas_ingest_complete", stats=stats)
    return stats
