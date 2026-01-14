import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from cyberred.rag.sources import atomic_red
from cyberred.rag.sources.atomic_red import (
    _parse_atomic_test_file,
    _create_document,
)
from cyberred.rag.utils import validate_technique_id, TECHNIQUE_ID_PATTERN
from cyberred.rag.ingest import IngestionStats


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ingest_public_api_no_args(tmp_path):
    """Test that ingest can be called with no arguments (AC: 2)."""
    # Create mock repo structure
    mock_repo = tmp_path / "mock_repo"
    atomics_dir = mock_repo / "atomics"
    atomics_dir.mkdir(parents=True)
    
    with patch("cyberred.rag.sources.atomic_red.RAGStore") as MockStore, \
         patch("cyberred.rag.sources.atomic_red.RAGEmbeddings") as MockEmbeddings, \
         patch("cyberred.rag.sources.atomic_red.RAGIngestPipeline") as MockPipeline, \
         patch("cyberred.rag.sources.atomic_red._download_atomics", return_value=mock_repo) as MockDownload:
        
        mock_pipeline_instance = MockPipeline.return_value
        mock_pipeline_instance.process = AsyncMock(return_value=IngestionStats(
            source="atomic_red",
            last_updated=AsyncMock(),
            chunk_count=10,
            document_count=10,
            file_hashes={},
            failed_docs=[]
        ))
        
        stats = await atomic_red.ingest()
        assert isinstance(stats, IngestionStats)
        assert stats.source == "atomic_red"

@pytest.mark.unit
def test_parse_atomic_test_file(tmp_path):
    """Test parsing of Atomic Red Team YAML file (AC: 4-7)."""
    yaml_content = """
attack_technique: T1059.001
display_name: "PowerShell"
atomic_tests:
  - name: "Test 1"
    description: "Description 1"
    supported_platforms:
      - windows
    executor:
      name: powershell
      command: "Write-Host 'Attack'"
      cleanup_command: "Write-Host 'Cleanup'"
  - name: "Test 2"
    description: "Description 2"
    supported_platforms:
      - linux
      - macos
    executor:
      name: sh
      command: "echo 'Attack'"
"""
    test_file = tmp_path / "T1059.001.yaml"
    test_file.write_text(yaml_content, encoding="utf-8")
    
    tests = _parse_atomic_test_file(test_file)
    
    assert len(tests) == 2
    
    t1 = tests[0]
    assert t1["technique_id"] == "T1059.001"
    assert t1["display_name"] == "PowerShell"
    assert t1["test_name"] == "Test 1"
    assert t1["description"] == "Description 1"
    assert t1["supported_platforms"] == ["windows"]
    assert t1["executor_type"] == "powershell"
    assert t1["attack_command"] == "Write-Host 'Attack'"
    assert t1["cleanup_command"] == "Write-Host 'Cleanup'"
    
    t2 = tests[1]
    assert t2["technique_id"] == "T1059.001"
    assert t2["display_name"] == "PowerShell"
    assert t2["supported_platforms"] == ["linux", "macos"]
    assert t2["cleanup_command"] is None


@pytest.mark.unit
class TestTechniqueIdValidation:
    """Test technique ID validation against regex ^T\\d{4}(\\.\\d{3})?$ (AC: unit test requirement)."""
    
    def test_valid_technique_id_base(self):
        """Test valid base technique ID (T####)."""
        assert validate_technique_id("T1059") is True
        assert validate_technique_id("T1234") is True
        assert validate_technique_id("T0001") is True
        
    def test_valid_technique_id_subtechnique(self):
        """Test valid sub-technique ID (T####.###)."""
        assert validate_technique_id("T1059.001") is True
        assert validate_technique_id("T1234.999") is True
        assert validate_technique_id("T0001.000") is True
        
    def test_invalid_technique_id_format(self):
        """Test invalid technique ID formats."""
        assert validate_technique_id("1059") is False  # Missing T
        assert validate_technique_id("T059") is False  # Too few digits
        assert validate_technique_id("T10590") is False  # Too many digits
        assert validate_technique_id("T1059.01") is False  # Sub-technique too few digits
        assert validate_technique_id("T1059.0001") is False  # Sub-technique too many digits
        assert validate_technique_id("TABC") is False  # Non-numeric
        assert validate_technique_id("") is False  # Empty
        assert validate_technique_id(None) is False  # None
        
    def test_regex_pattern_matches(self):
        """Test TECHNIQUE_ID_PATTERN regex directly."""
        assert TECHNIQUE_ID_PATTERN.match("T1059") is not None
        assert TECHNIQUE_ID_PATTERN.match("T1059.001") is not None
        assert TECHNIQUE_ID_PATTERN.match("invalid") is None


