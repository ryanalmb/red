# Cyber-Red v2 Migration Research

**Date:** 2025-12-26
**Status:** Complete
**Source:** Party Mode Research Session

---

## 1. Executive Summary

This document captures the technical research, analysis, and architectural decisions made during the v1 → v2 migration planning session. It serves as the foundational research for the Architecture and PRD documents.

**Key Migration Decisions:**
- Migrate from custom orchestrator to **Swarms framework**
- Replace Council of Experts with **Multi-LLM Director Ensemble**
- Implement **stigmergic P2P agent coordination**
- Scale from ~100 agents to **10,000+**
- Replace AI Critic with **hard-gate scope validator**

---

## 2. Swarms Framework Analysis

### 2.1 Framework Overview

**Swarms** is an enterprise-grade, production-ready multi-agent orchestration framework:
- 100+ million agent interactions per day capacity
- 20,000+ active enterprises
- Supports thousands of concurrent agents

**Repository:** https://github.com/kyegomez/swarms
**Documentation:** https://docs.swarms.world

### 2.2 Core Architecture

#### Agent Definition

```python
from swarms import Agent

agent = Agent(
    # Identity
    agent_name="Ghost-Agent",
    agent_description="Offensive security execution agent",

    # LLM Configuration
    model_name="deepseek-ai/deepseek-v3.2",
    temperature=0.7,
    max_tokens=4096,

    # Execution Control
    max_loops=1,
    stopping_token="<DONE>",

    # Tools
    tools=[nmap_tool, nuclei_tool, sqlmap_tool],
    tool_choice="auto",
    execute_tool=True,

    # Safety
    safety_prompt_on=True,
)
```

#### Key Constructor Parameters

| Category | Parameters | Description |
|----------|------------|-------------|
| Identity | `agent_name`, `agent_description`, `role` | Agent identification |
| LLM Config | `model_name`, `temperature`, `max_tokens` | Language model settings |
| Execution | `max_loops`, `stopping_condition`, `stopping_token` | Runtime behavior |
| Memory | `long_term_memory`, `context_length` | State management |
| Tools | `tools`, `mcp_url`, `tool_choice`, `execute_tool` | Function calling |
| Safety | `safety_prompt_on`, `response_filters` | Governance controls |

### 2.3 Orchestration Patterns

#### HierarchicalSwarm (Director Delegation)

```python
from swarms import Agent, HierarchicalSwarm

swarm = HierarchicalSwarm(
    name="CyberRed-Director",
    agents=[recon_agent, vuln_agent, exploit_agent],
    max_loops=50,
    director_model_name="deepseek-ai/deepseek-v3.2",
    director_feedback_on=True,  # Iterative refinement
)

result = swarm.run(task="Achieve admin access on target")
```

**Execution Flow:**
1. Director receives task and creates execution plan
2. Director distributes orders to specialized agents
3. Workers execute assigned subtasks
4. Director evaluates results and issues new orders
5. Loop until objective achieved

#### MixtureOfAgents (Expert Synthesis)

```python
from swarms import Agent, MixtureOfAgents

moa = MixtureOfAgents(
    agents=[strategist, analyst, ghost],
    final_agent=synthesizer,
    layers=1,  # Single pass for speed
    verbose=True
)
```

**Key Feature:** Multiple experts synthesized — NO VETO, just aggregation.

#### AgentRearrange (Dynamic Relationships)

```python
from swarms import AgentRearrange

swarm = AgentRearrange(
    agents=[agent1, agent2, agent3],
    flow="Agent1 -> Agent2 -> Agent3",  # Sequential
    # flow="Agent1, Agent2 -> Agent3",  # Parallel then sequential
    team_awareness=True,
)
```

**Flow Syntax:**
- `->` : Sequential execution
- `,` : Parallel execution
- Combine: `"A, B -> C -> D, E -> F"`

#### ConcurrentWorkflow (Parallel Execution)

```python
from swarms import ConcurrentWorkflow

workflow = ConcurrentWorkflow(
    name="Ghost-Swarm",
    agents=[create_ghost_agent(i) for i in range(100)],
    max_loops=1,
    show_dashboard=True
)
```

**Resource Management:**
- Max workers: 95% of available CPU cores
- Status tracking: `pending`, `running`, `completed`, `error`
- Automatic cleanup

#### GraphWorkflow (DAG-Based)

```python
from swarms import GraphWorkflow

workflow = GraphWorkflow()
workflow.add_node("collector", data_collector)
workflow.add_node("analyzer1", analyzer1)
workflow.add_node("analyzer2", analyzer2)
workflow.add_edge("collector", "analyzer1")
workflow.add_edge("collector", "analyzer2")  # Fan-out
workflow.compile()
```

