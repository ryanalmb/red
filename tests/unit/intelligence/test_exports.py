
import pytest

@pytest.mark.unit
def test_module_exports():
    """Test that NucleiSource and NucleiTemplate are exported from the package."""
    from cyberred.intelligence.sources import NucleiSource, NucleiTemplate
    assert NucleiSource is not None
    assert NucleiTemplate is not None