@pytest.mark.unit
class TestMalformedYamlHandling:
    """Test handling of malformed/missing fields (graceful skip with warning)."""
    
    def test_malformed_yaml_syntax(self, tmp_path):
        """Test graceful handling of invalid YAML syntax."""
        yaml_content = "invalid: yaml: content: [["
        test_file = tmp_path / "malformed.yaml"
        test_file.write_text(yaml_content, encoding="utf-8")
        
        tests = _parse_atomic_test_file(test_file)
        assert tests == []  # Should return empty, not crash
        
    def test_missing_attack_technique(self, tmp_path):
        """Test graceful handling when attack_technique is missing."""
        yaml_content = """
display_name: "Test"
atomic_tests:
  - name: "Test 1"
    description: "Description"
"""
        test_file = tmp_path / "no_technique.yaml"
        test_file.write_text(yaml_content, encoding="utf-8")
        
        tests = _parse_atomic_test_file(test_file)
        assert tests == []
        
    def test_invalid_technique_id_format_in_file(self, tmp_path):
        """Test graceful handling of invalid technique ID format."""
        yaml_content = """
attack_technique: INVALID123
display_name: "Test"
atomic_tests:
  - name: "Test 1"
"""
        test_file = tmp_path / "invalid_id.yaml"
        test_file.write_text(yaml_content, encoding="utf-8")
        
        tests = _parse_atomic_test_file(test_file)
        assert tests == []  # Invalid ID should be rejected
        
    def test_missing_test_name(self, tmp_path):
        """Test graceful skip when test name is missing."""
        yaml_content = """
attack_technique: T1059
atomic_tests:
  - description: "No name field"
    executor:
      name: bash
      command: "echo test"
  - name: "Valid Test"
    description: "Has name"
    executor:
      name: bash
      command: "echo valid"
"""
        test_file = tmp_path / "missing_name.yaml"
        test_file.write_text(yaml_content, encoding="utf-8")
        
        tests = _parse_atomic_test_file(test_file)
        assert len(tests) == 1  # Only valid test included
        assert tests[0]["test_name"] == "Valid Test"
        
    def test_empty_yaml_file(self, tmp_path):
        """Test handling of empty YAML file."""
        test_file = tmp_path / "empty.yaml"
        test_file.write_text("", encoding="utf-8")
        
        tests = _parse_atomic_test_file(test_file)
        assert tests == []
        
    def test_null_yaml_content(self, tmp_path):
        """Test handling of YAML that parses to None."""
        test_file = tmp_path / "null.yaml"
        test_file.write_text("null", encoding="utf-8")
        
        tests = _parse_atomic_test_file(test_file)
        assert tests == []


@pytest.mark.unit
class TestManualExecutorHandling:
    """Test handling of manual executor type (no command)."""
    
    def test_manual_executor_with_no_command(self, tmp_path):
        """Test manual executor type gets placeholder command."""
        yaml_content = """
attack_technique: T1059
atomic_tests:
  - name: "Manual Test"
    description: "Requires manual execution"
    supported_platforms:
      - windows
    executor:
      name: manual
"""
        test_file = tmp_path / "manual.yaml"
        test_file.write_text(yaml_content, encoding="utf-8")
        
        tests = _parse_atomic_test_file(test_file)
        assert len(tests) == 1
        assert tests[0]["executor_type"] == "manual"
        assert "[Manual execution required" in tests[0]["attack_command"]
        
    def test_manual_executor_with_command(self, tmp_path):
        """Test manual executor with command preserves the command."""
        yaml_content = """
attack_technique: T1059
atomic_tests:
  - name: "Manual with steps"
    description: "Has manual steps"
    supported_platforms:
      - windows
    executor:
      name: manual
      command: "Step 1: Do this\\nStep 2: Do that"
"""
        test_file = tmp_path / "manual_cmd.yaml"
        test_file.write_text(yaml_content, encoding="utf-8")
        
        tests = _parse_atomic_test_file(test_file)
        assert len(tests) == 1
        assert "Step 1" in tests[0]["attack_command"]

