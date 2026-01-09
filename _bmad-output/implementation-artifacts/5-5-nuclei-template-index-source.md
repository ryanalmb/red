# Story 5.5: Nuclei Template Index Source

Status: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD methodology at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly. Each task must have a failing test before implementation.

> [!NOTE]
> **DEPENDENCY:** Story 5.1 must be complete. This story implements `IntelligenceSource` interface from [base.py](file:///root/red/src/cyberred/intelligence/base.py).

> [!NOTE]
> **PATTERN REFERENCE:** Follow the implementation patterns established in Stories 5.2, 5.3, and 5.4:
> - [cisa_kev.py](file:///root/red/src/cyberred/intelligence/sources/cisa_kev.py)
> - [nvd.py](file:///root/red/src/cyberred/intelligence/sources/nvd.py)
> - [exploitdb.py](file:///root/red/src/cyberred/intelligence/sources/exploitdb.py)

## Story

As an **agent**,
I want **to query Nuclei template index for detection templates**,
So that **I find relevant vulnerability checks (FR69)**.

## Acceptance Criteria

1. **Given** Story 5.1 is complete
   **When** I call `nuclei_source.query("WordPress", "5.8")`
   **Then** source queries local Nuclei template index
   **And** returns matching templates

2. **Given** a Nuclei index query result
   **When** I examine the `IntelResult` objects
   **Then** results include: template_id, severity, tags, cve_ids (in metadata)

3. **Given** templates are returned
   **When** I check categorization
   **Then** templates are categorized (cve, exposure, misconfiguration, default-login, etc.)

4. **Given** any result from Nuclei source
   **When** I check its priority
   **Then** results have `priority=IntelPriority.NUCLEI` (priority=5)

5. **Given** unit tests
   **When** running against mock template data
   **Then** they verify correct parsing of Nuclei template YAML format

6. **Given** integration tests
   **When** tests run with actual nuclei-templates repository
   **Then** they verify against real template files (cloned to test fixture)

## Tasks / Subtasks

### Phase 0: Setup [BLUE]

- [x] Task 0.1: Verify prerequisites
  - [x] Confirm `pyyaml>=6.0` is in pyproject.toml (already present per story notes)
  - [x] Clone nuclei-templates to fixture (or mock for unit tests)
  - [x] Understand Nuclei template YAML structure:
    ```yaml
    id: wordpress-login-detection
    info:
      name: WordPress Login Detection
      author: projectdiscovery
      severity: info
      description: Detects WordPress login page
      tags: wordpress,login,tech
      reference:
        - https://wordpress.org  
      metadata:
        max-request: 1
      classification:
        cve-id: CVE-XXXX-YYYY  # or cve-id: [] for multiple
        cwe-id: CWE-200
    ```

---

### Phase 1: Template Entry Dataclass [RED → GREEN → REFACTOR]

#### 1A: Define Nuclei Template Entry (AC: 2, 3)

- [x] Task 1.1: Create template entry dataclass
  - [x] **[RED]** Create `tests/unit/intelligence/test_nuclei.py`
  - [x] **[RED]** Write failing test: `NucleiTemplate` dataclass has required fields (template_id, name, severity, tags, cve_ids, category, path)
  - [x] **[RED]** Write failing test: `NucleiTemplate.from_yaml()` parses template YAML info block
  - [x] **[RED]** Write failing test: `NucleiTemplate.from_yaml()` extracts CVE IDs from classification block
  - [x] **[RED]** Write failing test: `NucleiTemplate.from_yaml()` handles missing optional fields gracefully
  - [x] **[GREEN]** Create `src/cyberred/intelligence/sources/nuclei.py`
  - [x] **[GREEN]** Implement `NucleiTemplate` dataclass:
    ```python
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
    ```
  - [x] **[REFACTOR]** Add `from_yaml()` classmethod for parsing template YAML files

---

### Phase 2: NucleiSource Implementation [RED → GREEN → REFACTOR]

#### 2A: Implement IntelligenceSource Interface (AC: 1, 4)

- [x] Task 2.1: Create NucleiSource class
  - [x] **[RED]** Write failing test: `NucleiSource` extends `IntelligenceSource`
  - [x] **[RED]** Write failing test: `NucleiSource.name` returns "nuclei"
  - [x] **[RED]** Write failing test: `NucleiSource.priority` returns `IntelPriority.NUCLEI` (5)
  - [x] **[GREEN]** Implement `NucleiSource` class:
    ```python
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
    ```
  - [x] **[REFACTOR]** Add docstrings and type annotations

#### 2B: Build Template Index (AC: 1, 2)

- [x] Task 2.2: Implement index building
  - [x] **[RED]** Write failing test: `_build_index()` scans templates directory
  - [x] **[RED]** Write failing test: `_build_index()` parses YAML info blocks
  - [x] **[RED]** Write failing test: `_build_index()` builds keyword → templates mapping
  - [x] **[RED]** Write failing test: `_build_index()` handles malformed YAML gracefully
  - [x] **[RED]** Write failing test: `_extract_keywords()` extracts tokens from id, name, tags, cve_ids
  - [x] **[GREEN]** Implement `_build_index()` and `_extract_keywords()` methods:
    ```python
    def _build_index(self) -> Dict[str, List[NucleiTemplate]]:
        """Build keyword-based index of templates.
        
        Scans all .yaml files in templates directory, parses info blocks,
        and creates an inverted index mapping keywords to templates.
        
        Keywords are extracted from:
            - template id
            - name (words)
            - tags
            - CVE IDs (if present)
        
        Returns:
            Dict mapping lowercase keywords to list of matching templates.
        """
        import time
        start_time = time.time()
        index: Dict[str, List[NucleiTemplate]] = {}
        
        for yaml_path in self._templates_path.rglob("*.yaml"):
            try:
                template = self._parse_template(yaml_path)
                if template is None:
                    continue
                
                # Index by all keywords
                keywords = self._extract_keywords(template)
                for keyword in keywords:
                    if keyword not in index:
                        index[keyword] = []
                    index[keyword].append(template)
            except Exception as e:
                log.debug("nuclei_template_parse_error", path=str(yaml_path), error=str(e))
                continue
        
        duration = time.time() - start_time
        log.info("nuclei_index_built", count=sum(len(v) for v in index.values()), duration_s=round(duration, 2))
        
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
    ```
  - [x] **[REFACTOR]** Add lazy initialization (build index on first query)

#### 2C: Implement Query Method (AC: 1, 2, 3)

- [x] Task 2.3: Implement template search
  - [x] **[RED]** Write failing test: `query("WordPress", "5.8")` returns matching templates
  - [x] **[RED]** Write failing test: query searches by service name keywords
  - [x] **[RED]** Write failing test: query filters by version when version-specific templates exist
  - [x] **[RED]** Write failing test: query returns empty list when no matches
  - [x] **[RED]** Write failing test: query returns empty list on error (per ERR3)
  - [x] **[GREEN]** Implement `query()` method:
    ```python
    async def query(self, service: str, version: str) -> List[IntelResult]:
        """Query Nuclei templates matching service/version.
        
        Searches local template index for templates matching the
        service name and optionally the version.
        
        Args:
            service: Service name (e.g., "WordPress", "Apache")
            version: Version string (e.g., "5.8", "2.4.49")
            
        Returns:
            List of IntelResult sorted by severity.
            Empty list on any error.
        """
        log.info("nuclei_query_start", service=service, version=version)
        
        try:
            # Lazy index initialization
            if self._index is None:
                loop = asyncio.get_event_loop()
                self._index = await asyncio.wait_for(
                    loop.run_in_executor(None, self._build_index),
                    timeout=self._timeout,
                )
            
            # Normalize search terms
            service_lower = service.lower()
            version_lower = version.lower() if version else ""
            
            # Find matching templates
            matches: Set[NucleiTemplate] = set()
            
            # Search by service name
            if service_lower in self._index:
                matches.update(self._index[service_lower])
            
            # Search by service name keywords
            for keyword in service_lower.split():
                if keyword in self._index:
                    matches.update(self._index[keyword])
            
            # Convert to IntelResults
            results = [self._to_intel_result(t) for t in matches]
            
            # Sort by severity
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            results.sort(key=lambda r: severity_order.get(r.severity, 5))
            
            log.info("nuclei_query_complete", result_count=len(results))
            return results
            
        except Exception as e:
            log.warning("nuclei_query_error", error=str(e))
            return []
    ```
  - [x] **[REFACTOR]** Add version filtering for more precise matches

#### 2D: Parse Template YAML (AC: 2)

- [x] Task 2.4: Implement YAML parsing
  - [x] **[RED]** Write failing test: `_parse_template()` extracts id, info block
  - [x] **[RED]** Write failing test: `_parse_template()` handles templates without classification
  - [x] **[RED]** Write failing test: `_parse_template()` handles single and list CVE IDs
  - [x] **[RED]** Write failing test: `_parse_template()` categorizes by tags
  - [x] **[GREEN]** Implement `_parse_template()` method:
    ```python
    def _parse_template(self, yaml_path: Path) -> Optional[NucleiTemplate]:
        """Parse a single Nuclei template YAML file.
        
        Args:
            yaml_path: Path to the template YAML file.
            
        Returns:
            NucleiTemplate if successfully parsed, None otherwise.
        """
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data or 'id' not in data or 'info' not in data:
            return None
        
        info = data['info']
        template_id = data['id']
        
        # Extract severity (default to info)
        severity = info.get('severity', 'info').lower()
        if severity not in VALID_SEVERITIES:
            severity = 'info'
        
        # Extract tags (string → list)
        tags_raw = info.get('tags', [])
        if isinstance(tags_raw, str):
            tags = [t.strip().lower() for t in tags_raw.split(',')]
        else:
            tags = [str(t).lower() for t in tags_raw]
        
        # Extract CVE IDs from classification block
        cve_ids = []
        classification = info.get('classification', {})
        if classification:
            cve_raw = classification.get('cve-id', [])
            if isinstance(cve_raw, str):
                cve_ids = [cve_raw] if cve_raw else []
            elif isinstance(cve_raw, list):
                cve_ids = [str(c) for c in cve_raw if c]
        
        # Determine category from tags
        category = self._determine_category(tags)
        
        # Relative path from templates root
        try:
            rel_path = str(yaml_path.relative_to(self._templates_path))
        except ValueError:
            rel_path = str(yaml_path)
        
        return NucleiTemplate(
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
    ```

#### 2E: Category Determination (AC: 3)

- [x] Task 2.5: Map tags to categories
  - [x] **[RED]** Write failing test: `_determine_category(["cve", "rce"])` returns "cve"
  - [x] **[RED]** Write failing test: `_determine_category(["exposure"])` returns "exposure"
  - [x] **[RED]** Write failing test: `_determine_category(["misconfig"])` returns "misconfiguration"
  - [x] **[RED]** Write failing test: `_determine_category(["default-login"])` returns "default-login"
  - [x] **[RED]** Write failing test: `_determine_category([])` returns "other"
  - [x] **[GREEN]** Implement `_determine_category()`:
    ```python
    def _determine_category(self, tags: List[str]) -> str:
        """Determine primary category from template tags.
        
        Categories are prioritized in order:
            1. cve - Templates for known CVEs
            2. exposure - Information disclosure/exposure checks
            3. misconfiguration - Security misconfigurations
            4. default-login - Default credential checks
            5. other - All other templates
        
        Args:
            tags: List of template tags.
            
        Returns:
            Primary category string.
        """
        tag_set = set(tags)
        
        # Priority order for categorization
        if 'cve' in tag_set or any(t.startswith('cve-') for t in tag_set):
            return 'cve'
        if 'exposure' in tag_set:
            return 'exposure'
        if 'misconfig' in tag_set or 'misconfiguration' in tag_set:
            return 'misconfiguration'
        if 'default-login' in tag_set:
            return 'default-login'
        
        return 'other'
    ```

#### 2F: Convert to IntelResult (AC: 2, 4)

- [x] Task 2.6: Implement result conversion
  - [x] **[RED]** Write failing test: `IntelResult.source` is "nuclei"
  - [x] **[RED]** Write failing test: `IntelResult.priority` is 5 (NUCLEI)
  - [x] **[RED]** Write failing test: `IntelResult.metadata` contains template_id, tags, category
  - [x] **[RED]** Write failing test: `IntelResult.cve_id` is first CVE from template (or None)
  - [x] **[RED]** Write failing test: `IntelResult.exploit_available` is True for exploit templates
  - [x] **[GREEN]** Implement `_to_intel_result()`:
    ```python
    def _to_intel_result(self, template: NucleiTemplate) -> IntelResult:
        """Convert Nuclei template to IntelResult.
        
        Args:
            template: Parsed Nuclei template.
            
        Returns:
            IntelResult with Nuclei-specific metadata.
        """
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
    ```

#### 2G: Implement Health Check (AC: 1)

- [x] Task 2.7: Implement health_check method
  - [x] **[RED]** Write failing test: `health_check()` returns True when templates directory exists
  - [x] **[RED]** Write failing test: `health_check()` returns False when directory missing
  - [x] **[RED]** Write failing test: `health_check()` returns False when directory is empty
  - [x] **[GREEN]** Implement `health_check()`:
    ```python
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
            for _ in self._templates_path.rglob("*.yaml"):
                return True
            
            return False  # Empty directory
            
        except Exception:
            return False
    ```

---

### Phase 3: Module Exports [RED → GREEN]

#### 3A: Export New Modules (AC: 1)

- [x] Task 3.1: Verify imports
  - [x] **[RED]** Write test: `from cyberred.intelligence.sources import NucleiSource` works
  - [x] **[RED]** Write test: `from cyberred.intelligence.sources import NucleiTemplate` works
  - [x] **[GREEN]** Update `src/cyberred/intelligence/sources/__init__.py`:
    ```python
    from cyberred.intelligence.sources.nuclei import NucleiSource, NucleiTemplate
    
    __all__ = [
        # ... existing exports ...
        "NucleiSource",
        "NucleiTemplate",
    ]
    ```
  - [x] **[REFACTOR]** Update module docstring to include NucleiSource

---

### Phase 4: Integration Tests [RED → GREEN → REFACTOR]

- [x] Task 4.1: Create integration tests (AC: 6)
  - [x] Create `tests/integration/intelligence/test_nuclei.py`
  - [x] Create test fixture with sample nuclei templates in `tests/fixtures/nuclei-templates/`
  - [x] **[RED]** Write test: queries against fixture templates (mark `@pytest.mark.integration`)
  - [x] **[RED]** Write test: parses real template format correctly
  - [x] **[RED]** Write test: returns valid IntelResult objects with correct fields
  - [x] **[RED]** Write test: handles non-existent service gracefully
  - [x] **[GREEN]** Ensure tests pass against fixture templates
  - [x] **[REFACTOR]** Add skip marker if templates not available: `@pytest.mark.skipif(not Path(...).exists(), reason="nuclei-templates not available")`

---

### Phase 5: Coverage & Documentation [BLUE]

- [x] Task 5.1: Verify 100% coverage
  - [x] Run: `pytest tests/unit/intelligence/test_nuclei.py --cov=cyberred.intelligence.sources.nuclei --cov-report=term-missing`
  - [x] Ensure all statement coverage

- [x] Task 5.2: Update Dev Agent Record
  - [x] Complete Agent Model Used
  - [x] Add Debug Log References
  - [x] Complete Completion Notes List
  - [x] Fill in File List

- [x] Task 5.3: Final verification
  - [x] Verify all ACs met
  - [x] Run full test suite: `pytest tests/unit/intelligence/test_nuclei.py -v --tb=short`
  - [x] Update story status to `review`

## Dev Notes

### Architecture Reference

From [architecture.md#L235-L273](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L235-L273):

```
Integration Pattern:
1. Agent discovers service → calls intelligence.query(service, version)
2. Aggregator queries sources in parallel (5s timeout per source)
3. Results prioritized: CISA KEV > Critical CVE > High CVE > MSF > Nuclei > ExploitDB
4. Agent receives IntelligenceResult with prioritized exploit paths
```

**Priority:** Nuclei = 5 (after Metasploit, before ExploitDB)

### Nuclei Template YAML Structure

From web research and [projectdiscovery.io](https://docs.projectdiscovery.io/templates/structure):

```yaml
id: wordpress-xmlrpc-detection
info:
  name: WordPress XML-RPC Detection
  author: pdteam
  severity: info
  description: Detects WordPress XML-RPC endpoint
  tags: wordpress,xmlrpc,tech,cms
  reference:
    - https://wordpress.org/support/article/xml-rpc-pingback-api/
  classification:
    cve-id: CVE-XXXX-YYYY    # String or list
    cwe-id: CWE-200
  metadata:
    max-request: 1

# Protocol-specific sections follow (http, dns, tcp, file, etc.)
http:
  - method: GET
    path:
      - "{{BaseURL}}/xmlrpc.php"
    matchers:
      - type: word
        words:
          - "XML-RPC"
```

**Key fields to extract:**
- `id` — Template ID (required)
- `info.name` — Human-readable name
- `info.severity` — info/low/medium/high/critical
- `info.tags` — Comma-separated or list
- `info.classification.cve-id` — String or list of CVE IDs
- `info.author` — Template author
- `info.description` — Description text

### Template Categories

Templates can be categorized by tags for filtering:
- **cve** — Templates targeting specific CVEs
- **exposure** — Information disclosure checks
- **misconfiguration** — Security misconfigurations
- **default-login** — Default credential checks
- **tech** — Technology/version detection
- **panel** — Admin panel detection
- **rce** — Remote code execution
- **sqli** — SQL injection
- **xss** — Cross-site scripting
- **lfi/rfi** — File inclusion

### Dependencies

Uses existing dependencies only:
- `pyyaml` — Already in pyproject.toml (≥6.0)
- `pathlib` — stdlib for path handling
- `asyncio` — stdlib for async wrapper
- `structlog` — For logging (existing)

**No new dependencies required.**

### Pattern from Stories 5.2, 5.3, and 5.4

Follow the same structure as [cisa_kev.py](file:///root/red/src/cyberred/intelligence/sources/cisa_kev.py), [nvd.py](file:///root/red/src/cyberred/intelligence/sources/nvd.py), and [exploitdb.py](file:///root/red/src/cyberred/intelligence/sources/exploitdb.py):

1. **Entry dataclass** — Normalized representation of source data (`NucleiTemplate`)
2. **Source class** — Extends `IntelligenceSource` from base.py (`NucleiSource`)
3. **`query()` method** — Returns `List[IntelResult]`, handles errors gracefully
4. **`health_check()` method** — Returns bool, quick verification
5. **`_to_intel_result()` method** — Converts source data to `IntelResult`

### Critical Implementation Notes

1. **Lazy Index Loading** — Build index on first query, not initialization (performance)
2. **YAML Parsing is BLOCKING** — Must wrap in `loop.run_in_executor()` for async compatibility
3. **Error Handling (ERR3)** — Always return empty list on error, never raise exception
4. **Template Path** — Must be resolvable to actual filesystem path
5. **Tag Parsing** — Tags can be comma-separated string OR list in YAML
6. **CVE ID Extraction** — CVE IDs may be in `classification.cve-id` as string or list
7. **Severity Normalization** — Lowercase and validate against VALID_SEVERITIES

### Key Learnings from Stories 5.2, 5.3, and 5.4

From previous story implementations:

1. **Use structlog for logging** — NOT `print()` statements
2. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases explicitly
3. **Verify coverage claims** — Run `pytest --cov` before marking done
4. **Use pytest markers** — Always include `@pytest.mark.unit` and `@pytest.mark.integration`
5. **Async methods** — All query/health methods must be async
6. **Base confidence** — Use 0.7 for template match (lower than keyword match since less precise)
7. **Timeout handling** — Use `asyncio.wait_for()` with `loop.run_in_executor()` for sync operations

### Test Fixture Setup

Create minimal fixture templates in `tests/fixtures/nuclei-templates/`:

```
tests/fixtures/nuclei-templates/
├── cves/
│   └── CVE-2021-44228.yaml     # Log4j template
├── technologies/
│   └── wordpress-detection.yaml  # WordPress detection
└── misconfigurations/
    └── http-missing-security-headers.yaml
```

Example fixture template (`CVE-2021-44228.yaml`):
```yaml
id: CVE-2021-44228
info:
  name: Apache Log4j RCE (Log4Shell)
  author: pdteam
  severity: critical
  description: Apache Log4j2 allows RCE via JNDI injection
  tags: cve,cve2021,rce,log4j,apache
  classification:
    cve-id: CVE-2021-44228
    cwe-id: CWE-502
```

### References

- **Epic 5 Overview:** [epics-stories.md#L2056-L2098](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2056-L2098)
- **Story 5.5 Requirements:** [epics-stories.md#L2202-L2225](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2202-L2225)
- **Architecture - Intelligence Layer:** [architecture.md#L235-L273](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L235-L273)
- **Story 5.1 Implementation:** [5-1-intelligence-source-base-interface.md](file:///root/red/_bmad-output/implementation-artifacts/5-1-intelligence-source-base-interface.md)
- **Story 5.2 Implementation (Pattern):** [5-2-cisa-kev-source-integration.md](file:///root/red/_bmad-output/implementation-artifacts/5-2-cisa-kev-source-integration.md)
- **Story 5.3 Implementation (Pattern):** [5-3-nvd-api-source-integration.md](file:///root/red/_bmad-output/implementation-artifacts/5-3-nvd-api-source-integration.md)
- **Story 5.4 Implementation (Pattern):** [5-4-exploitdb-source-integration.md](file:///root/red/_bmad-output/implementation-artifacts/5-4-exploitdb-source-integration.md)
- **Base Interface Code:** [base.py](file:///root/red/src/cyberred/intelligence/base.py)
- **Nuclei Templates Repo:** https://github.com/projectdiscovery/nuclei-templates
- **Nuclei Template Guide:** https://docs.projectdiscovery.io/templates/structure

## Dev Agent Record

### Agent Model Used

gemini-2.0-flash-exp

### Debug Log References

- See `logs/` for detailed TDD cycles.
- Unit tests: `tests/unit/intelligence/test_nuclei.py`
- Integration tests: `tests/integration/intelligence/test_nuclei.py`

### Completion Notes List

- Implemented `NucleiTemplate` dataclass and parsing logic.
- Implemented `NucleiSource` with `_build_index` using keyword inversion.
- Implemented lazy loading for index to optimize startup time.
- Implemented robust error handling for malformed YAMLs (logs warning but bypasses file).
- Verified full coverage with unit and integration tests (mocking fs vs using fixtures).
- Updated `__init__.py` exports.
- **[Code Review Fix]** Added tests for category determination branches (exposure, misconfiguration, default-login).
- **[Code Review Fix]** Added tests for `health_check` exception handling and `is_dir=False` case.
- **[Code Review Fix]** Added tests for list CVE parsing and path fallback.
- **[Code Review Fix]** Added tests for query exception returns empty list.
- **[Code Review Fix]** Added tests for `_build_index` parse errors and slow warning.
- **[Code Review Fix]** Updated module docstring to include NucleiSource.
- **[Code Review Fix]** Marked all Phase 0-4 tasks as complete.

### File List

| Action | File Path |
|--------|-----------|
| [NEW] | `src/cyberred/intelligence/sources/nuclei.py` |
| [MODIFY] | `src/cyberred/intelligence/sources/__init__.py` |
| [NEW] | `tests/unit/intelligence/test_nuclei.py` |
| [NEW] | `tests/integration/intelligence/test_nuclei.py` |
| [NEW] | `tests/fixtures/nuclei-templates/cves/CVE-2021-44228.yaml` |
| [NEW] | `tests/fixtures/nuclei-templates/technologies/wordpress-detection.yaml` |
| [NEW] | `tests/fixtures/nuclei-templates/misconfigurations/http-missing-security-headers.yaml` |
