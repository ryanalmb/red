# Epic 7: Agent Framework Refactor Proposal

**Version:** 1.0  
**Date:** 2026-01-14  
**Status:** DRAFT - Pending Approval  
**Authors:** BMAD Party Mode (Winston, Amelia, Murat, Mary, Bob, John)

---

## Executive Summary

This proposal recommends a **complete refactor** of Epic 7 (Agent Framework & Stigmergic Coordination) to address fundamental architectural misalignments discovered during implementation review. The current implementation (Stories 7.1-7.5) uses hardcoded tool sequences, diverging from the architecture's intent of LLM-driven tool selection with access to 1,556+ Kali tools.

### Key Decisions

| Decision | Recommendation |
|----------|----------------|
| Refactor approach | Complete refactor (not hybrid) |
| Agent class design | Single base class + role/specialty injection + thin subclasses |
| Tool access | Full 1,556-tool manifest via LLM reasoning |
| Number of agent roles | 8 roles (up from 3) |
| Extension mechanism | Prompt files + subclass inheritance |

### Estimated Impact

- **Stories affected:** 7.1-7.5 (superseded), 7.6+ (minor updates)
- **New stories required:** 11
- **Total effort:** ~41 story points
- **Risk level:** Medium (significant but well-scoped change)
- **Emergence impact:** Positive (increased agent diversity)

---

## 1. Problem Statement

### 1.1 Current Implementation Analysis

Stories 7.1-7.5 have been implemented with the following characteristics:

```python
# CURRENT: recon.py (line 147-148) - Hardcoded tool sequence
tool_sequence: List[str] = [
    "masscan", "nmap", "whatweb", "wafw00f", "subfinder"
]

# CURRENT: recon.py (line 217-237) - Hardcoded dispatch
def _generate_tool_command(self, tool_name: str, target: str) -> str:
    if tool_name == "masscan":
        return self._generate_masscan_command(target)
    elif tool_name == "nmap":
        return self._generate_nmap_command(target)
    # ... static dispatch for ~15 total tools
```

### 1.2 Architecture Requirements (What Should Be)

| Requirement | Architecture Specification | Current Implementation |
|-------------|---------------------------|------------------------|
| **FR31** | "600+ tools via Swarms-native `kali_execute()` code execution" | ❌ ~15 hardcoded tools |
| **FR32** | "Agents **generate** bash/Python code executed in isolated Kali containers" | ❌ Hardcoded command templates |
| **FR5** | "Route tasks to appropriate swarm types (recon, exploit, post-ex)" | ⚠️ Only 3 types, limited flexibility |
| **NFR35** | ">20% novel attack chains vs isolated agents" | ⚠️ At risk due to lack of diversity |

### 1.3 Root Cause

The stories as originally written were ambiguous:

> **Original Story 7.3:** "Tools: nmap, masscan, whatweb, wafw00f, subfinder"

This was interpreted as "implement these specific tools" rather than "these are examples of tools the agent might use via LLM reasoning."

### 1.4 Impact of Not Addressing

| Risk | Consequence |
|------|-------------|
| Limited tool coverage | Only ~1% of Kali tools accessible |
| No LLM reasoning | Agents can't adapt to novel situations |
| Homogeneous swarm | All agents behave identically per type |
| Emergence failure | NFR35 (>20% novel chains) likely fails |
| Architecture drift | Implementation diverges further over time |

---

## 2. Proposed Solution

### 2.1 Design Philosophy

**Core Principle:** One base class with behavioral diversity via role/specialty injection.

This approach balances:
- **Code simplicity** (single base implementation)
- **Behavioral diversity** (multiple roles/specialties for emergence)
- **Extensibility** (easy to add new roles via prompts or subclasses)
- **Architecture alignment** (LLM-driven, full tool access)

### 2.2 Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      AgentProtocol                               │
│  (Structural subtyping - any matching class is compliant)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     StigmergicAgent                              │
│  - role: AgentRole                                               │
│  - specialty: Optional[str]                                      │
│  - system_prompt: str (loaded from PromptLibrary)               │
│  - manifest: ManifestLoader (ALL 1,556 tools)                   │
│  + select_tool(context) -> ToolSelection  [LLM-driven]          │
│  + generate_command(tool, target) -> str  [LLM-driven]          │
│  + execute_phase(target) -> List[Finding]                       │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   ReconAgent    │ │  ExploitAgent   │ │   PostExAgent   │
│ (thin subclass) │ │ (thin subclass) │ │ (thin subclass) │
│ role=RECON      │ │ role=EXPLOIT    │ │ role=POSTEX     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │
          ├── specialty="network"
          ├── specialty="osint"
          ├── specialty="dns"
          └── specialty="subdomain"
```

### 2.3 Role Taxonomy

| Role | Description | Specialties | Example Tools |
|------|-------------|-------------|---------------|
| **RECON** | Discovery & enumeration | network, osint, dns, subdomain | nmap, masscan, amass, subfinder |
| **EXPLOIT** | Vulnerability exploitation | web, network, service | sqlmap, metasploit, nuclei |
| **POSTEX** | Post-exploitation | windows, linux, macos | mimikatz, linpeas, bloodhound |
| **WEBAPP** | Web application testing | (general) | burp, zap, ffuf, wfuzz |
| **WIRELESS** | Wireless network attacks | (general) | aircrack-ng, wifite, kismet |
| **AD** | Active Directory attacks | (general) | rubeus, kerbrute, impacket |
| **CREDENTIAL** | Credential harvesting/cracking | (general) | hashcat, john, hydra |
| **FORENSICS** | Digital forensics | (general) | volatility, autopsy, binwalk |

**Total: 8 roles × multiple specialties = rich behavioral diversity**

### 2.4 Manifest vs --help Approach

**Key Design Decision:** Command syntax comes from the tool's own `--help` output, not from curated manifest metadata.

#### Manifest Responsibilities (Discovery)

| Purpose | How Used |
|---------|----------|
| **Tool Discovery** | LLM needs to know what tools exist |
| **Category Filtering** | Agent roles filter to relevant categories |
| **Tool Validation** | Verify tool exists before execution |
| **Capabilities Summary** | High-level list for LLM tool selection |
| **Parser Mapping** | Route output to correct Tier 1 parser |

#### --help Responsibilities (Command Generation)

| Purpose | How Used |
|---------|----------|
| **Command Syntax** | Fetched dynamically via `tool --help` |
| **Flag Details** | Parsed from help output by LLM |
| **Usage Patterns** | LLM learns from help + general knowledge |

**Benefits:**
- Zero curation effort (no need to document 1,556 tools)
- Always up-to-date (tool's own help is source of truth)
- Works for ANY tool (even obscure ones)
- Minimal code (~30 lines for help caching)

**Flow:**
```
1. Tool Selection: Manifest provides list → LLM selects tool
2. Command Generation: --help provides syntax → LLM generates command
3. Output Processing: Manifest provides parser mapping → Parse output
```

### 2.5 Code Design

#### 2.5.1 Base Agent Class

```python
# src/cyberred/agents/base.py

