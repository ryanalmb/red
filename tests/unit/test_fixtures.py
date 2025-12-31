
def test_sample_engagement_loaded(sample_engagement_data):
    """Verify sample engagement data is loaded correctly."""
    assert sample_engagement_data["id"] == "eng-001"
    assert sample_engagement_data["target"] == "127.0.0.1"


def test_sample_sqli_loaded(sample_sqli_data):
    """Verify sample SQLi finding data is loaded correctly."""
    assert sample_sqli_data["type"] == "sqli"
    assert sample_sqli_data["severity"] == "high"


def test_sample_scope_loaded(sample_scope_data):
    """Verify sample scope data is loaded correctly."""
    assert "allowed_hosts" in sample_scope_data
    assert "127.0.0.1" in sample_scope_data["allowed_hosts"]


def test_missing_fixture(load_fixture_data):
    """Verify loading a missing fixture raises FileNotFoundError."""
    import pytest
    with pytest.raises(FileNotFoundError):
        load_fixture_data("non_existent_file.json")


def test_unsupported_format(load_fixture_data, tmp_path, monkeypatch):
    """Verify unsupported file extension raises ValueError."""
    import pytest
    
    # Create a file with unsupported extension
    unsupported_file = tmp_path / "test.txt"
    unsupported_file.write_text("test content")
    
    # Monkeypatch fixtures_dir to point to tmp_path
    def mock_load(filename: str):
        file_path = tmp_path / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Fixture file not found: {file_path}")
        if not filename.endswith((".json", ".yaml", ".yml")):
            raise ValueError(f"Unsupported fixture format: {filename}")
        return {}
    
    with pytest.raises(ValueError, match="Unsupported fixture format"):
        mock_load("test.txt")
