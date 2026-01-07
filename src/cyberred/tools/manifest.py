import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

@dataclass
class ToolManifest:
    """Metadata for a single Kali tool."""
    name: str
    category: str
    description: str = ""
    common_flags: List[str] = field(default_factory=list)
    output_format: str = "stdout"
    requires_root: bool = False

class ManifestLoader:
    """Load and query the Kali tool manifest."""
    
    def __init__(self, manifest_path: Path):
        self._path = manifest_path
        self._tools: List[ToolManifest] = []
        self._loaded = False
    
    @classmethod
    def from_file(cls, path: str) -> "ManifestLoader":
        """Create loader from manifest file path."""
        return cls(Path(path))
    
    def load(self) -> List[ToolManifest]:
        """Load and parse the manifest YAML."""
        if self._loaded:
            return self._tools
            
        with open(self._path) as f:
            data = yaml.safe_load(f)
        
        for category_name, category_data in data.get("categories", {}).items():
            for tool in category_data.get("tools", []):
                self._tools.append(ToolManifest(
                    name=tool["name"],
                    category=category_name,
                    description=tool.get("description", ""),
                    common_flags=tool.get("common_flags", []),
                    output_format=tool.get("output_format", "stdout"),
                    requires_root=tool.get("requires_root", False),
                ))
        
        self._loaded = True
        return self._tools
    
    def get_by_category(self, category: str) -> List[ToolManifest]:
        """Get all tools in a category."""
        self.load()
        return [t for t in self._tools if t.category == category]
    
    def get_all_categories(self) -> List[str]:
        """Get list of all categories."""
        self.load()
        return list(set(t.category for t in self._tools))
    
    def get_capabilities_prompt(self, max_tokens: int = 4000) -> str:
        """Generate a prompt-friendly summary of capabilities."""
        self.load()
        lines = ["# Available Kali Tools\n"]
        
        for category in sorted(self.get_all_categories()):
            tools = self.get_by_category(category)
            lines.append(f"\n## {category.replace('_', ' ').title()}\n")
            for tool in tools[:20]:  # Limit per category for token budget
                lines.append(f"- **{tool.name}**: {tool.description}")
        
        return "\n".join(lines)
