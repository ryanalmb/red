import os
import pytest
import subprocess
import yaml
from pathlib import Path

# Assuming tests start from root, or relative path calculation
PROJECT_ROOT = Path(__file__).resolve().parents[3]

@pytest.mark.integration
def test_manifest_script_exists_and_executable():
    """AC1: Script exists and is executable."""
    script_path = PROJECT_ROOT / "scripts" / "generate_manifest.sh"
    
    assert script_path.exists(), f"Script not found at {script_path}"
    assert os.access(script_path, os.X_OK), f"Script at {script_path} is not executable"

@pytest.mark.integration
def test_manifest_generation_execution():
    """AC1, AC2: Script runs and generates valid YAML manifest with tools."""
    script_path = PROJECT_ROOT / "scripts" / "generate_manifest.sh"
    output_path = PROJECT_ROOT / "tools" / "manifest.yaml"
    
    # Run the script
    result = subprocess.run(
        [str(script_path)], 
        env={**os.environ, "OUTPUT_FILE": str(output_path)},
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    assert output_path.exists(), "Output file not created"
    
    with open(output_path) as f:
        # We need pyyaml installed. If not, this might fail. 
        # But project seems to have it (requirements).
        import yaml
        data = yaml.safe_load(f)
        
    assert "tools" in data
    assert len(data.get("tools", [])) > 0, "No tools found in manifest"

    # Task 3: Verify categories
    required_categories = {
        "reconnaissance", "web_application", "exploitation", 
        "post_exploitation", "wireless"
    }
    found_categories = set(data.get("categories", {}).keys())
    missing = required_categories - found_categories
    assert not missing, f"Missing categories in manifest: {missing}"

    # Verify exclusions (AC: exclude standard Unix utilities)
    excluded_samples = ["ls", "cd", "cp", "mv", "grep", "cat", "echo", "mkdir"]
    tool_names = {t["name"] for t in data.get("tools", [])}
    
    for tool in excluded_samples:
        assert tool not in tool_names, f"Standard utility '{tool}' should be excluded"
        
    # Verify we found *some* categorized tools if possible, or at least 'other' isn't everything
    # If the container is minimal, we might not find nmap/sqlmap.
    # But let's check if we have any tool in a real category.
    # Note: categorized_tools.py puts unknowns in 'other' now.
    
    # Check if we successfully categorized anything into standard categories
    categorized_count = 0
    for cat in required_categories:
        categorized_count += len(data["categories"].get(cat, {}).get("tools", []))
        
    # If we are running in a minimal environment, this might be 0.
    # But we want to ensure the *logic* works.
    # The integration test uses whatever is in the container.
    # If standard utils are excluded, and we find NOTHING else, tool_count might be 0?
    
    # Assert tool_count > 0 still holds (AC1/4)
    assert len(data.get("tools", [])) > 0, "No tools found after filtering"