from enum import Enum
from typing import Optional, List, Dict, Any
from swarms import Agent
from cyberred.tools.manifest import ManifestLoader
from cyberred.llm.gateway import LLMGateway
from cyberred.protocols.agent import AgentProtocol


class AgentRole(Enum):
    """Agent role determines behavioral focus."""
    RECON = "recon"
    EXPLOIT = "exploit"
    POSTEX = "postex"
    WEBAPP = "webapp"
    WIRELESS = "wireless"
    AD = "active_directory"
    CREDENTIAL = "credential"
    FORENSICS = "forensics"


class StigmergicAgent(Agent):
    """
    Base agent with LLM-driven tool selection and stigmergic coordination.
    
    All tool selection is performed by the LLM based on:
    - Current task context
    - Role-specific system prompt
    - Full tool manifest (1,556+ tools)
    - Findings from other agents (stigmergic signals)
    """
    
    def __init__(
        self,
        role: AgentRole,
        specialty: Optional[str] = None,
        system_prompt: Optional[str] = None,
        manifest: Optional[ManifestLoader] = None,
        llm_gateway: Optional[LLMGateway] = None,
        event_bus: Optional[EventBus] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.role = role
        self.specialty = specialty
        self.manifest = manifest or ManifestLoader()
        self.llm = llm_gateway or LLMGateway()
        self.event_bus = event_bus
        
        # Load role-specific prompt or use provided override
        self.system_prompt = system_prompt or PromptLibrary.get(
            role=role, 
            specialty=specialty
        )
        
        # State
        self.findings: List[Finding] = []
        self.current_strategy: Optional[str] = None
        self._throttle_state = ThrottleState()
    
    async def select_tool(self, task_context: Dict[str, Any]) -> ToolSelection:
        """
        LLM-driven tool selection from full manifest.
        
        The LLM considers:
        - Task requirements
        - Target characteristics
        - Previous findings
        - Current strategy from Director
        - Full tool manifest capabilities
        """
        capabilities = self.manifest.get_capabilities_summary(
            categories=self._relevant_categories()
        )
        
        prompt = f"""
        You are a {self.role.value} specialist{f' ({self.specialty})' if self.specialty else ''}.
        
        Task Context:
        {json.dumps(task_context, indent=2)}
        
        Available Tools:
        {capabilities}
        
        Previous Findings:
        {self._summarize_findings()}
        
        Current Strategy:
        {self.current_strategy or 'No specific strategy - use best judgment'}
        
        Select the most appropriate tool and generate the exact command.
        Consider efficiency, stealth requirements, and target characteristics.
        
        Return JSON:
        {{
            "tool": "tool_name",
            "command": "full executable command",
            "reasoning": "brief explanation of choice",
            "expected_output": "what findings to expect"
        }}
        """
        
        response = await self.llm.complete(
            prompt=prompt,
            system=self.system_prompt,
            tier="STANDARD"
        )
        
        return ToolSelection.from_llm_response(response.content)
    
    async def generate_command(
        self, 
        tool: str, 
        target: str, 
        context: Dict[str, Any]
    ) -> str:
        """
        LLM generates command for ANY tool using --help output.
        
        No hardcoded command templates - LLM learns syntax from tool's own help.
        """
        # Get tool help dynamically (cached per session)
        help_output = await self._get_tool_help(tool)
        
        prompt = f"""
        Generate a {tool} command for the following task:
        
        Target: {target}
        Context: {json.dumps(context, indent=2)}
        
        Tool help output:
        ```
        {help_output}
        ```
        
        Requirements:
        - Command must be valid and executable
        - Use the syntax shown in the help output
        - Consider any scope restrictions
        - Optimize for the specific target characteristics
        
        Return ONLY the executable command, no explanation.
        """
        
        response = await self.llm.complete(
            prompt=prompt,
            system=self.system_prompt,
            tier="STANDARD"
        )
        
        return response.content.strip()
    
    async def _get_tool_help(self, tool: str) -> str:
        """Get tool help output, cached per session."""
        if not hasattr(self, '_tool_help_cache'):
            self._tool_help_cache: Dict[str, str] = {}
        
        if tool not in self._tool_help_cache:
            result = await self.kali_execute(f"{tool} --help 2>&1 | head -80")
            self._tool_help_cache[tool] = result.stdout if result.success else ""
        
        return self._tool_help_cache[tool]
    
    async def execute_phase(self, target: Target) -> List[Finding]:
        """
        Execute agent's phase with LLM-driven tool selection.
        
        No hardcoded tool sequences - LLM decides dynamically.
        """
        task_context = {
            "phase": self.role.value,
            "specialty": self.specialty,
            "target": target.to_dict(),
            "scope": target.scope.to_dict(),
            "findings_so_far": [f.to_dict() for f in self.findings],
        }
        
        iteration = 0
        max_iterations = 20  # Safety limit
        
        while not await self._phase_complete(task_context) and iteration < max_iterations:
            # Apply self-throttling
            await self._apply_throttle()
            
            # LLM selects next action
            selection = await self.select_tool(task_context)
            
            # Validate against scope (hard gate)
            if not await self._validate_scope(selection.command, target.scope):
                self.logger.warning(f"Command rejected by scope validator: {selection.command}")
                continue
            
            # Execute via kali_execute()
            result = await self.kali_execute(selection.command)
            
            # Process output (Tier 1 parser or Tier 2 LLM summarization)
            findings = await self.output_processor.process(
                tool=selection.tool,
                output=result,
                context=task_context
            )
            
            # Update state
            self.findings.extend(findings)
            task_context["findings_so_far"] = [f.to_dict() for f in self.findings]
            
            # Publish to stigmergic layer
            await self._publish_findings(findings)
            
            iteration += 1
        
        return self.findings
    
    def _relevant_categories(self) -> List[str]:
        """Get manifest categories relevant to this agent's role."""
        category_map = {
            AgentRole.RECON: ["reconnaissance", "network"],
            AgentRole.EXPLOIT: ["exploitation", "web_application"],
            AgentRole.POSTEX: ["post_exploitation"],
            AgentRole.WEBAPP: ["web_application"],
            AgentRole.WIRELESS: ["wireless"],
            AgentRole.AD: ["post_exploitation"],  # AD tools in post_ex
            AgentRole.CREDENTIAL: ["exploitation", "post_exploitation"],
            AgentRole.FORENSICS: ["forensics"],
        }
        # Return relevant categories, but LLM can access ALL tools if needed
        return category_map.get(self.role, [])
```

#### 2.5.2 Thin Subclasses (Convenience)

```python
# src/cyberred/agents/recon.py

class ReconAgent(StigmergicAgent):
    """
    Reconnaissance specialist agent.
    
    Thin subclass that sets role=RECON. All logic is in base class.
    Specialty can further focus the agent's expertise.
    """
    
    def __init__(
        self, 
        specialty: str = "network",
        **kwargs
    ):
        super().__init__(
            role=AgentRole.RECON,
            specialty=specialty,
            **kwargs
        )


# src/cyberred/agents/exploit.py

class ExploitAgent(StigmergicAgent):
    """Exploitation specialist agent."""
    
    def __init__(self, specialty: str = "network", **kwargs):
        super().__init__(role=AgentRole.EXPLOIT, specialty=specialty, **kwargs)


# src/cyberred/agents/postex.py

class PostExAgent(StigmergicAgent):
    """Post-exploitation specialist agent."""
    
    def __init__(self, specialty: str = "linux", **kwargs):
        super().__init__(role=AgentRole.POSTEX, specialty=specialty, **kwargs)


# src/cyberred/agents/webapp.py (NEW)

class WebAppAgent(StigmergicAgent):
    """Web application testing specialist."""
    
    def __init__(self, **kwargs):
        super().__init__(role=AgentRole.WEBAPP, **kwargs)


# src/cyberred/agents/wireless.py (NEW)

class WirelessAgent(StigmergicAgent):
    """Wireless network security specialist."""
    
    def __init__(self, **kwargs):
        super().__init__(role=AgentRole.WIRELESS, **kwargs)


# src/cyberred/agents/ad.py (NEW)

class ActiveDirectoryAgent(StigmergicAgent):
    """Active Directory attack specialist."""
    
    def __init__(self, **kwargs):
        super().__init__(role=AgentRole.AD, **kwargs)


# src/cyberred/agents/credential.py (NEW)

class CredentialAgent(StigmergicAgent):
    """Credential harvesting and cracking specialist."""
    
    def __init__(self, **kwargs):
        super().__init__(role=AgentRole.CREDENTIAL, **kwargs)


# src/cyberred/agents/forensics.py (NEW)

class ForensicsAgent(StigmergicAgent):
    """Digital forensics specialist."""
    
    def __init__(self, **kwargs):
        super().__init__(role=AgentRole.FORENSICS, **kwargs)
```

#### 2.5.3 Prompt Library

```python
# src/cyberred/agents/prompts.py

class PromptLibrary:
    """
    Load and manage role-specific system prompts.
    
    Prompts are stored as markdown files for easy editing and extension.
    """
    
    PROMPT_DIR = Path(__file__).parent / "prompts"
    
    @classmethod
    def get(cls, role: AgentRole, specialty: Optional[str] = None) -> str:
        """Load prompt for role/specialty combination."""
        # Try specialty-specific first
        if specialty:
            specialty_path = cls.PROMPT_DIR / f"{role.value}_{specialty}.md"
            if specialty_path.exists():
                return specialty_path.read_text()
        
        # Fall back to role-level prompt
        role_path = cls.PROMPT_DIR / f"{role.value}.md"
        if role_path.exists():
            return role_path.read_text()
        
        # Default prompt
        return cls._default_prompt(role, specialty)
    
    @classmethod
    def _default_prompt(cls, role: AgentRole, specialty: Optional[str]) -> str:
        return f"""You are an expert penetration tester specializing in {role.value}.
{f'Your specific expertise is {specialty}.' if specialty else ''}

You have access to the full Kali Linux toolset (1,556+ tools).
Select and execute tools based on the target context and current findings.

Guidelines:
- Always verify scope before executing commands
- Prefer stealthy approaches when possible
- Document your reasoning for tool selection
- Build on findings from other agents in the swarm
"""
```

#### 2.5.4 Example Prompt Files

```markdown
<!-- src/cyberred/agents/prompts/recon.md -->

# Reconnaissance Specialist

You are an expert reconnaissance agent in a penetration testing swarm.

## Primary Objectives
- Discover hosts, services, and attack surface
- Identify technologies and versions
- Map network topology
- Gather OSINT when applicable

## Tool Selection Guidelines
- Start broad (masscan for port discovery) then narrow (nmap for service detection)
- Use passive techniques before active when stealth matters
- Correlate findings from multiple tools
- Consider target environment (cloud vs on-prem vs hybrid)

## Output Expectations
- Report all discovered hosts and services
- Flag potential vulnerabilities for ExploitAgent
- Identify high-value targets for prioritization

## Coordination
- Publish findings to stigmergic layer for other agents
- Respond to Director strategy updates
- Avoid duplicate scanning of already-enumerated targets
```

```markdown
<!-- src/cyberred/agents/prompts/recon_osint.md -->

# OSINT Reconnaissance Specialist

You are an expert in Open Source Intelligence gathering.

## Primary Objectives
- Discover publicly available information about targets
- Identify employee names, emails, social media
- Find exposed credentials or sensitive data
- Map organizational structure

## Tool Selection Guidelines
- theHarvester for email/subdomain enumeration
- amass for comprehensive DNS reconnaissance  
- subfinder for subdomain discovery
- Avoid active scanning - OSINT only

## Coordination
- Feed discovered subdomains to network recon agents
- Share credential findings with credential agents
```

---

## 3. Story Specifications

### 3.1 Stories to Supersede

The following stories are marked as **SUPERSEDED** - their implementation will be replaced:

| Story | Title | Status | Reason |
|-------|-------|--------|--------|
| 7.1 | StigmergicAgent Base Class | SUPERSEDED | Hardcoded approach, no LLM tool selection |
| 7.3 | ReconAgent Implementation | SUPERSEDED | Hardcoded tool sequence |
| 7.4 | ExploitAgent Implementation | SUPERSEDED | Hardcoded tool dispatch |
| 7.5 | PostExAgent Implementation | SUPERSEDED | Hardcoded tool dispatch |

**Note:** Story 7.2 (Agent Self-Throttling) is **RETAINED** - the throttling logic is valid and will be integrated into the new base class.

### 3.2 New/Revised Story Specifications

---

#### Story 7.1-v2: StigmergicAgent Base with LLM Tool Selection

**Priority:** P0 (Critical Path)  
**Effort:** 8 story points  
**Dependencies:** ManifestLoader (4.4), LLMGateway (3.10), OutputProcessor (4.5)

**User Story:**
> As the Cyber-Red system, I need agents that can intelligently select and execute ANY tool from the 1,556+ tool manifest using LLM reasoning, so that the swarm can adapt to novel situations and discover emergent attack paths.

**Acceptance Criteria:**

```gherkin
Feature: LLM-Driven Tool Selection

  Scenario: Agent selects appropriate tool based on context
    Given an agent with role "recon" and specialty "network"
    And a target "192.168.1.0/24"
    And the full tool manifest is available
    When the agent executes its phase
    Then the LLM selects a tool from the manifest
    And generates a valid executable command
    And the command is validated against scope before execution

  Scenario: Agent can use ANY tool regardless of role
    Given an agent with role "recon"
    And context indicates web application discovered
    When the LLM determines sqlmap is appropriate
    Then the agent CAN execute sqlmap (not restricted by role)
    And the system logs the cross-role tool usage

  Scenario: Tool selection considers previous findings
    Given an agent has discovered open ports [22, 80, 443]
    When selecting the next tool
    Then the LLM prompt includes previous findings
    And the selection builds on existing reconnaissance

  Scenario: System prompt varies by role and specialty
    Given agents with different roles
    When each agent initializes
    Then each loads its role-specific prompt from PromptLibrary
    And specialty-specific prompts override role-level prompts
```

**Technical Requirements:**
- [ ] `AgentRole` enum with 8 roles
- [ ] `StigmergicAgent` base class with `select_tool()` method
- [ ] `generate_command()` method for LLM command generation
- [ ] `PromptLibrary` class for role/specialty prompt loading
- [ ] Integration with `ManifestLoader.get_capabilities_summary()`
- [ ] Integration with `LLMGateway.complete()`
- [ ] Scope validation before command execution
- [ ] Self-throttling integration (from 7.2)

**Files Changed:**
- `src/cyberred/agents/base.py` (major rewrite)
- `src/cyberred/agents/roles.py` (new)
- `src/cyberred/agents/prompts.py` (new)
- `src/cyberred/agents/prompts/*.md` (new - prompt files)

---

#### Story 7.3-v2: ReconAgent LLM-Driven Implementation

**Priority:** P0  
**Effort:** 3 story points  
**Dependencies:** 7.1-v2

**User Story:**
> As a penetration tester, I need ReconAgent to intelligently select reconnaissance tools based on target context, so that discovery is thorough and adaptive.

**Acceptance Criteria:**

```gherkin
Feature: ReconAgent LLM-Driven Reconnaissance

  Scenario: ReconAgent performs adaptive scanning
    Given a ReconAgent with specialty "network"
    And target "10.0.0.0/24"
    When execute_phase() is called
    Then the agent uses LLM to select scanning strategy
    And may use ANY recon tool (nmap, masscan, rustscan, etc.)
    And adapts based on discovered services

  Scenario: ReconAgent specialties influence tool preference
    Given a ReconAgent with specialty "osint"
    When selecting tools
    Then the LLM system prompt emphasizes OSINT techniques
    And prefers passive tools (theHarvester, amass)
    But CAN still use active tools if needed

  Scenario: ReconAgent publishes findings for swarm coordination
    Given a ReconAgent discovers open ports
    When findings are processed
    Then findings are published to stigmergic layer
    And other agents receive the signals
```

**Technical Requirements:**
- [ ] Thin subclass setting `role=AgentRole.RECON`
- [ ] Support for specialties: network, osint, dns, subdomain
- [ ] Prompt files: `recon.md`, `recon_network.md`, `recon_osint.md`, etc.
- [ ] Remove ALL hardcoded tool sequences
- [ ] Remove ALL hardcoded command generators

**Files Changed:**
- `src/cyberred/agents/recon.py` (major simplification)
- `src/cyberred/agents/prompts/recon.md` (new)
- `src/cyberred/agents/prompts/recon_network.md` (new)
- `src/cyberred/agents/prompts/recon_osint.md` (new)

---

#### Story 7.4-v2: ExploitAgent LLM-Driven Implementation

**Priority:** P0  
**Effort:** 3 story points  
**Dependencies:** 7.1-v2

**User Story:**
> As a penetration tester, I need ExploitAgent to intelligently select exploitation tools based on discovered vulnerabilities and intelligence, so that exploitation is effective and adaptive.

**Acceptance Criteria:**

```gherkin
Feature: ExploitAgent LLM-Driven Exploitation

  Scenario: ExploitAgent selects exploit based on vulnerability
    Given a vulnerability finding for SQL injection
    And intelligence indicates CVE-2021-44228 (Log4Shell)
    When ExploitAgent selects tool
    Then LLM considers both findings
    And may select sqlmap, nuclei, or metasploit as appropriate

  Scenario: ExploitAgent handles authorization gates
    Given an exploit requires manual authorization (FR13)
    When the agent attempts execution
    Then agent enters WAITING_AUTHORIZATION state
    And waits for operator approval
    And resumes upon approval
```

**Technical Requirements:**
- [ ] Thin subclass setting `role=AgentRole.EXPLOIT`
- [ ] Support for specialties: web, network, service
- [ ] Integration with Intelligence layer for CVE correlation
- [ ] Authorization state handling (per FR13/FR15)
- [ ] Prompt files for exploitation strategies

**Files Changed:**
- `src/cyberred/agents/exploit.py` (major simplification)
- `src/cyberred/agents/prompts/exploit.md` (new)
- `src/cyberred/agents/prompts/exploit_web.md` (new)

---

#### Story 7.5-v2: PostExAgent LLM-Driven Implementation

**Priority:** P0  
**Effort:** 3 story points  
**Dependencies:** 7.1-v2

**User Story:**
> As a penetration tester, I need PostExAgent to intelligently select post-exploitation tools based on access level and target OS, so that lateral movement and persistence are effective.

**Acceptance Criteria:**

```gherkin
Feature: PostExAgent LLM-Driven Post-Exploitation

  Scenario: PostExAgent adapts to target OS
    Given shell access to a Windows host
    When PostExAgent selects tools
    Then LLM considers Windows-specific options
    And may select mimikatz, winpeas, or bloodhound

  Scenario: PostExAgent adapts to Linux target
    Given shell access to a Linux host
    When PostExAgent selects tools
    Then LLM considers Linux-specific options
    And may select linpeas, pspy, or GTFOBins techniques
```

**Technical Requirements:**
- [ ] Thin subclass setting `role=AgentRole.POSTEX`
- [ ] Support for specialties: windows, linux, macos
- [ ] OS detection integration
- [ ] Prompt files for post-exploitation strategies

**Files Changed:**
- `src/cyberred/agents/postex.py` (major simplification)
- `src/cyberred/agents/prompts/postex.md` (new)
- `src/cyberred/agents/prompts/postex_windows.md` (new)
- `src/cyberred/agents/prompts/postex_linux.md` (new)

---

#### Story 7.18: WebAppAgent Implementation

**Priority:** P1  
**Effort:** 5 story points  
**Dependencies:** 7.1-v2

**User Story:**
> As a penetration tester, I need a specialized WebAppAgent for web application testing, so that web vulnerabilities are discovered with expert-level tool selection.

**Acceptance Criteria:**

```gherkin
Feature: WebAppAgent Web Application Testing

  Scenario: WebAppAgent performs comprehensive web testing
    Given a web application at https://target.com
    When WebAppAgent executes phase
    Then the agent uses LLM to select web testing strategy
    And may use tools like ffuf, sqlmap, nuclei, nikto, wfuzz
    And considers WAF detection results in tool selection

  Scenario: WebAppAgent handles authentication flows
    Given a web application with login page
    When WebAppAgent encounters authentication
    Then it can perform credential testing
    And can test authenticated areas if credentials provided
```

**Technical Requirements:**
- [ ] New file `src/cyberred/agents/webapp.py`
- [ ] Thin subclass setting `role=AgentRole.WEBAPP`
- [ ] Prompt file emphasizing OWASP Top 10
- [ ] WAF detection awareness

**Files Created:**
- `src/cyberred/agents/webapp.py` (new)
- `src/cyberred/agents/prompts/webapp.md` (new)

---

#### Story 7.19: WirelessAgent Implementation

**Priority:** P1  
**Effort:** 5 story points  
**Dependencies:** 7.1-v2

**User Story:**
> As a penetration tester, I need a specialized WirelessAgent for wireless network attacks, so that WiFi vulnerabilities are discovered with expert-level tool selection.

**Acceptance Criteria:**

```gherkin
Feature: WirelessAgent Wireless Network Testing

  Scenario: WirelessAgent performs WiFi reconnaissance
    Given wireless interfaces available
    When WirelessAgent executes phase
    Then the agent discovers nearby access points
    And identifies encryption types
    And selects appropriate attack tools

  Scenario: WirelessAgent handles handshake capture
    Given a WPA2 network discovered
    When WirelessAgent attempts credential attack
    Then it captures handshakes appropriately
    And can integrate with CredentialAgent for cracking
```

**Technical Requirements:**
- [ ] New file `src/cyberred/agents/wireless.py`
- [ ] Thin subclass setting `role=AgentRole.WIRELESS`
- [ ] Prompt file for wireless attack methodology
- [ ] Tools: aircrack-ng, wifite, kismet, bettercap

**Files Created:**
- `src/cyberred/agents/wireless.py` (new)
- `src/cyberred/agents/prompts/wireless.md` (new)

---

#### Story 7.20: ActiveDirectoryAgent Implementation

**Priority:** P1  
**Effort:** 5 story points  
**Dependencies:** 7.1-v2

**User Story:**
> As a penetration tester, I need a specialized ActiveDirectoryAgent for AD attacks, so that domain environments are tested with expert-level tool selection.

**Acceptance Criteria:**

```gherkin
Feature: ActiveDirectoryAgent AD Testing

  Scenario: ADAgent performs domain enumeration
    Given access to a domain-joined host
    When ADAgent executes phase
    Then the agent enumerates domain structure
    And identifies privilege escalation paths
    And discovers kerberoastable accounts

  Scenario: ADAgent integrates with BloodHound
    Given domain access established
    When ADAgent collects data
    Then it uses SharpHound/BloodHound for path analysis
    And identifies shortest paths to Domain Admin
```

**Technical Requirements:**
- [ ] New file `src/cyberred/agents/ad.py`
- [ ] Thin subclass setting `role=AgentRole.AD`
- [ ] Prompt file for AD attack methodology
- [ ] Tools: bloodhound, rubeus, kerbrute, impacket-*

**Files Created:**
- `src/cyberred/agents/ad.py` (new)
- `src/cyberred/agents/prompts/ad.md` (new)

---

#### Story 7.21: CredentialAgent Implementation

**Priority:** P1  
**Effort:** 5 story points  
**Dependencies:** 7.1-v2

**User Story:**
> As a penetration tester, I need a specialized CredentialAgent for credential harvesting and cracking, so that authentication attacks are performed with expert-level tool selection.

**Acceptance Criteria:**

```gherkin
Feature: CredentialAgent Credential Attacks

  Scenario: CredentialAgent performs password spraying
    Given discovered user accounts
    When CredentialAgent executes
    Then it performs intelligent password spraying
    And respects lockout policies
    And uses appropriate tools (hydra, crackmapexec)

  Scenario: CredentialAgent cracks captured hashes
    Given NTLM hashes from mimikatz
    When CredentialAgent processes hashes
    Then it selects appropriate cracking approach
    And may use hashcat or john
    And considers hash type for tool selection
```

**Technical Requirements:**
- [ ] New file `src/cyberred/agents/credential.py`
- [ ] Thin subclass setting `role=AgentRole.CREDENTIAL`
- [ ] Prompt file for credential attack methodology
- [ ] Tools: hashcat, john, hydra, mimikatz, responder

**Files Created:**
- `src/cyberred/agents/credential.py` (new)
- `src/cyberred/agents/prompts/credential.md` (new)

---

#### Story 7.22: ForensicsAgent Implementation

**Priority:** P2  
**Effort:** 3 story points  
**Dependencies:** 7.1-v2

**User Story:**
> As a penetration tester, I need a specialized ForensicsAgent for evidence collection and analysis, so that engagement artifacts are properly handled.

**Acceptance Criteria:**

```gherkin
Feature: ForensicsAgent Evidence Collection

  Scenario: ForensicsAgent collects artifacts
    Given post-exploitation access established
    When ForensicsAgent executes
    Then it collects relevant artifacts
    And maintains chain of custody
    And stores evidence appropriately
```

**Technical Requirements:**
- [ ] New file `src/cyberred/agents/forensics.py`
- [ ] Thin subclass setting `role=AgentRole.FORENSICS`
- [ ] Prompt file for forensics methodology
- [ ] Tools: volatility, autopsy, binwalk

**Files Created:**
- `src/cyberred/agents/forensics.py` (new)
- `src/cyberred/agents/prompts/forensics.md` (new)

---

#### Story 7.23: AgentRole Enum & PromptLibrary

**Priority:** P0  
**Effort:** 3 story points  
**Dependencies:** None

**User Story:**
> As a developer, I need a centralized role enum and prompt library, so that agent behaviors are consistently managed and easily extended.

**Acceptance Criteria:**

```gherkin
Feature: Role and Prompt Management

  Scenario: PromptLibrary loads role-specific prompts
    Given prompt files exist in prompts/ directory
    When PromptLibrary.get(role=RECON, specialty="network") is called
    Then it returns contents of recon_network.md
    And falls back to recon.md if specialty file missing

  Scenario: New roles can be added
    Given a developer wants to add a custom agent role
    When they add to AgentRole enum
    And create corresponding prompt file
    Then agents can be instantiated with new role
```

**Technical Requirements:**
- [ ] `AgentRole` enum with all 8 roles
- [ ] `PromptLibrary` class with prompt file loading
- [ ] Fallback logic for missing specialty prompts
- [ ] Hot-reload support for prompt changes (optional)

**Files Created:**
- `src/cyberred/agents/roles.py` (new)
- `src/cyberred/agents/prompts.py` (new)

---

#### Story 7.24: SwarmRouter Multi-Agent Support

**Priority:** P0  
**Effort:** 3 story points  
**Dependencies:** 7.23

**User Story:**
> As the Cyber-Red system, I need SwarmRouter to support all 8 agent roles, so that tasks can be routed to the appropriate specialist agents.

**Acceptance Criteria:**

```gherkin
Feature: SwarmRouter Extended Routing

  Scenario: SwarmRouter routes to new agent types
    Given a web application vulnerability finding
    When SwarmRouter determines routing
    Then it may route to WebAppAgent instead of generic ExploitAgent

  Scenario: SwarmRouter spawns diverse swarms
    Given a request to spawn a swarm of 100 agents
    When spawn_swarm() is called
    Then agents are distributed across roles
    And distribution is configurable
```

**Technical Requirements:**
- [ ] Update SwarmRouter to recognize all 8 roles
- [ ] Configurable role distribution for swarm spawning
- [ ] Routing rules for new agent types

**Files Changed:**
- `src/cyberred/agents/router.py` (update)

---

#### Story 7.25: Agent Test Suite (Unified)

**Priority:** P0  
**Effort:** 5 story points  
**Dependencies:** 7.1-v2 through 7.22

**User Story:**
> As a developer, I need a unified test suite for all agent types, so that agent behavior is consistently validated.

**Acceptance Criteria:**

```gherkin
Feature: Unified Agent Testing

  Scenario: All agents pass protocol compliance
    Given all agent classes
    When tested against AgentProtocol
    Then all agents implement required methods
    And all agents can be instantiated

  Scenario: LLM tool selection is tested
    Given mock LLM responses
    When select_tool() is called
    Then tool selection logic is validated
    And command generation is validated

  Scenario: Role-specific behavior is tested
    Given agents with different roles
    When executing with same target
    Then different tools are selected (based on prompts)
    And behavior matches role expectations
```

**Technical Requirements:**
- [ ] Parametrized tests for all 8 agent roles
- [ ] Mock LLM for deterministic testing
- [ ] Protocol compliance tests
- [ ] Integration tests with real LLM (optional/CI gate)

**Files Changed:**
- `tests/unit/agents/test_base.py` (rewrite)
- `tests/unit/agents/test_recon_agent.py` (rewrite)
- `tests/unit/agents/test_exploit_agent.py` (rewrite)
- `tests/unit/agents/test_postex_agent.py` (rewrite)
- `tests/unit/agents/test_webapp_agent.py` (new)
- `tests/unit/agents/test_wireless_agent.py` (new)
- `tests/unit/agents/test_ad_agent.py` (new)
- `tests/unit/agents/test_credential_agent.py` (new)
- `tests/unit/agents/test_forensics_agent.py` (new)
- `tests/integration/agents/test_llm_tool_selection.py` (new)

---

#### Story 7.26: Emergence Validation Update

**Priority:** P0  
**Effort:** 5 story points  
**Dependencies:** 7.25

**User Story:**
> As the Cyber-Red system, I need emergence validation tests to account for the new agent diversity, so that NFR35-37 are properly validated.

**Acceptance Criteria:**

```gherkin
Feature: Emergence Validation with Diverse Agents

  Scenario: Diverse swarm achieves >20% emergence
    Given a swarm with all 8 agent roles
    And identical isolated agent runs
    When comparing attack paths discovered
    Then stigmergic swarm finds >20% more unique paths (NFR35)

  Scenario: Causal chain tracking works with new agents
    Given diverse agent actions
    When decision_context is recorded
    Then all actions have traceable context (NFR37)
    And 3+ hop causal chains are detectable (NFR36)
```

**Technical Requirements:**
- [ ] Update emergence tests for 8 roles
- [ ] Verify diversity improves emergence score
- [ ] Validate decision_context propagation across all roles

**Files Changed:**
- `tests/emergence/test_emergence_score.py` (update)
- `tests/emergence/test_causal_chains.py` (update)

---

## 4. Migration Plan

### 4.0 Dependency Chain (Critical)

The following dependency chain MUST be respected:

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: Foundation                                              │
│ 7.18 (AgentRole + PromptLibrary) → 7.1 (Base) → 7.2 (Throttle)  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: ALL Agent Types (must complete BEFORE routing)         │
│ 7.3, 7.4, 7.5 (Core) + 7.19-7.23 (New Agents)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: Routing & Coordination (knows ALL 8 agent types)       │
│ 7.6 (SwarmRouter) → 7.7 (Spawner) → 7.13 (Sharding)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: Emergence & Validation                                  │
│ 7.8-7.12, 7.14-7.17, 7.24, 7.25                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Insight:** Story 7.6 (SwarmRouter) MUST come AFTER all agent types are implemented, not before. Otherwise SwarmRouter would need rework when new agents are added.

### 4.1 Phase 1: Foundation (Sprint N)

| Task | Stories | Effort | Deliverable |
|------|---------|--------|-------------|
| Implement AgentRole enum (8 roles) | 7.18 | 2 pts | `roles.py` |
| Implement PromptLibrary | 7.18 | 1 pt | `prompts.py` |
| Create base prompt files | 7.18 | - | `prompts/*.md` |
| Refactor StigmergicAgent base | 7.1 | 8 pts | `base.py` |
| Self-Throttling (unchanged) | 7.2 | 3 pts | (already done) |

**Sprint Total:** 14 points

### 4.2 Phase 2: ALL Agent Types (Sprint N+1)

**Critical:** All agent types must be implemented BEFORE SwarmRouter (7.6).

| Task | Stories | Effort | Deliverable |
|------|---------|--------|-------------|
| Refactor ReconAgent | 7.3 | 3 pts | `recon.py` |
| Refactor ExploitAgent | 7.4 | 3 pts | `exploit.py` |
| Refactor PostExAgent | 7.5 | 3 pts | `postex.py` |
| WebAppAgent | 7.19 | 5 pts | `webapp.py` |
| WirelessAgent | 7.20 | 5 pts | `wireless.py` |

**Sprint Total:** 19 points

### 4.3 Phase 3: Remaining Agents + Routing (Sprint N+2)

| Task | Stories | Effort | Deliverable |
|------|---------|--------|-------------|
| ActiveDirectoryAgent | 7.21 | 5 pts | `ad.py` |
| CredentialAgent | 7.22 | 5 pts | `credential.py` |
| ForensicsAgent | 7.23 | 3 pts | `forensics.py` |
| SwarmRouter (ALL 8 types) | 7.6 | 5 pts | `router.py` |
| Dynamic Agent Spawner | 7.7 | 3 pts | `spawner.py` |
| Topic Sharding | 7.13 | 3 pts | `sharding.py` |

**Sprint Total:** 24 points

### 4.4 Phase 4: Emergence & Validation (Sprint N+3 and N+4)

| Task | Stories | Effort | Deliverable |
|------|---------|--------|-------------|
| Decision Context Tracking | 7.8 | 3 pts | `context.py` |
| Isolated vs Stigmergic Comparison | 7.9 | 5 pts | `comparison.py` |
| Emergence Score Calculation | 7.10 | 3 pts | `emergence.py` |
| Causal Chain Depth Validation | 7.11 | 3 pts | `causal.py` |
| Agent Crash Recovery | 7.12 | 5 pts | `recovery.py` |
| Emergence Gate Test | 7.14 | 5 pts | `tests/emergence/` |
| Emergent Strategy Triggering | 7.15 | 5 pts | `strategy.py` |
| Authorization Handling | 7.16 | 3 pts | `auth.py` |
| Director Feedback Loop | 7.17 | 5 pts | `feedback.py` |
| Unified Agent Test Suite | 7.24 | 5 pts | `tests/unit/agents/` |
| Emergence Validation Update | 7.25 | 5 pts | `tests/emergence/` |

**Sprint Total:** 47 points (split across 2 sprints)

### 4.5 Complete Story Sequence

| Order | Story | Title | Points | Phase |
|-------|-------|-------|--------|-------|
| 1 | **7.18** | AgentRole Enum + PromptLibrary | 3 | Foundation |
| 2 | **7.1** | StigmergicAgent Base (LLM tool selection) | 8 | Foundation |
| 3 | **7.2** | Self-Throttling | 3 | Foundation |
| 4 | **7.3** | ReconAgent (LLM-driven) | 3 | Agents |
| 5 | **7.4** | ExploitAgent (LLM-driven) | 3 | Agents |
| 6 | **7.5** | PostExAgent (LLM-driven) | 3 | Agents |
| 7 | **7.19** | WebAppAgent | 5 | Agents |
| 8 | **7.20** | WirelessAgent | 5 | Agents |
| 9 | **7.21** | ActiveDirectoryAgent | 5 | Agents |
| 10 | **7.22** | CredentialAgent | 5 | Agents |
| 11 | **7.23** | ForensicsAgent | 3 | Agents |
| 12 | **7.6** | SwarmRouter (ALL 8 types) | 5 | Routing |
| 13 | **7.7** | Dynamic Agent Spawner | 3 | Routing |
| 14 | **7.13** | Topic Sharding | 3 | Routing |
| 15 | **7.8** | Decision Context Tracking | 3 | Emergence |
| 16 | **7.9** | Isolated vs Stigmergic Comparison | 5 | Emergence |
| 17 | **7.10** | Emergence Score Calculation | 3 | Emergence |
| 18 | **7.11** | Causal Chain Depth Validation | 3 | Emergence |
| 19 | **7.12** | Agent Crash Recovery | 5 | Resilience |
| 20 | **7.14** | Emergence Gate Test (HARD GATE) | 5 | Validation |
| 21 | **7.15** | Emergent Strategy Triggering | 5 | Coordination |
| 22 | **7.16** | Authorization Handling | 3 | Coordination |
| 23 | **7.17** | Director Feedback Loop | 5 | Coordination |
| 24 | **7.24** | Unified Agent Test Suite | 5 | Testing |
| 25 | **7.25** | Emergence Validation Update | 5 | Testing |

**Total: 25 stories, ~104 story points across 5 sprints**

### 4.6 Code Removal Plan

The following code will be **DELETED** during refactoring:

```python
# FROM recon.py - DELETE THESE:
tool_sequence: List[str] = ["masscan", "nmap", "whatweb", "wafw00f", "subfinder"]

def _generate_tool_command(self, tool_name: str, target: str) -> str:
    if tool_name == "masscan": ...
    elif tool_name == "nmap": ...
    # ... entire dispatch block

def _generate_masscan_command(self, target: str) -> str: ...
def _generate_nmap_command(self, target: str) -> str: ...
def _generate_whatweb_command(self, target: str) -> str: ...
# ... all hardcoded command generators

# FROM exploit.py - DELETE THESE:
def _determine_exploit_command(self, ...) -> str:
    # ... hardcoded exploit selection

# FROM postex.py - DELETE THESE:
# ... similar hardcoded patterns
```

---

## 5. Risk Assessment

### 5.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM generates invalid commands | MEDIUM | HIGH | Validate commands before execution; have fallback patterns |
| LLM token limits with full manifest | LOW | MEDIUM | Use summarized manifest; paginate if needed |
| Prompt engineering complexity | MEDIUM | MEDIUM | Iterate on prompts; A/B test effectiveness |
| Existing tests break | HIGH | MEDIUM | Rewrite tests as part of refactor (7.25) |
| Performance regression | LOW | MEDIUM | Benchmark before/after; cache LLM responses |

### 5.2 Schedule Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Refactor takes longer than estimated | MEDIUM | MEDIUM | Phase delivery; prioritize P0 stories |
| Prompt tuning requires iteration | HIGH | LOW | Budget time for prompt refinement |
| Integration issues with other epics | LOW | HIGH | Coordinate with Epic 3 (LLM) and Epic 4 (Tools) |

### 5.3 Emergence Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Diverse agents don't improve emergence | LOW | HIGH | Test early with mock swarms |
| LLM reasoning is too homogeneous | MEDIUM | MEDIUM | Vary temperature; use diverse prompts |
| NFR35 (>20% emergence) still fails | LOW | CRITICAL | This refactor specifically targets emergence |

---

## 6. Success Metrics

### 6.1 Functional Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Tool coverage | 1,556 tools accessible | Any tool can be selected by LLM |
| Role coverage | 8 roles implemented | All roles have agents |
| Specialty coverage | 15+ specialties | Diverse prompt variations |
| Test coverage | >90% | Unit + integration tests |

### 6.2 Emergence Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| NFR35: Novel attack chains | >20% | Stigmergic vs isolated comparison |
| NFR36: Causal chain depth | ≥3 hops | decision_context analysis |
| NFR37: Context coverage | 100% | All actions have decision_context |
| Role diversity impact | Measurable | Compare 3-role vs 8-role swarms |

### 6.3 Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Invalid command rate | <5% | LLM generates valid commands |
| Scope violation attempts | 0 | All commands pass scope validation |
| Agent crash rate | <1% | Agents handle errors gracefully |

---

## 7. Appendices

### Appendix A: File Structure After Refactor

```
src/cyberred/agents/
├── __init__.py
├── base.py              # StigmergicAgent (LLM-driven)
├── roles.py             # AgentRole enum
├── prompts.py           # PromptLibrary class
├── prompts/
│   ├── recon.md
│   ├── recon_network.md
│   ├── recon_osint.md
│   ├── recon_dns.md
│   ├── exploit.md
│   ├── exploit_web.md
│   ├── exploit_network.md
│   ├── postex.md
│   ├── postex_windows.md
│   ├── postex_linux.md
│   ├── webapp.md
│   ├── wireless.md
│   ├── ad.md
│   ├── credential.md
│   └── forensics.md
├── recon.py             # Thin subclass
├── exploit.py           # Thin subclass
├── postex.py            # Thin subclass
├── webapp.py            # NEW - Thin subclass
├── wireless.py          # NEW - Thin subclass
├── ad.py                # NEW - Thin subclass
├── credential.py        # NEW - Thin subclass
├── forensics.py         # NEW - Thin subclass
├── factory.py           # Agent factory (optional)
├── director.py          # DirectorEnsemble (unchanged)
├── ghost_agent.py       # (unchanged)
└── rag_escalator.py     # (unchanged)
```

### Appendix B: Comparison with Current Implementation

| Aspect | Current (7.1-7.5) | Proposed (Refactor) |
|--------|-------------------|---------------------|
| Tool selection | Hardcoded sequences | LLM-driven |
| Tool access | ~15 tools | 1,556 tools |
| Command generation | Template dispatch | LLM generation |
| Agent roles | 3 | 8 |
| Specialties | None | 15+ |
| Extension mechanism | Subclass + modify code | Add prompt file |
| Emergence potential | Limited (homogeneous) | High (diverse) |
| Architecture alignment | ❌ Divergent | ✅ Aligned |

### Appendix C: Glossary

| Term | Definition |
|------|------------|
| **Role** | Primary behavioral focus of an agent (RECON, EXPLOIT, etc.) |
| **Specialty** | Sub-focus within a role (network, osint, web, etc.) |
| **System Prompt** | LLM instruction that shapes agent behavior |
| **Tool Selection** | LLM-driven choice of which tool to execute |
| **Command Generation** | LLM-driven creation of executable command |
| **Stigmergic** | Indirect coordination through environment (findings) |
| **Emergence** | Novel behaviors arising from agent interaction |

---

## 8. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product Owner | | | |
| Tech Lead | | | |
| Architect | | | |
| QA Lead | | | |

---

**Document Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-14 | BMAD Party Mode | Initial proposal |