### 2.4 Tool Integration

**Method 1: Callable Functions**

```python
def nmap_scan(target: str, ports: str = "1-1000") -> str:
    """
    Run nmap scan against target.

    Args:
        target: IP or hostname to scan
        ports: Port range to scan

    Returns:
        JSON string with scan results
    """
    # Implementation via MCP adapter
    return json.dumps(results)

agent = Agent(
    agent_name="Recon-Agent",
    tools=[nmap_scan],
    tool_choice="auto",
    execute_tool=True,
)
```

**Method 2: MCP Integration**

```python
agent = Agent(
    agent_name="MCP-Agent",
    mcp_url="http://localhost:8000/mcp",
    output_type="json",
)
```

### 2.5 Governance Controls

**Stopping Conditions:**

```python
def scope_check(response: str) -> bool:
    """Returns True to stop execution."""
    if "out_of_scope" in response.lower():
        return True
    return False

agent = Agent(
    stopping_condition=scope_check,
    max_loops=10
)
```

**Kill Switch:**

```python
# Token-based stop
agent = Agent(
    stopping_token="STOP",
    preset_stopping_token=True  # Enables "<DONE>" sentinel
)

# Swarm-level control
swarm.pause_agent("Agent-1")
swarm.stop_agent("Agent-1")
swarm.reset_all_agents()
```

---

## 3. Current Architecture Analysis (v1)

### 3.1 Component Overview

| Component | File | Role | Issue |
|-----------|------|------|-------|
| `Orchestrator` | `src/core/orchestrator.py` | Central coordinator | Bottleneck |
| `CouncilOfExperts` | `src/core/council.py` | 3-model voting | Causes refusals |
| `WarRoom` | `src/core/war_room.py` | Architect + Engineer | Sequential calls |
| `GhostAgent` | `src/agents/ghost_agent.py` | Attack executor | Limited to 100 IDs |
| `WorkerPool` | `src/core/worker_pool.py` | Docker containers | Fixed 10 containers |
| `EventBus` | `src/core/event_bus.py` | Pub/sub | No agent awareness |

### 3.2 Pain Points Identified

1. **Too Slow:** Sequential Council voting (3 LLM calls per decision)
2. **Too Few Agents:** Limited to ~100 (ID cycling)
3. **Poor Coordination:** Agents unaware of other processes
4. **Excessive Refusals:** Critic blocks legitimate operations (currently bypassed)
5. **Workflow Bottleneck:** Central orchestrator limits parallelism

### 3.3 Council Bypass Evidence

From `council.py` lines 106-130:
```python
# HITL BYPASSED FOR TESTING - auto-approve all targets
# TODO: Re-enable after flow is verified
await brain_log("✅ HITL bypassed - target auto-approved", "COUNCIL")

# Skip Critic for now - just return approved
# TODO: Re-enable Critic after flow is verified
await brain_log("✅ Strategy approved (Critic bypassed for testing)", "COUNCIL")
```

**Conclusion:** The Critic's veto-based model is fundamentally broken for offensive security.

---

## 4. Gap Analysis: v1 → Swarms

### 4.1 Component Mapping

| Cyber-Red v1 | Current Role | Swarms Equivalent | Action |
|--------------|--------------|-------------------|--------|
| `Orchestrator` | Central coordinator | `SwarmRouter` / `HierarchicalSwarm` | Replace |
| `CouncilOfExperts` | 3-model voting | **DELETE** → `MixtureOfAgents` | Delete |
| `WarRoom` | Architect + Engineer | Merge into Director | Merge |
| `GhostAgent` | Attack executor | Swarms `Agent` with tools | Migrate |
| `WorkerPool` | Docker containers | Keep (tool execution) | Preserve |
| `EventBus` | Pub/sub | Swarms + Redis | Hybrid |
| `Critic` | Veto gate | **DELETE** → Hard-gate validator | Delete |

### 4.2 Architecture Shift

**FROM:**
```
Orchestrator → Council → WarRoom → Agent → Tools
     ↓
   (bottleneck)
```

**TO:**
```
Director Ensemble → Agent Swarm → Tools
        ↓
   (stigmergic memory)
        ↓
   (shared findings)
```

---

## 5. Multi-LLM Director Ensemble Design

