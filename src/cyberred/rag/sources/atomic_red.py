"""Atomic Red Team Source Integration for RAG Layer.

Story 6.6: Atomic Red Team Source Integration (FR77)

Downloads and ingests Atomic Red Team tests into the RAG vector store.
"""
import asyncio
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
import yaml

from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.ingest import IngestionStats, RAGIngestPipeline
from cyberred.rag.store import RAGStore
from cyberred.rag.utils import get_tactics_for_technique, validate_technique_id

log = structlog.get_logger()

# Constants
ATOMIC_RED_REPO_URL = "https://github.com/redcanaryco/atomic-red-team.git"
DEFAULT_CACHE_DIR = Path("~/.cyber-red/rag/sources/atomic_red").expanduser()

async def ingest(
    *,
    store: Optional[RAGStore] = None,
    embeddings: Optional[RAGEmbeddings] = None,
    incremental: bool = True,
    force_refresh: bool = False,
) -> IngestionStats:
    """Ingest Atomic Red Team tests into RAG store.
    
    Args:
        store: RAGStore instance. Defaults to new instance.
        embeddings: RAGEmbeddings instance. Defaults to new instance.
        incremental: Whether to use incremental ingestion.
        force_refresh: If True, re-download atomics even if cached.
        
    Returns:
        IngestionStats object.
    """
    if store is None:
        store = RAGStore()
    if embeddings is None:
        embeddings = RAGEmbeddings()
        
    log.info("atomic_red_ingest_start", incremental=incremental, force_refresh=force_refresh)

    # Download atomics (using cache dir constant per AC requirements)
    cache_dir = DEFAULT_CACHE_DIR
    repo_dir = await _download_atomics(cache_dir, force_refresh=force_refresh)
    
    # Find atomics folder in cloned repo
    atomics_path = repo_dir / "atomics"
    if not atomics_path.exists():
        log.error("atomic_red_atomics_not_found", path=str(atomics_path))
        raise FileNotFoundError(f"Atomics directory not found at {atomics_path}")

    # Find all YAML files matching T*/*.yaml
    yaml_files = list(atomics_path.glob("T*/T*.yaml"))
    log.info("atomic_red_files_found", count=len(yaml_files))
    
    # Parse YAML files using asyncio.to_thread to avoid blocking event loop
    # (CPU-bound parsing of ~900+ files)
    documents = await asyncio.to_thread(_parse_all_yaml_files, yaml_files)
    
    pipeline = RAGIngestPipeline(store, embeddings)
    
    stats = await pipeline.process(
        source="atomic_red",
        documents=documents,
        incremental=incremental
    )
    
    return stats


def _parse_all_yaml_files(yaml_files: List[Path]) -> List[Dict[str, Any]]:
    """Parse all YAML files and convert to documents (CPU-bound, run in thread).
    
    Args:
        yaml_files: List of YAML file paths to parse.
        
    Returns:
        List of document dicts ready for ingestion.
    """
    documents = []
    for yaml_file in yaml_files:
        tests = _parse_atomic_test_file(yaml_file)
        for idx, test in enumerate(tests):
            # Look up tactics for this technique
            technique_id = test.get("technique_id", "")
            tactics = get_tactics_for_technique(technique_id)
            doc = _create_document(test, idx, tactics=tactics)
            documents.append(doc)
    return documents


