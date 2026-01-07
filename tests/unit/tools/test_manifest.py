import pytest
from dataclasses import is_dataclass
# from cyberred.tools.manifest import ToolManifest (Import inside test to allow test collection even if file missing)

def test_tool_manifest_structure():
    """AC6: ToolManifest dataclass structure."""
    try:
        from cyberred.tools.manifest import ToolManifest
    except ImportError:
        pytest.fail("ToolManifest not found in cyberred.tools.manifest")
    
    assert is_dataclass(ToolManifest)
    
    # Check structure
    tool = ToolManifest(name="nmap", category="reconnaissance")
    assert tool.name == "nmap"
    assert tool.category == "reconnaissance"
    assert hasattr(tool, "description")
    assert hasattr(tool, "common_flags")
    assert hasattr(tool, "output_format")
    assert hasattr(tool, "output_format")
    assert hasattr(tool, "requires_root")

def test_manifest_loader(tmp_path):
    """AC6: ManifestLoader loads from YAML."""
    try:
        from cyberred.tools.manifest import ManifestLoader
    except ImportError:
        pytest.fail("ManifestLoader not found")

    # Create dummy manifest
    manifest_content = """
version: "1.0"
categories:
  reconnaissance:
    tools:
      - name: nmap
        common_flags: ["-sV"]
"""
    p = tmp_path / "manifest.yaml"
    p.write_text(manifest_content)
    
    loader = ManifestLoader.from_file(str(p))
    tools = loader.load()
    
    assert len(tools) == 1
    assert tools[0].name == "nmap"
    assert len(tools) == 1
    assert tools[0].name == "nmap"
    assert tools[0].category == "reconnaissance"

def test_manifest_filtering(tmp_path):
    """AC3: Category filtering."""
    from cyberred.tools.manifest import ManifestLoader
    
    manifest_content = """
version: "1.0"
categories:
  reconnaissance:
    tools:
      - name: nmap
  exploitation:
    tools:
      - name: sqlmap
"""
    p = tmp_path / "manifest_filter.yaml"
    p.write_text(manifest_content)
    
    loader = ManifestLoader.from_file(str(p))
    
    recon = loader.get_by_category("reconnaissance")
    assert len(recon) == 1
    assert recon[0].name == "nmap"
    
    exploit = loader.get_by_category("exploitation")
    assert len(exploit) == 1
    assert exploit[0].name == "sqlmap"
    
    wireless = loader.get_by_category("wireless")
    assert len(wireless) == 0
    
    cats = loader.get_all_categories()
    assert "reconnaissance" in cats
    assert "exploitation" in cats

def test_capabilities_prompt(tmp_path):
    """AC5: Prompt generation."""
    from cyberred.tools.manifest import ManifestLoader
    
    manifest_content = """
version: "1.0"
categories:
  reconnaissance:
    tools:
      - name: nmap
        description: "Port scanner"
"""
    p = tmp_path / "manifest_prompt.yaml"
    p.write_text(manifest_content)
    
    loader = ManifestLoader.from_file(str(p))
    prompt = loader.get_capabilities_prompt()
    
    # Debug print if fails
    print(f"Generated prompt: {prompt}")
    
    assert "Available Kali Tools" in prompt
    assert "Reconnaissance" in prompt
    assert "nmap" in prompt
    assert "Port scanner" in prompt



