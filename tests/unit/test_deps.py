
import pytest
import importlib.util

def test_swarms_installed():
    """Verify swarms package is installed and version is >= 8.0.0."""
    spec = importlib.util.find_spec("swarms")
    assert spec is not None, "swarms package not found"
    
    from importlib.metadata import version, PackageNotFoundError
    try:
        pkg_version = version("swarms")
    except PackageNotFoundError:
        pkg_version = None
    assert pkg_version is not None, "swarms version not found metadata"
    assert pkg_version >= "8.0.0", f"swarms version {pkg_version} is less than 8.0.0"
