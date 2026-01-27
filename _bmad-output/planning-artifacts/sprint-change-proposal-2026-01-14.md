# Sprint Change Proposal — Epic 7 Agent Architecture Refactor

**Date:** 2026-01-14  
**Triggered by:** Stories 7.3–7.5 implementation deviated from architectural requirements  
**Proposal Type:** Major (requires PM/Architect involvement)

---

## 1. Issue Summary

### Problem Statement

Epic 7 ("Agent Framework & Stigmergic Coordination") was implemented with **hardcoded tool sequences** instead of the architecturally-required **LLM-driven tool selection**. This fundamentally undermines the emergence validation Hard Gate (NFR35-37) that requires measurable emergent behavior.

### How Discovered

Analysis of the refactor proposal (`epic-7-agent-refactor-proposal.md`) and implementation artifacts revealed:

- ReconAgent, ExploitAgent, PostExAgent use static tool lists (`tool_sequence = ["nmap", "masscan", ...]`)
- Agents generate commands via fixed `_generate_*_command()` methods instead of LLM calls
- Only ~15 tools accessible vs. the 1,556+ tool manifest available

### Evidence

| Requirement | Architecture Intent | Current Implementation |
|-------------|---------------------|------------------------|
| **FR31** | 600+ tools via `kali_execute()` | ~15 hardcoded tools |
| **FR32** | Agents generate bash/Python via LLM | Static command templates |
| **NFR35** | >20% novel attack chains | No diversity mechanism |
| **NFR37** | 100% `decision_context` population | Implemented (passes) |

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact | Description |
|------|--------|-------------|
| **Epic 7** | MAJOR | Stories 7.1, 7.3, 7.4, 7.5 require supersession with -v2 versions |
| **Epic 8** | MODERATE | Director Ensemble feedback loops depend on diverse agent behavior |
| **Epic 9** | MAJOR | Emergence validation relies on behavioral diversity |

### Story Impact

| Story | Current Status | Required Action |
|-------|----------------|-----------------|
| **7.1** | done | SUPERSEDE with 7.1-v2 (add LLM tool selection) |
| **7.3** | done | SUPERSEDE with 7.3-v2 (ReconAgent refactor) |
| **7.4** | done | SUPERSEDE with 7.4-v2 (ExploitAgent refactor) |
| **7.5** | done | SUPERSEDE with 7.5-v2 (PostExAgent refactor) |
| **7.18** | not started | CRITICAL DEPENDENCY — implement first (AgentRole + PromptLibrary) |
| **7.19–7.23** | not started | Proceed after 7.18 (5 additional agent types) |

### Artifact Conflicts

| Artifact | Conflict | Resolution |
|----------|----------|------------|
| **epics-stories.md** | Story numbering conflicts with refactor proposal | Reconcile: keep 7.18 as AgentRole/PromptLibrary |
| **sprint-status.yaml** | 7.1, 7.3, 7.4, 7.5 marked "done" | Update status to "superseded" |
| **Implementation artifacts** | 7-1, 7-3, 7-4, 7-5 files | Archive as reference, create -v2 versions |

---

## 3. Recommended Path Forward

### Selected Approach: Story Supersession Pattern

**Rationale:**
- Changes are architectural, not incremental — in-place refactor would obscure history
- Test migration needs clear before/after boundary
- -v2 stories can reference what they supersede for context

### Why not other options?

| Option | Verdict | Reason |
|--------|---------|--------|
| **Direct Adjustment** | Not viable | Changes are too fundamental |
| **Rollback** | Not viable | Code is functional, just wrong approach |
| **MVP Review** | Not viable | PRD requires LLM-driven agents for emergence |

### Effort Estimate

| Phase | Stories | Points | Complexity |
|-------|---------|--------|------------|
| Phase 0: Dependency | 7.18 | 5 | Medium |
| Phase 1: Base | 7.1-v2 | 8 | High |
| Phase 2: Refactors | 7.3-v2, 7.4-v2, 7.5-v2 | 13 (total) | Medium |
| Phase 3: New Types | 7.19–7.23 | 15 (total) | Low (follow pattern) |
| **Total** | **10 stories** | **~41 points** | — |

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Test migration breaks coverage | Medium | High | Migrate tests alongside code, track coverage delta |
| LLM selection introduces latency | Low | Medium | Cache `--help` output per tool, async selection |
| Emergence Hard Gate still fails | Low | Critical | Design 8-role diversity specifically for novelty |

