# Stigmergic Colony Evolution: AlphaEvolve-Powered Self-Improving Infrastructure

**Author:** Root  
**Date:** 2026-01-22  
**Status:** Draft v2 (Complete Rewrite Based on Deeper Research)  
**Inspired by:** DeepMind AlphaEvolve (arXiv:2506.13131), Ant Colony Evolutionary Adaptation

---

## The Ant Colony Insight

> *"What will ants, under extremely difficult conditions, do? Evolve to fit into the ecosystem over millions of years."*

Ants don't just use stigmergy — **stigmergy itself evolved**. The pheromone chemistry, the signal decay rates, the caste proportions, the foraging algorithms, the nest architecture — all emerged through evolutionary pressure over millions of years.

**Cyber-Red's stigmergic coordination layer is currently static.** We designed the signal handling, the propagation rules, the agent coordination patterns. But like a first-generation ant colony, we're limited by our initial design.

**The vision:** Apply AlphaEvolve's proven paradigm to evolve the stigmergic infrastructure itself — not just prompts, but the **actual Python code** that implements coordination, signal processing, agent spawning, and emergent behavior.

---

## The Two-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ENGAGEMENT (LIVE LAYER)                                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STIGMERGIC COORDINATION (Running)                                   │    │
│  │                                                                      │    │
│  │  Agents ──► Actions ──► Findings ──► Signals ──► Agent Reactions    │    │
│  │     │                                                    │           │    │
│  │     └─────────── decision_context (traced) ──────────────┘           │    │
│  │                                                                      │    │
│  │  ╔═══════════════════════════════════════════════════════════════╗  │    │
│  │  ║               METRICS COLLECTION (Continuous)                  ║  │    │
│  │  ║  • Signal propagation latency                                  ║  │    │
│  │  ║  • Emergence chains (decision_context depth)                   ║  │    │
│  │  ║  • Attack path success rates                                   ║  │    │
│  │  ║  • Agent coordination efficiency                               ║  │    │
│  │  ║  • Novel vs redundant discoveries                              ║  │    │
│  │  ╚═══════════════════════════════════════════════════════════════╝  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                       Metrics Flow                                           │
│                              │                                               │
└──────────────────────────────┼───────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EVOLUTION (OFFLINE LAYER)                                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  EVOLUTIONARY DATABASE                                               │    │
│  │  • Population of stigmergic infrastructure variants                 │    │
│  │  • Fitness history from real engagements                            │    │
│  │  • Lineage tracking (parent→child mutations)                        │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                   │                                          │
│  ┌────────────────────────────────▼────────────────────────────────────┐    │
│  │  MUTATION ENGINE (LLM-Powered)                                       │    │
│  │                                                                      │    │
│  │  ┌───────────────────┐    ┌────────────────────┐                    │    │
│  │  │ FAST MODEL        │    │ DEEP MODEL         │                    │    │
│  │  │ (Breadth: Gemini  │    │ (Depth: DeepSeek   │                    │    │
│  │  │  Flash / Llama)   │    │  R1 / o3-mini)     │                    │    │
│  │  │                   │    │                    │                    │    │
│  │  │ Generates many    │    │ Refines promising  │                    │    │
│  │  │ code variants     │    │ variants deeply    │                    │    │
│  │  └───────────────────┘    └────────────────────┘                    │    │
│  │                                                                      │    │
│  │  Proposes ACTUAL CODE CHANGES to:                                   │    │
│  │  • src/cyberred/agents/base.py (signal handling)                    │    │
│  │  • src/cyberred/core/events.py (pub/sub patterns)                   │    │
│  │  • src/cyberred/orchestration/spawner.py (agent ratios)             │    │
│  │  • src/cyberred/orchestration/aggregator.py (emergence patterns)    │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                   │                                          │
│  ┌────────────────────────────────▼────────────────────────────────────┐    │
│  │  EVALUATOR POOL (Cyber Range)                                        │    │
│  │                                                                      │    │
│  │  For each code variant:                                             │    │
│  │  1. Deploy variant to isolated test environment                     │    │
│  │  2. Run standardized engagement against cyber range                 │    │
│  │  3. Collect fitness metrics                                         │    │
│  │  4. Compare against baseline and other variants                     │    │
│  │                                                                      │    │
│  │  SAFETY GATE: Reject any variant that:                              │    │
│  │  • Fails static analysis (syntax, type errors)                      │    │
│  │  • Fails unit tests                                                 │    │
│  │  • Produces scope violations                                        │    │
│  │  • Regresses >20% on any core metric                                │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                   │                                          │
│  ┌────────────────────────────────▼────────────────────────────────────┐    │
│  │  SELECTION (MAP-Elites + Islands)                                    │    │
│  │                                                                      │    │
│  │  MAP-Elites: Maintain elites across multiple feature dimensions:    │    │
│  │  • Efficiency axis (vulns/time)                                     │    │
│  │  • Emergence axis (chain depth)                                     │    │
│  │  • Diversity axis (technique coverage)                              │    │
│  │                                                                      │    │
│  │  Islands: 4-8 populations evolving semi-independently              │    │
│  │  • Ring topology with periodic migration                            │    │
│  │  • Prevents premature convergence                                   │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                   │                                          │
│                            Best Variant                                      │
│                                   │                                          │
└───────────────────────────────────┼──────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   HUMAN REVIEW (Optional)     │
                    │   Auto-deploy if confidence   │
                    │   >95% and all tests pass     │
                    └───────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   NEXT ENGAGEMENT RUNS WITH   │
                    │   EVOLVED INFRASTRUCTURE      │
                    └───────────────────────────────┘