### 5.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DIRECTOR ENSEMBLE                             │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ DeepSeek    │  │ Kimi K2     │  │ MiniMax M2  │              │
│  │ v3.2        │  │ Instruct    │  │             │              │
│  │             │  │             │  │             │              │
│  │ Role:       │  │ Role:       │  │ Role:       │              │
│  │ Strategic   │  │ Deep        │  │ Creative    │              │
│  │ Planning    │  │ Reasoning   │  │ Evasion     │              │
│  │ + Code Gen  │  │ + Analysis  │  │ + Lateral   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          ▼                                       │
│                ┌─────────────────┐                               │
│                │   SYNTHESIZER   │                               │
│                │  (Fast model)   │                               │
│                │                 │                               │
│                │ Aggregates 3    │                               │
│                │ perspectives    │                               │
│                │ into action     │                               │
│                └─────────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Implementation

```python
from swarms import Agent, MixtureOfAgents

# Three perspective agents with different LLMs
deepseek_strategist = Agent(
    agent_name="DeepSeek-Strategist",
    model_name="deepseek-ai/deepseek-v3.2",
    system_prompt="""You are the Strategic Planner.
    Focus on: Attack sequencing, tool selection, kill chain progression.
    Output: Prioritized action recommendations with reasoning."""
)

kimi_analyst = Agent(
    agent_name="Kimi-Analyst",
    model_name="moonshotai/kimi-k2-instruct",
    system_prompt="""You are the Deep Reasoning Analyst.
    Focus on: Pattern analysis, vulnerability chaining, edge cases.
    Use <thinking> tags for extended reasoning.
    Output: Risk-assessed recommendations with confidence scores."""
)

minimax_ghost = Agent(
    agent_name="MiniMax-Ghost",
    model_name="minimaxai/minimax-m2",
    system_prompt="""You are the Creative Evasion Specialist.
    Focus on: WAF bypass, lateral movement, unconventional vectors.
    Output: Alternative approaches the others might miss."""
)

# Fast synthesizer (aggregates, doesn't veto)
synthesizer = Agent(
    agent_name="Director-Synthesizer",
    model_name="meta/llama-3.3-70b-instruct",
    system_prompt="""You synthesize 3 expert perspectives into ONE action plan.

    Rules:
    - NO VETO. Combine the best elements from each.
    - Prioritize by: confidence score, novelty, resource efficiency
    - Output JSON: {"tools": [...], "targets": [...], "reasoning": "..."}"""
)

# The Director Ensemble
director_ensemble = MixtureOfAgents(
    agents=[deepseek_strategist, kimi_analyst, minimax_ghost],
    final_agent=synthesizer,
    layers=1,
    verbose=True
)
```

### 5.3 Key Differences from v1 Council

| Aspect | v1 Council | v2 Director Ensemble |
|--------|------------|----------------------|
| Decision model | Veto (Critic blocks) | Synthesis (Director aggregates) |
| Iteration | Fixed loop count | Until objective achieved |
| Parallelism | Sequential voting | Parallel suggestions |
| Failure mode | Excessive refusals | Always produces action |

---

## 6. Stigmergic P2P Coordination Design

### 6.1 Concept

**Stigmergy:** Agents communicate indirectly through shared environment modifications (like ants leaving pheromone trails).

### 6.2 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    REDIS SHARED MEMORY                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  findings:{target}:ports     → [22, 80, 443, 8080]              │
│  findings:{target}:vulns     → [{cve, severity, service}, ...]  │
│  findings:{target}:creds     → [{user, hash, source}, ...]      │
│  findings:{target}:shells    → [{type, access_level}, ...]      │
│                                                                  │
│  agents:active               → {agent_id: {phase, target, ...}} │
│  agents:discoveries          → PubSub channel for real-time     │
│                                                                  │
│  targets:graph               → NetworkX-serialized attack graph │
│  targets:priority_queue      → Sorted by exploitability score   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 Implementation

```python
class StigmergicAgent(SwarmsAgent):
    async def run_loop(self):
        while active:
            # 1. Check shared memory for relevant discoveries
            new_findings = await self.redis.get_since(self.last_check)

            # 2. React to environment changes (stigmergic trigger)
            for finding in new_findings:
                if self.should_pivot(finding):
                    await self.pivot_to(finding)

            # 3. Execute my current task
            results = await self.execute_tools()

            # 4. Publish MY discoveries (leave pheromone trail)
            await self.redis.publish("agents:discoveries", results)
```

### 6.4 Emergent Behavior Example

1. **Recon Agent #1** finds port 445 open → publishes to `findings:target:ports`
2. **SMB Specialist Agent** sees 445 → auto-spawns
3. **SMB Agent** finds EternalBlue vuln → publishes to `findings:target:vulns`
4. **Exploit Agent** sees critical vuln → attempts exploit
5. **All agents** see shell obtained → pivot to post-exploitation

**No central coordinator told them to do this.**

---

## 7. Hard-Gate Scope Validator Design

### 7.1 Concept

