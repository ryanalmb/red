def test_manifest_exports():
    """AC: Verify public exports."""
    try:
        from cyberred.tools import ManifestLoader, ToolManifest
    except ImportError as e:
        import pytest
        pytest.fail(f"Failed to import ManifestLoader or ToolManifest: {e}")
    
    assert ManifestLoader is not None
    assert ToolManifest is not None
