# Swarms API Stability Research Report

**Date:** 2026-01-14  
**Researcher:** Automated via Party Mode  
**Current Version:** swarms v8.7.0 (installed)

---

## Executive Summary

**Risk Level: LOW** ✅

Our usage of `kyegomez/swarms` is minimal and compatible. The breaking changes in v8.5.0 do NOT affect Cyber-Red because:

1. We manage our own state via Redis EventBus (not Swarms' removed backends)
2. We extend `Agent` minimally — only using `agent_name` and `system_prompt`
3. We don't use Swarms' LLM integration — we have our own `LLMGateway`

---

## Research Findings

### 1. Breaking Changes in Swarms v8.5.0

| Change | Impact on Cyber-Red |
|--------|---------------------|
| **Redis backend removed** | ✅ **NO IMPACT** — We use `cyberred.core.events.EventBus`, not Swarms' Redis |
| **Supabase integration removed** | ✅ **NO IMPACT** — We don't use Supabase |
| **Personator merged into Agent** | ✅ **NO IMPACT** — We don't use Personator |
| **Legacy storage adapters removed** | ✅ **NO IMPACT** — We use `cyberred.storage` |
| **Docstring parser removed** | ✅ **NO IMPACT** — We don't use this |

### 2. Current Usage Analysis

**File:** `src/cyberred/agents/base.py`

```python
from swarms import Agent  # Line 11

class StigmergicAgent(Agent):
    def __init__(
        self, 
        agent_name: str,  # ✅ Stable attribute
        agent_id: str,    # Our custom attribute
        engagement_id: str,  # Our custom attribute
        event_bus: EventBus,  # Our custom attribute
        *args, 
        **kwargs
    ):
        kwargs['agent_name'] = agent_name
        super().__init__(*args, **kwargs)
```

**What we use from Swarms:**
- `agent_name` — ✅ Stable (documented attribute)
- `system_prompt` (via kwargs) — ✅ Optional, stable  
- `llm` (via kwargs) — ✅ Optional, stable

**What we DON'T use:**
- Swarms Memory system — ❌ (we use Redis via EventBus)
- Swarms tool execution — ❌ (we use `kali_execute()`)
- Swarms LLM integration — ❌ (we use `LLMGateway`)
- Swarms state persistence — ❌ (we use SQLite checkpoints)

### 3. Potential Conflicts

| Concern | Assessment | Action Needed |
|---------|------------|---------------|
| `Agent.run()` vs `StigmergicAgent.execute()` | **Compatible** — We don't override `run()` | None |
| Memory system overlap | **Compatible** — Swarms Memory is optional | None |
| Tool system overlap | **Compatible** — We bypass Swarms tools entirely | None |
| LLM integration | **Compatible** — We pass `llm` via kwargs or manage externally | None |

### 4. Features to Consider Adopting

| Feature | Description | Recommendation |
|---------|-------------|----------------|
| `handoffs` | Agent-to-agent task delegation | **CONSIDER** — Could replace manual stigmergic hand-off |
| `mcp_url` | Model Context Protocol integration | **DEFER** — Not needed currently |
| `reasoning_enabled` | Built-in reasoning traces | **CONSIDER** — Could aid decision_context |
| `fallback_models` | Automatic model fallback | **DEFER** — We have our own LLM tier system |

---

## Recommendations

### Immediate Actions

1. **✅ No breaking changes needed** — Current implementation is compatible
2. **✅ Keep `swarms>=8.0.0` in pyproject.toml** — Allows minor updates
3. **Add version ceiling** (optional) — Consider `swarms>=8.0.0,<9.0.0` to prevent major breaking changes

### Future Considerations

1. **Monitor v9.0 announcements** — Major version may have breaking changes
2. **Consider `handoffs` feature** — Could simplify agent collaboration patterns
3. **Evaluate `reasoning_enabled`** — May provide free decision tracing

---

## Conclusion

**Verdict: SAFE TO PROCEED** ✅

The Swarms framework is stable for our use case. Our architecture specifically designed for minimal coupling:

- We inherit from `Agent` but don't rely on its internal state management
- We handle coordination via our own EventBus (Redis Pub/Sub)
- We handle LLM calls via our own `LLMGateway`
- We handle state via our own checkpoint system

This "thin wrapper" approach insulates us from Swarms internal changes.

---

## Checklist Status

- [x] Review Swarms changelog for v8.0.0+ breaking changes
- [x] Check if `Agent` base class API is stable
- [x] Identify deprecated methods we may be using → None found
- [x] Does `swarms.Agent.run()` conflict with our `execute()`? → No
- [x] Does Swarms' Memory system conflict with our Redis-based state? → No
- [x] Does Swarms' tool system overlap with `kali_execute()`? → No
- [x] Does Swarms' internal LLM integration conflict with our `LLMGateway`? → No
- [x] Are there new Swarms v8.0+ features useful for our use case? → `handoffs`, `reasoning_enabled` worth watching
