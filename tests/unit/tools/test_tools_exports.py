import pytest

def test_tools_module_exports():
    """Verify public API exports from cyberred.tools."""
    import cyberred.tools as tools
    
    assert hasattr(tools, "ContainerPool"), "ContainerPool not exported"
    assert hasattr(tools, "MockContainer"), "MockContainer not exported"
    assert hasattr(tools, "ContainerContext"), "ContainerContext not exported"