```

---

## What Actually Evolves

Unlike prompt-only evolution, we're evolving **the algorithms that define stigmergic behavior**:

### 1. Signal Handling Logic

**Current (static):**
```python
# src/cyberred/agents/base.py
def on_finding_signal(self, finding: Finding):
    if finding.severity == "critical":
        self.priority_queue.insert(0, finding.target)
    else:
        self.priority_queue.append(finding.target)
```

**Evolution could discover:**
```python
# Evolved variant - emergent from successful engagements
def on_finding_signal(self, finding: Finding):
    # Evolved: exponential decay based on signal age
    freshness = exp(-(time.now() - finding.timestamp).seconds / 300)
    priority = finding.severity_score * freshness * self._exploitation_weight
    
    # Evolved: probabilistic swarming based on colony state  
    if random.random() < (priority / self.colony_saturation):
        self.redirect_to_target(finding.target)
    else:
        self.continue_current_task()
```

### 2. Agent Spawning Ratios

**Current (static):**
```python
# src/cyberred/orchestration/spawner.py
SPAWN_RATIOS = {
    "recon": 0.4,
    "exploit": 0.35,
    "postex": 0.15,
    "wireless": 0.1
}
```

**Evolution could discover:** Dynamic ratios that adapt to engagement phase:
```python
# Evolved spawning logic
def calculate_spawn_ratios(self, phase: str, progress: float):
    if phase == "reconnaissance" and progress < 0.3:
        return {"recon": 0.7, "exploit": 0.2, "postex": 0.05, "wireless": 0.05}
    elif self.critical_vulns_found > 5:
        return {"recon": 0.1, "exploit": 0.6, "postex": 0.25, "wireless": 0.05}
    # ... evolved decision tree
```

### 3. Emergence Cascade Patterns

**Current (static):**
```python
# Fixed cascade depth
MAX_CASCADE_DEPTH = 5
```

**Evolution could discover:** Adaptive cascade limits based on target density, signal quality, and swarm state.

### 4. Pheromone Dynamics (Signal Decay)

**Current (static):**
```python
# Fixed TTL for Redis signals
SIGNAL_TTL_SECONDS = 300
```

**Evolution could discover:** Variable decay rates per signal type, per target type, per phase.

---

## Fitness Function: Colony Success

The fitness function measures **collective swarm behavior**, not individual agents:

| Metric | Weight | Formula |
|--------|--------|---------|
| **Objective Completion** | 0.25 | `objective_achieved ? 1.0 : progress_percentage` |
| **Efficiency** | 0.20 | `vulns_found / (agent_count * time_hours)` |
| **Emergence Score** | 0.20 | `novel_chains / total_chains` (per NFR35) |
| **Chain Depth** | 0.15 | `avg(decision_context_depth)` |
| **Coverage** | 0.10 | `vulns_found / known_vulns_in_range` |
| **Resource Efficiency** | 0.10 | `1 / (redis_ops + llm_calls)` |

### Hard Constraints (Reject if violated)

- **Scope violations = 0** (absolute)
- **All existing tests pass** (no regressions)
- **Kill switch latency < 1s** (safety invariant)
- **No new syntax/type errors** (static analysis gate)

---

## Integration with OpenEvolve

AlphaEvolve's architecture has an open-source implementation: [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve)

We can leverage this directly:

```yaml
# evolution/config.yaml (OpenEvolve-compatible)

database:
  type: file_based
  storage_dir: ~/.cyber-red/evolution/db
  
llm:
  primary:
    model: deepseek-r1:latest
    base_url: ${LLM_API_URL}
  secondary:
    model: llama-3.3-70b
    base_url: ${LLM_API_URL}
    
evaluator:
  type: cyber_range
  range_compose: ./cyber-range/docker-compose.yml
  metrics_collector: ./evolution/metrics.py
  timeout: 1800  # 30 min per evaluation
  
selection:
  type: map_elites
  dimensions:
    - name: efficiency
      bins: 10
    - name: emergence
      bins: 10
  islands: 4
  migration_interval: 10  # generations
  
evolvable_files:
  - src/cyberred/agents/base.py
  - src/cyberred/core/events.py
  - src/cyberred/orchestration/spawner.py
  - src/cyberred/orchestration/aggregator.py
  - src/cyberred/orchestration/emergence/tracker.py