Replace AI-based Critic (semantic "is this safe?") with **deterministic scope validation**.

### 7.2 Implementation

```python
def scope_validator(action: dict, roe: dict) -> dict:
    """
    HARD GATE - No AI interpretation.
    Replaces the Critic's semantic analysis.
    """
    target = action.get("target", "")

    # IP/Domain whitelist check (deterministic)
    if not is_in_scope(target, roe["allowed_targets"]):
        return {"blocked": True, "reason": "Target not in scope"}

    # Forbidden action check (deterministic)
    if action.get("type") in roe["forbidden_actions"]:
        return {"blocked": True, "reason": "Action type forbidden"}

    # PASS - no semantic "is this safe?" nonsense
    return {"blocked": False}
```

### 7.3 Key Differences

| Aspect | v1 Critic | v2 Hard-Gate |
|--------|-----------|--------------|
| Type | AI semantic analysis | Deterministic rules |
| Decision | "Is this safe?" | "Is this in scope?" |
| False positives | High (blocked legitimate ops) | Zero (rules are clear) |
| Speed | Slow (LLM call) | Instant (rule check) |

---

## 8. WiFi Pivot Architecture

### 8.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CYBER-RED (Cloud/VPS)                        │
│                                                                  │
│  Director Ensemble → Agent Swarm → Stigmergic Memory            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Secure C2 Channel
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PRE-DEPLOYED DROP BOX (On-Site)                 │
│                                                                  │
│  • Raspberry Pi / Mini PC / Compromised Host                    │
│  • WiFi capability (aircrack-ng, wifite, kismet)                │
│  • Receives commands from Cyber-Red                             │
│  • Relays captured handshakes/credentials back                  │
│  • Can pivot to internal network via WiFi                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ WiFi Attack
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TARGET WIFI NETWORK                           │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Supported Models

1. **Pre-Deployed Drop Box** — Physical device placed on-site (required for WiFi ops)
2. **Compromised Host Pivot** — Already-pwned machine with WiFi capability

### 8.3 Preconditions

- Drop box must be connected before WiFi scan enabled
- Drop box deployment is a manual, physical step by operator
- Authorization required for WiFi scope expansion

---

## 9. Migration Path

### Phase 1: Strangler Fig

```
├── Keep: WorkerPool, MCP Adapters, EventBus, Redis
├── Replace: Council → Director Ensemble
├── Replace: WarRoom → MixtureOfAgents specialists
└── Add: Swarms ConcurrentWorkflow for execution
```

### Phase 2: Stigmergic Layer

```
├── Add: Redis pub/sub for agent coordination
├── Add: Shared findings store
└── Modify: Agents subscribe to relevant channels
```

### Phase 3: Full Swarms Migration

```
├── Replace: Orchestrator → SwarmRouter
├── Replace: GhostAgent → Swarms Agent
└── Scale: 100 → 10,000+ agents
```

---

## 10. Tool Adapter Requirements

### 10.1 Current Adapters (6)

- `nmap_adapter.py`
- `nuclei_adapter.py`
- `sqlmap_adapter.py`
- `hydra_adapter.py`
- `ffuf_adapter.py`
- `nikto_adapter.py`

### 10.2 Required Adapters (50+)

| Category | Tools | Priority |
|----------|-------|----------|
| Reconnaissance | amass, subfinder, masscan, dnsrecon | P1 |
| Web | gobuster, dirb, wpscan, burp-cli | P1 |
| Exploit | metasploit, crackmapexec, impacket | P1 |
| Post-Ex | mimikatz, bloodhound, linpeas/winpeas | P1 |
| Network | responder, bettercap | P2 |
| Wireless | aircrack-ng, wifite, kismet | P1 |

---

## 11. Testing Requirements

### 11.1 Coverage Targets

| Type | Target |
|------|--------|
| Unit Tests | 100% |
| Integration Tests | 100% |
| E2E Tests | Full attack chain |
| Safety Tests | Scope enforcement |
| Scale Tests | 10,000 agents |
| WiFi Tests | Isolated wireless lab |

### 11.2 Test Infrastructure Needed

- Expanded Cyber Range (AD environment, wireless AP simulator)
- CI infrastructure for 10,000 agent load tests
- Docker images with all Kali tools pre-installed

---

## 12. References

- Swarms GitHub: https://github.com/kyegomez/swarms
- Swarms Docs: https://docs.swarms.world
- v1 Architecture: `docs/archive/v1/3-solutioning/architecture.md`
- v1 Product Brief: `docs/archive/v1/1-analysis/product-brief.md`

---

**Document Status:** Complete
**Next Steps:** Use this research to inform Architecture and PRD documents
