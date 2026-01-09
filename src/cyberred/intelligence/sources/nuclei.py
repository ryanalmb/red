from dataclasses import dataclass
from typing import List, Dict, Optional, Set, Any
from pathlib import Path
import yaml

@dataclass
class NucleiTemplate:
    """Normalized Nuclei template entry.
    
    Maps Nuclei template YAML to flat structure for IntelResult conversion.
    
    Attributes:
        template_id: Unique template ID (e.g., "CVE-2021-44228")
        name: Human-readable template name
        severity: One of: "info", "low", "medium", "high", "critical"
        tags: List of tags for categorization (e.g., ["cve", "rce", "wordpress"])
        cve_ids: List of associated CVE IDs from classification block
        category: Primary category derived from tags (cve, exposure, misconfiguration, etc.)
        path: Relative path to template file
        author: Template author(s)
        description: Template description (optional)
    """
    template_id: str
    name: str
    severity: str
    tags: List[str]
    cve_ids: List[str]
    category: str
    path: str
    author: str = ""
    description: str = ""

    @classmethod
    def from_yaml(cls, yaml_path: Path, templates_root: Path) -> 'NucleiTemplate':
        """Parse a Nuclei template YAML file.
        
        Args:
            yaml_path: Path to the template YAML file.
            templates_root: Root directory of nuclei templates (for relative path calculation).
            
        Returns:
            NucleiTemplate populated from YAML.
            
        Raises:
            ValueError: If parsing fails or required fields missing.
        """
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data or 'id' not in data or 'info' not in data:
            raise ValueError(f"Invalid template format: {yaml_path}")
        
        info = data['info']
        template_id = data['id']
        
        # Extract severity
        severity = info.get('severity', 'info').lower()
        
        # Extract tags
        tags_raw = info.get('tags', [])
        if isinstance(tags_raw, str):
            tags = [t.strip().lower() for t in tags_raw.split(',')]
        else:
            tags = [str(t).lower() for t in tags_raw]
        
        # Extract CVE IDs
        cve_ids = []
        classification = info.get('classification', {})
        if classification:
            cve_raw = classification.get('cve-id', [])
            if isinstance(cve_raw, str):
                cve_ids = [cve_raw] if cve_raw else []
            elif isinstance(cve_raw, list):
                cve_ids = [str(c) for c in cve_raw if c]
        
        # Determine category
        category = cls._determine_category(tags)
        
        # Relative path
        try:
            rel_path = str(yaml_path.relative_to(templates_root))
        except ValueError:
            rel_path = str(yaml_path)
        
        return cls(
            template_id=template_id,
            name=info.get('name', template_id),
            severity=severity,
            tags=tags,
            cve_ids=cve_ids,
            category=category,
            path=rel_path,
            author=info.get('author', ''),
            description=info.get('description', ''),
        )

    @staticmethod
    def _determine_category(tags: List[str]) -> str:
        """Determine primary category from tags."""
        tag_set = set(tags)
        
        if 'cve' in tag_set or any(t.startswith('cve-') for t in tag_set):
            return 'cve'
        if 'exposure' in tag_set:
            return 'exposure'
        if 'misconfig' in tag_set or 'misconfiguration' in tag_set:
            return 'misconfiguration'
        if 'default-login' in tag_set:
            return 'default-login'
        
        return 'other'


from cyberred.intelligence.base import IntelligenceSource, IntelPriority, IntelResult
import asyncio
import structlog

log = structlog.get_logger()