async def _download_atomics(cache_dir: Path, *, force_refresh: bool = False) -> Path:
    """Download Atomic Red Team repo via sparse checkout.
    
    Args:
        cache_dir: Parent directory for the repo
        force_refresh: If True, delete existing cache and re-download
        
    Returns:
        Path to the checked out repo directory
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = cache_dir / "atomic-red-team"
    
    # Handle force refresh by removing existing cache
    if force_refresh and repo_dir.exists():
        log.info("atomic_red_force_refresh", path=str(repo_dir))
        shutil.rmtree(repo_dir)
    
    if not repo_dir.exists():
        log.info("atomic_red_download_start", url=ATOMIC_RED_REPO_URL)
        # Clone with sparse checkout options (run in thread to avoid blocking)
        cmd = [
            "git", "clone", 
            "--depth", "1", 
            "--filter=blob:none", 
            "--sparse", 
            ATOMIC_RED_REPO_URL, 
            str(repo_dir)
        ]
        await asyncio.to_thread(subprocess.run, cmd, check=True, capture_output=True)
        
        # Configure sparse checkout to only get atomics directory
        cmd_sparse = ["git", "sparse-checkout", "set", "atomics"]
        await asyncio.to_thread(
            subprocess.run, cmd_sparse, check=True, cwd=repo_dir, capture_output=True
        )
        log.info("atomic_red_download_complete")
    else:
        # Verify atomics folder exists, reconfigure sparse checkout if missing
        if not (repo_dir / "atomics").exists():
            log.warning("atomic_red_atomics_missing_reconfigure", path=str(repo_dir))
            cmd_sparse = ["git", "sparse-checkout", "set", "atomics"]
            await asyncio.to_thread(
                subprocess.run, cmd_sparse, check=True, cwd=repo_dir, capture_output=True
            )
    
    return repo_dir

def _parse_atomic_test_file(path: Path) -> List[Dict[str, Any]]:
    """Parse a single Atomic Red Team YAML file.
    
    Args:
        path: Path to the YAML file.
        
    Returns:
        List of parsed test dictionaries. Empty list if file is invalid.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        log.warning("atomic_red_parse_file_failed", path=str(path), error=str(e))
        return []
    
    # Handle None or non-dict data
    if not isinstance(data, dict):
        log.warning("atomic_red_invalid_yaml_structure", path=str(path))
        return []
        
    technique_id = data.get("attack_technique")
    if not technique_id:
        log.warning("atomic_red_missing_technique_id", path=str(path))
        return []
    
    # Validate technique ID format
    if not validate_technique_id(str(technique_id)):
        log.warning(
            "atomic_red_invalid_technique_id", 
            path=str(path), 
            technique_id=technique_id
        )
        return []
    
    display_name = data.get("display_name", "")
    parsed_tests = []
    
    for test in data.get("atomic_tests", []):
        # Skip tests with missing required fields
        test_name = test.get("name")
        if not test_name:
            log.warning(
                "atomic_red_skip_test_no_name",
                path=str(path),
                technique_id=technique_id
            )
            continue
            
        executor = test.get("executor", {})
        executor_type = executor.get("name", "manual")
        attack_command = executor.get("command")
        
        # Handle manual executor type (no command expected)
        if executor_type == "manual" and not attack_command:
            attack_command = "[Manual execution required - see description]"
        
        parsed_test = {
            "technique_id": str(technique_id),
            "display_name": display_name,
            "test_name": test_name,
            "description": test.get("description", ""),
            "supported_platforms": test.get("supported_platforms", []),
            "executor_type": executor_type,
            "attack_command": attack_command,
            "cleanup_command": executor.get("cleanup_command"),
            "input_arguments": test.get("input_arguments") or {}
        }
        parsed_tests.append(parsed_test)
        
    return parsed_tests

def _create_document(test_data: Dict[str, Any], index: int, tactics: Optional[List[str]] = None) -> Dict[str, Any]:
    """Convert parsed test data to RAG document.
    
    Args:
        test_data: Parsed test dictionary from _parse_atomic_test_file.
        index: Index of the test within its technique file (for stable ID).
        tactics: Optional list of ATT&CK tactics for this technique.
        
    Returns:
        Document dict with 'text' and 'metadata' keys.
    """
    technique_id = test_data["technique_id"]
    display_name = test_data.get("display_name", "")
    test_name = test_data["test_name"]
    platforms = ", ".join(test_data["supported_platforms"])
    executor = test_data["executor_type"]
    description = test_data["description"]
    attack_command = test_data["attack_command"]
    input_args = test_data.get("input_arguments", {})
    tactics = tactics or []
    
    # Build document text using template from story AC:7
    text = f"Atomic Red Team Test: {test_name}\n"
    
    # Include display_name if available (AC: 4)
    if display_name:
        text += f"Technique: {technique_id} - {display_name}\n"
    else:
        text += f"Technique: {technique_id}\n"
    
    # Include tactics if available
    if tactics:
        text += f"Tactics: {', '.join(tactics)}\n"
    
    text += f"Platforms: {platforms}\n"
    text += f"Executor: {executor}\n\n"
    text += f"Description:\n{description}\n\n"
    text += f"Attack Command:\n```{executor}\n{attack_command}\n```"
    
    if test_data.get("cleanup_command"):
        text += f"\n\nCleanup Command:\n```{executor}\n{test_data['cleanup_command']}\n```"
        
    if input_args:
        text += "\n\nInput Arguments:"
        for arg_name, arg_data in input_args.items():
            desc = arg_data.get("description", "")
            default = arg_data.get("default", "")
            text += f"\n- {arg_name}: {desc} (default: {default})"
        
    # Metadata with stable ID (technique_id:test_index) per AC requirements
    doc_id = f"{technique_id}:{index}"
    
    metadata = {
        "id": doc_id,
        "technique_id": technique_id,
        "technique_ids": [technique_id],
        "tactics": tactics,
        "test_name": test_name,
        "display_name": display_name,
        "supported_platforms": test_data["supported_platforms"],
        "executor_type": executor
    }
    
    return {"text": text, "metadata": metadata}