---

## 4. Detailed Change Proposals

### 4.1 Story Status Updates in `sprint-status.yaml`

```yaml
# OLD:
7.1:
  status: done
7.3:
  status: done
7.4:
  status: done
7.5:
  status: done

# NEW:
7.1:
  status: superseded
  superseded_by: "7.1-v2"
7.3:
  status: superseded
  superseded_by: "7.3-v2"
7.4:
  status: superseded
  superseded_by: "7.4-v2"
7.5:
  status: superseded
  superseded_by: "7.5-v2"
7.1-v2:
  status: ready
  depends_on: ["7.18"]
7.3-v2:
  status: ready
  depends_on: ["7.1-v2"]
7.4-v2:
  status: ready
  depends_on: ["7.1-v2"]
7.5-v2:
  status: ready
  depends_on: ["7.1-v2"]
7.18:
  status: ready
  priority: critical
```

**Rationale:** Preserves implementation history while unblocking new work.

### 4.2 New Story Files Required

| File | Description |
|------|-------------|
| `7-18-agent-role-and-prompt-library.md` | AgentRole enum (8 values) + PromptLibrary class |
| `7-1-v2-stigmergic-agent-llm-selection.md` | Refactored base class with LLM tool selection |
| `7-3-v2-recon-agent-refactor.md` | ReconAgent using LLM selection |
| `7-4-v2-exploit-agent-refactor.md` | ExploitAgent using LLM selection |
| `7-5-v2-postex-agent-refactor.md` | PostExAgent using LLM selection |

### 4.3 Architecture Updates Required

None — the architecture already specifies LLM-driven tool selection. This refactor aligns implementation with existing architecture.

---

## 5. Execution Order

```
PHASE 0: CRITICAL DEPENDENCY (Must Complete First)
├── 7.18: AgentRole Enum & PromptLibrary  ← START HERE
│   └── Creates: src/cyberred/agents/roles.py
│   └── Creates: src/cyberred/agents/prompts.py
│   └── Creates: src/cyberred/agents/prompts/*.md

PHASE 1: BASE REFACTOR
├── 7.1-v2: StigmergicAgent with LLM Tool Selection
│   └── Adds: select_tool(), generate_command() methods
│   └── Preserves: on_finding, on_signal, on_complete hooks

PHASE 2: AGENT REFACTORS (can parallelize after 7.1-v2)
├── 7.3-v2: ReconAgent Refactor
│   └── Removes: hardcoded tool_sequence
│   └── Removes: _generate_*_command() methods
├── 7.4-v2: ExploitAgent Refactor
├── 7.5-v2: PostExAgent Refactor

PHASE 3: NEW AGENT TYPES (can parallelize)
├── 7.19: WebAppAgent
├── 7.20: WirelessAgent
├── 7.21: ActiveDirectoryAgent
├── 7.22: CredentialAgent
├── 7.23: ForensicsAgent

PHASE 4: INTEGRATION
├── 7.6: SwarmRouter (routes to all 8 types)
├── 7.7: Dynamic Agent Spawner
├── 7.14: Emergence Validation Gate Test
```

---

## 6. Implementation Handoff

### Scope Classification: **MAJOR**

This change requires PM/Architect involvement due to:
- Fundamental architectural implications
- 10+ stories affected
- Hard Gate (emergence validation) at risk

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Architect** | Validate LLM tool selection design decisions |
| **SM** | Update sprint-status.yaml, manage backlog reordering |
| **Dev** | Implement refactored agents following TDD |
| **TEA** | Verify test migration maintains 100% coverage |

### Success Criteria

1. [ ] Story 7.18 completed — AgentRole enum and PromptLibrary available
2. [ ] Story 7.1-v2 completed — LLM tool selection working
3. [ ] Stories 7.3-v2, 7.4-v2, 7.5-v2 completed — All agents using LLM selection
4. [ ] Test coverage maintained at 100% (no regression)
5. [ ] Emergence Hard Gate (NFR35-37) passes in Story 7.14

---

## Approval

- [x] **User approval to proceed with refactor** ✅ Approved 2026-01-14T22:35:36Z

> [!IMPORTANT]
> Proceeding will mark 7.1, 7.3, 7.4, 7.5 as superseded and block new work on those stories.

---

*Generated via Correct Course workflow on 2026-01-14*