class NucleiSource(IntelligenceSource):
    """Nuclei template index intelligence source.
    
    Scans local nuclei-templates directory for matching templates
    based on service/version keywords.
    
    Requires:
        - nuclei-templates repository cloned locally
        - Update via `nuclei -ut` or manual git pull
    
    Configuration:
        - templates_path: Path to nuclei-templates directory
        - No authentication required (local filesystem)
    """
    
    def __init__(
        self,
        templates_path: str = "/root/nuclei-templates",
        timeout: float = 5.0,
    ) -> None:
        super().__init__(
            name="nuclei",
            timeout=timeout,
            priority=IntelPriority.NUCLEI,
        )
        self._templates_path = Path(templates_path)
        self._index: Optional[Dict[str, List[NucleiTemplate]]] = None



    async def query(self, service: str, version: str) -> List[IntelResult]:
        """Query Nuclei templates matching service/version."""
        log.info("nuclei_query_start", service=service, version=version)
        
        try:
            # Lazy index initialization
            if self._index is None:
                loop = asyncio.get_event_loop()
                self._index = await loop.run_in_executor(None, self._build_index)
            
            # Normalize search terms
            service_lower = service.lower()
            
            # Find matching templates
            matches: Set[NucleiTemplate] = set() # type: ignore
            # Note: Set[NucleiTemplate] requires NucleiTemplate to be hashable (frozen=True or __hash__)
            # Dataclasses are not hashable by default if mutable. 
            # I should make NucleiTemplate frozen=True or use a list and deduplicate by ID.
            # Let's check NucleiTemplate definition. It is a standard dataclass.
            # I'll use a dictionary keyed by template_id to deduplicate.
            match_map: Dict[str, NucleiTemplate] = {}
            
            # Search by service name
            if self._index and service_lower in self._index:
                for t in self._index[service_lower]:
                    match_map[t.template_id] = t
            
            # Search by service name keywords
            if self._index:
                for keyword in service_lower.split():
                    if keyword in self._index:
                        for t in self._index[keyword]:
                            match_map[t.template_id] = t
            
            # Convert to IntelResults
            results = [self._to_intel_result(t) for t in match_map.values()]
            
            # Sort by severity
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            results.sort(key=lambda r: severity_order.get(r.severity, 5))
            
            log.info("nuclei_query_complete", result_count=len(results))
            return results
            
        except Exception as e:
            log.warning("nuclei_query_error", error=str(e))
            return []

    def _to_intel_result(self, template: NucleiTemplate) -> IntelResult:
        """Convert Nuclei template to IntelResult."""
        # First CVE ID or None
        cve_id = template.cve_ids[0] if template.cve_ids else None
        
        # Determine if template is exploitative
        exploit_available = any(
            tag in template.tags
            for tag in ['rce', 'sqli', 'xss', 'lfi', 'rfi', 'ssrf', 'exploit']
        )
        
        # Template path is the "exploit path" for Nuclei
        template_path = str(self._templates_path / template.path)
        
        return IntelResult(
            source="nuclei",
            cve_id=cve_id,
            severity=template.severity,
            exploit_available=exploit_available,
            exploit_path=template_path,
            confidence=0.7,  # Template match, not confirmed vulnerable
            priority=IntelPriority.NUCLEI,
            metadata={
                "template_id": template.template_id,
                "name": template.name,
                "tags": template.tags,
                "category": template.category,
                "author": template.author,
                "description": template.description,
                "cve_ids": template.cve_ids,
            },
        )

    def _build_index(self) -> Dict[str, List[NucleiTemplate]]:
        """Build keyword-based index of templates.
        
        Scans all .yaml files in templates directory, parses info blocks,
        and creates an inverted index mapping keywords to templates.
        
        Returns:
            Dict mapping lowercase keywords to list of matching templates.
        """
        import time
        start_time = time.time()
        index: Dict[str, List[NucleiTemplate]] = {}
        
        for yaml_path in self._templates_path.rglob("*.yaml"):
            try:
                template = NucleiTemplate.from_yaml(yaml_path, self._templates_path)
                
                # Index by all keywords
                keywords = self._extract_keywords(template)
                for keyword in keywords:
                    if keyword not in index:
                        index[keyword] = []
                    index[keyword].append(template)
            except Exception as e:
                # Log debug but continue - don't let one bad template break index
                log.debug("nuclei_template_parse_error", path=str(yaml_path), error=str(e))
                continue
        
        duration = time.time() - start_time
        count = sum(len(v) for v in index.values())
        log.info("nuclei_index_built", count=count, duration_s=round(duration, 2))
        
        if duration > 4.0:
            log.warning("nuclei_index_slow", duration_s=duration, msg="Index build nearing timeout")
            
        return index

    def _extract_keywords(self, template: NucleiTemplate) -> Set[str]:
        """Extract searchable keywords from template.
        
        Args:
            template: Nuclei template entry.
            
        Returns:
            Set of lowercase keywords.
        """
        keywords = set()
        
        # ID and Name keywords
        keywords.add(template.template_id.lower())
        keywords.update(template.name.lower().split())
        
        # Tags and Category
        keywords.update(t.lower() for t in template.tags)
        keywords.add(template.category.lower())
        
        # CVE IDs
        keywords.update(c.lower() for c in template.cve_ids)
        
        return keywords

    async def health_check(self) -> bool:
        """Check if Nuclei templates are available.
        
        Verifies the templates directory exists and contains
        at least one .yaml template file.
        
        Returns:
            True if templates are available, False otherwise.
        """
        try:
            if not self._templates_path.exists():
                return False
            
            if not self._templates_path.is_dir():
                return False
            
            # Check for at least one template
            # rglob returns a generator, so we just need attempt to get one item
            for _ in self._templates_path.rglob("*.yaml"):
                return True
            
            return False  # Empty directory
            
        except Exception:
            return False