```

---

## The Evolution Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     EVOLUTION CYCLE (Offline)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. COLLECT: Gather metrics from completed engagements                  │
│     │                                                                    │
│  2. SAMPLE: Select programs from database using MAP-Elites              │
│     │                                                                    │
│  3. PROMPT: Create context-rich mutation prompts with:                  │
│     │        • Current best code                                        │
│     │        • Fitness scores and why they failed/succeeded             │
│     │        • Problem description (improve emergence by 5%)            │
│     │                                                                    │
│  4. MUTATE: LLM generates code variants (diff format)                   │
│     │                                                                    │
│  5. VALIDATE: Static analysis, type checking, unit tests               │
│     │        (REJECT failures immediately)                              │
│     │                                                                    │
│  6. EVALUATE: Deploy to cyber range, run standardized engagement        │
│     │        Collect fitness metrics                                    │
│     │                                                                    │
│  7. SELECT: Add to database if novel elite or beats existing elite      │
│     │                                                                    │
│  8. MIGRATE: Periodically share elites between island populations       │
│     │                                                                    │
│  └── REPEAT until convergence or iteration limit                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### Phase 1: Metrics Infrastructure (Foundation)

Add comprehensive metrics collection to live stigmergic layer:

```python
# src/cyberred/evolution/metrics.py
@dataclass
class EngagementMetrics:
    # Core performance
    vulns_found: int
    time_to_objective: float
    objective_achieved: bool
    
    # Emergence quality
    emergence_chains: List[ChainMetric]
    avg_chain_depth: float
    novel_chain_ratio: float
    
    # Coordination efficiency
    signal_count: int
    signal_response_rate: float
    cascade_amplification: float
    
    # Resource utilization
    agent_count: int
    llm_calls: int
    redis_operations: int
```

### Phase 2: Evolution Pipeline

Integrate OpenEvolve with Cyber-Red:

```
src/cyberred/evolution/
├── __init__.py
├── config.py           # Evolution configuration
├── database.py         # MAP-Elites program database
├── sampler.py          # Context-rich prompt generation
├── mutator.py          # LLM-driven code mutation
├── evaluator.py        # Cyber range integration
├── selector.py         # MAP-Elites selection
├── runner.py           # Evolution loop orchestrator
└── safety.py           # Validation gates
```

### Phase 3: Automated Evolution Cycles

- Post-engagement trigger: After each real engagement, queue evolution cycle
- Weekly scheduled evolution: Batch evolution using accumulated metrics
- TUI integration: Monitor evolution progress, view lineage, rollback

---

## Proposed FRs and NFRs

### New Functional Requirements

- **FR89:** System collects colony-level metrics during engagement (signal propagation, emergence chains, coordination efficiency)
- **FR90:** Evolution layer can propose code changes to stigmergic infrastructure
- **FR91:** All code variants validated against static analysis, type checking, and unit tests before evaluation
- **FR92:** Evolution evaluates variants against standardized cyber range scenarios
- **FR93:** Operator can view evolution history, lineage, and fitness progression in TUI
- **FR94:** Operator can rollback to any previous generation
- **FR95:** System auto-deploys evolved code if confidence >95% and all gates pass

### New Non-Functional Requirements

- **NFR40:** Evolved code must pass 100% of existing tests (no regressions)
- **NFR41:** Evolution cycle (50 generations) completes in <24 hours
- **NFR42:** Evolved stigmergic infrastructure achieves >10% fitness improvement over baseline within 20 generations
- **NFR43:** Kill switch latency invariant (<1s) preserved across all evolved variants

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **Degenerate mutations** | Static analysis + unit tests as first gate |
| **Catastrophic regressions** | Mandatory comparison against baseline; reject if >20% worse |
| **Scope safety violations** | Scope validator code is NEVER evolved (frozen) |
| **Infinite loops / hung agents** | Timeout enforcement in evaluator |
| **Overfitting to cyber range** | Diverse range scenarios + held-out test sets |
| **Runaway evolution** | Human review gate for production deployment |

---

## The Meta-Insight

> **Stigmergy + Evolution = Adaptive Intelligence**

Just as ant colonies evolved their pheromone systems over millions of years, Cyber-Red's swarm can evolve its coordination algorithms over engagements.

Each engagement is natural selection. Each successful attack path strengthens the stigmergic infrastructure that produced it. The swarm doesn't just coordinate — **it adapts**.

This is not prompt engineering. This is not parameter tuning. This is **infrastructure evolution** — the algorithms themselves improve.

---

## Decision Points

> [!IMPORTANT]
> **Key decisions for stakeholder review:**

1. **Scope of evolvable code:** Which files are safe to evolve? (Recommend: everything EXCEPT scope validation, kill switch, authorization)

2. **Deployment strategy:** Auto-deploy with >95% confidence, or always require human review?

3. **Evolution cadence:** After each engagement? Weekly batch? On-demand?

4. **OpenEvolve vs custom:** Use OpenEvolve directly, or build custom pipeline?

---

*Document Status: Draft v2 – Awaiting Review*