@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_atomics_git_clone():
    """Test git clone strategy for downloading atomics."""
    from cyberred.rag.sources.atomic_red import _download_atomics
    
    with patch("cyberred.rag.sources.atomic_red.asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = None
        
        cache_dir = Path("/tmp/cache")
        with patch.object(Path, "exists", return_value=False), \
             patch.object(Path, "mkdir"):
            await _download_atomics(cache_dir)
            
        # Verify git commands were called via asyncio.to_thread
        assert mock_to_thread.call_count >= 2  # clone + sparse-checkout


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_atomics_force_refresh(tmp_path):
    """Test force_refresh deletes existing cache and re-downloads."""
    from cyberred.rag.sources.atomic_red import _download_atomics
    
    # Create a fake existing repo
    repo_dir = tmp_path / "atomic-red-team"
    repo_dir.mkdir()
    (repo_dir / "atomics").mkdir()
    
    assert repo_dir.exists()  # Confirm it exists before
    
    with patch("cyberred.rag.sources.atomic_red.asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = None
        
        await _download_atomics(tmp_path, force_refresh=True)
        
        # Verify directory was removed (shutil.rmtree actually ran)
        assert not repo_dir.exists(), "force_refresh should have deleted the repo"
        # Verify git clone was triggered (clone + sparse-checkout = 2 calls)
        assert mock_to_thread.call_count >= 2


@pytest.mark.unit
def test_create_document_details():
    """Test detailed document creation logic (AC: 7)."""
    test_data = {
        "technique_id": "T1059.001",
        "display_name": "PowerShell",
        "test_name": "Test Name",
        "description": "Test Description",
        "supported_platforms": ["windows"],
        "executor_type": "powershell",
        "attack_command": "Write-Host 'Attack'",
        "cleanup_command": "Write-Host 'Cleanup'",
        "input_arguments": {
            "arg1": {"description": "desc1", "default": "def1"}
        }
    }
    
    doc = _create_document(test_data, index=0)
    
    # Verify ID stability (AC: stable chunk IDs)
    assert doc["metadata"]["id"] == "T1059.001:0"
    
    # Verify metadata fields
    meta = doc["metadata"]
    assert meta["technique_id"] == "T1059.001"
    assert meta["technique_ids"] == ["T1059.001"]
    assert meta["test_name"] == "Test Name"
    assert meta["display_name"] == "PowerShell"
    assert meta["supported_platforms"] == ["windows"]
    assert meta["executor_type"] == "powershell"
    
    # Verify text template includes display_name (AC: 4)
    text = doc["text"]
    assert "Technique: T1059.001 - PowerShell" in text
    assert "Atomic Red Team Test: Test Name" in text
    assert "Input Arguments:" in text
    assert "- arg1: desc1 (default: def1)" in text


@pytest.mark.unit
def test_create_document_without_display_name():
    """Test document creation when display_name is missing."""
    test_data = {
        "technique_id": "T1059",
        "display_name": "",  # Empty display_name
        "test_name": "Test",
        "description": "Desc",
        "supported_platforms": ["linux"],
        "executor_type": "bash",
        "attack_command": "echo test",
        "cleanup_command": None,
        "input_arguments": {}
    }
    
    doc = _create_document(test_data, index=0)
    
    # Should not include " - " when display_name is empty
    assert "Technique: T1059\n" in doc["text"]
    assert " - " not in doc["text"].split("\n")[1]  # Second line is technique
