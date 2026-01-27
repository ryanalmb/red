# Live Evolution Proposal: Evolved Attack Code as Pheromones

**Author:** Root  
**Date:** 2026-01-22  
**Status:** Draft v2  
**Companion to:** [evolution-proposal.md](./evolution-proposal.md) (Offline Evolution)

---

## Executive Summary

OpenEvolve runs **during engagements**, generating **novel attack code** in real-time. The evolved code itself becomes a pheromone — distributed through the existing stigmergic pub/sub system. Agents receive evolved techniques, execute them against targets, and success/failure signals provide fitness feedback. **True evolution of attack algorithms, not parameter tuning.**

---

## Core Principle: Code IS the Gene

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  THE EVOLVED CODE IS THE GENETIC MATERIAL                                    │
│  THE PHEROMONE SYSTEM IS THE GENE TRANSFER MECHANISM                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OpenEvolve generates:                                                      │
│  • Novel WAF bypass techniques                                              │
│  • Mutated payload encodings                                                │
│  • New exploit chain sequences                                              │
│  • Adaptive evasion algorithms                                              │
│                                                                              │
│  These are ACTUAL CODE BLOCKS, not parameters.                              │
│  They propagate through stigmergy like any other signal.                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LIVE EVOLUTION ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  OPENEVOLVE ENGINE                                                     │  │
│  │                                                                        │  │
│  │  Observes ──► Fitness signals (success/failure per technique_id)      │  │
│  │  Selects  ──► Best-performing techniques as mutation parents          │  │
│  │  Mutates  ──► LLM generates NEW CODE variants                         │  │
│  │  Emits    ──► Code pheromone into stigmergic layer                    │  │
│  │                                                                        │  │
│  └────────────────────────────────┬──────────────────────────────────────┘  │
│                                   │                                          │
│                          evolved_code signal                                 │
│                                   │                                          │
│                                   ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  STIGMERGIC PUB/SUB (Redis)                                            │  │
│  │                                                                        │  │
│  │  Channel: cyberred.evolved_code                                        │  │
│  │  Signal TTL: 600s (decays naturally)                                  │  │
│  │                                                                        │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                        │
│            ┌────────────────────────┼────────────────────────┐              │
│            │                        │                        │              │
│            ▼                        ▼                        ▼              │
│    ┌──────────────┐        ┌──────────────┐        ┌──────────────┐        │
│    │ ExploitAgent │        │ WebAppAgent  │        │ PostExAgent  │        │
│    │              │        │              │        │              │        │
│    │ Receives     │        │ Receives     │        │ Receives     │        │
│    │ evolved code │        │ evolved code │        │ evolved code │        │
│    │ Executes it  │        │ Executes it  │        │ Executes it  │        │
│    │ Reports      │        │ Reports      │        │ Reports      │        │
│    │ success/fail │        │ success/fail │        │ success/fail │        │
│    └──────────────┘        └──────────────┘        └──────────────┘        │
│            │                        │                        │              │
│            └────────────────────────┼────────────────────────┘              │
│                                     │                                        │
│                          fitness signals                                     │
│                                     │                                        │
│                                     ▼                                        │
│                          BACK TO OPENEVOLVE                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Evolved Code Pheromone Structure

```python
@dataclass
class EvolvedCodeSignal:
    '''Evolved attack code distributed as stigmergic signal'''
    id: str                    # UUID
    category: str              # "waf_bypass", "payload_mutation", "exploit_chain"
    code: str                  # Actual Python code (function definition)
    fitness: float             # Current fitness score
    parent_id: Optional[str]   # Lineage tracking
    context: str               # "effective against ModSecurity CRS"
    agent_id: str              # Emitting agent (OpenEvolve)
    timestamp: str             # ISO 8601
    ttl: int                   # Seconds until decay (default 600)
    signature: str             # HMAC for integrity
```

**Example payload:**
```json
{
  "id": "ev-47a3c9f2",
  "category": "waf_bypass",
  "code": "def bypass_waf_v47(payload):\n    encoded = base64.b64encode(payload.encode())\n    chunks = [encoded[i:i+4] for i in range(0, len(encoded), 4)]\n    return \"eval(atob('\" + \"'+\\n'\".join(c.decode() for c in chunks) + \"'))\"",
  "fitness": 0.87,
  "parent_id": "ev-46b2d8e1",
  "context": "bypasses ModSecurity CRS pattern matching",
  "ttl": 600
}
```

---

## What Gets Evolved

| Category | Description | Example |
|----------|-------------|---------|
| **WAF Bypass** | Encoding chains, chunking, timing | `bypass_waf_v47()` with novel obfuscation |
| **Payload Mutation** | Polymorphic wrappers, evasion | `mutate_sqli_v23()` escaping new filters |
| **Exploit Chains** | Multi-step sequences | `chain_auth_bypass_to_rce()` |
| **Evasion Logic** | Anti-detection patterns | `evade_ids_v12()` timing-based bypass |
| **Tool Pipelines** | Novel tool combinations | `nmap_to_nuclei_chain()` |

---

## Agent Integration

```python
class StigmergicAgent:
    def __init__(self):
        self.evolved_techniques: Dict[str, Callable] = {}
        self.subscribe("cyberred.evolved_code", self.on_evolved_code)
    
    def on_evolved_code(self, signal: EvolvedCodeSignal):
        '''Receive and register evolved technique'''
        if signal.fitness > self._current_fitness(signal.category):
            # Compile and register the evolved function
            exec(signal.code, self.evolved_techniques)
            self.log(f"Adopted {signal.category} technique {signal.id}")
    
    def apply_evolved_technique(self, category: str, input_data: Any) -> Any:
        '''Apply evolved technique if available'''
        if category in self.evolved_techniques:
            technique_fn = self.evolved_techniques[category]
            return technique_fn(input_data)
        return input_data  # Fallback to unmodified

class ExploitAgent(StigmergicAgent):
    def exploit(self, target: Target, payload: str):
        # Apply evolved WAF bypass if available
        payload = self.apply_evolved_technique("waf_bypass", payload)
        
        # Apply evolved payload mutation if available  
        payload = self.apply_evolved_technique("payload_mutation", payload)
        
        # Execute
        result = self.execute_exploit(target, payload)
        
        # Report fitness signal
        self.emit_fitness(
            technique_ids=list(self.evolved_techniques.keys()),
            success=result.success
        )
        return result
```

---

## Evolution Loop

```
┌───────────────────────────────────────────────────────────────────────────┐
│  1. OBSERVE                                                                │
│     Collect fitness signals: which technique_ids succeeded/failed         │
│     Aggregate: "waf_bypass_v47: 12 success, 3 failure → fitness 0.80"    │
└─────────────────────────────────┬─────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼─────────────────────────────────────────┐
│  2. SELECT                                                                 │
│     Pick best-performing techniques as parents for mutation               │
│     Consider diversity (MAP-Elites style): best per category             │
└─────────────────────────────────┬─────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼─────────────────────────────────────────┐
│  3. MUTATE (LLM)                                                           │
│                                                                            │
│  Prompt to LLM:                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ You are evolving offensive security techniques.                       │ │
│  │                                                                       │ │
│  │ Current best WAF bypass (fitness 0.80):                              │ │
│  │ ```python                                                             │ │
│  │ def bypass_waf_v47(payload):                                         │ │
│  │     encoded = base64.b64encode(payload.encode())                     │ │
│  │     ...                                                               │ │
│  │ ```                                                                   │ │
│  │                                                                       │ │
│  │ Recent failures: blocked by WAF detecting base64 patterns            │ │
│  │                                                                       │ │
│  │ Generate a MUTATION that evades this detection.                      │ │
│  │ Output complete Python function.                                     │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  LLM returns new code:                                                    │
│  ```python                                                                │
│  def bypass_waf_v48(payload):                                            │
│      # EVOLVED: Use hex encoding + unicode escapes to avoid base64 sig  │
│      hex_encoded = payload.encode().hex()                                │
│      chunks = [hex_encoded[i:i+2] for i in range(0, len(hex_encoded), 2)]│
│      return "".join(f"\\u00{c}" for c in chunks)                         │
│  ```                                                                      │
└─────────────────────────────────┬─────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼─────────────────────────────────────────┐
│  4. VALIDATE                                                               │
│     • Static analysis (syntax check)                                      │
│     • Sandbox execution (doesn't crash)                                   │
│     • FROZEN CODE not modified (scope, killswitch)                        │
└─────────────────────────────────┬─────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼─────────────────────────────────────────┐
│  5. EMIT                                                                   │
│     Publish EvolvedCodeSignal to cyberred.evolved_code channel           │
│     Agents receive through normal pub/sub                                 │
└─────────────────────────────────┬─────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼─────────────────────────────────────────┐
│  6. NATURAL SELECTION                                                      │
│     Agents use new technique against target                               │
│     Success → reinforces technique (emits positive fitness signal)       │
│     Failure → technique decays (TTL expires, replaced by better)         │
└─────────────────────────────────┬─────────────────────────────────────────┘
                                  │
                                  └─────── REPEAT ──────────────────────────►
```

---

## Module Structure

```
src/cyberred/live_evolution/
├── __init__.py
├── evolver.py           # LLM-driven code mutation engine
├── code_signal.py       # EvolvedCodeSignal dataclass
├── fitness_observer.py  # Aggregate success/failure per technique
├── emitter.py           # Publish evolved code to stigmergic layer
├── validator.py         # Safety checks before emission
└── registry.py          # Lineage tracking, best-of-breed storage
```

---

## Safety Guarantees

| Invariant | Enforcement |
|-----------|-------------|
| Evolved code is sandboxed | Execution in isolated context |
| Scope validation unchanged | FROZEN, never evolved |
| Kill switch unchanged | FROZEN, never evolved |
| Syntax valid | Static analysis pre-emit |
| Code signed | HMAC prevents tampering |
| TTL enforced | Bad techniques decay naturally |

---

## Why This Is TRUE Evolution

| Aspect | Parameter Tuning | **Code Evolution** |
|--------|-----------------|-------------------|
| Discovers novel techniques | ❌ No | ✅ Yes |
| Adapts to specific WAFs | ❌ Limited | ✅ Fully |
| Creates new exploit chains | ❌ No | ✅ Yes |
| Inherits from successful parents | ❌ No | ✅ Yes (lineage) |
| Selection pressure from environment | ❌ Artificial | ✅ Live target |

---

## Proposed Requirements

### Functional
- **FR96:** OpenEvolve generates novel attack code during engagement
- **FR97:** Evolved code distributed as pheromone signals
- **FR98:** Agents receive and execute evolved techniques
- **FR99:** Success/failure signals provide fitness feedback
- **FR100:** Techniques with higher fitness spread; lower fitness decay

### Non-Functional
- **NFR47:** Evolution loop latency <10s
- **NFR48:** Evolved code validated before emission
- **NFR49:** Novel technique discovery: >1 per engagement
- **NFR50:** Zero scope violations from evolved code

---

## Success Scenario

```
1. Swarm attacks target, hits ModSecurity WAF
2. Exploit success rate drops to 20%
3. OpenEvolve observes: "waf_bypass_v12 failing"
4. Mutates: generates bypass_v13 with hex+unicode encoding
5. Emits as pheromone signal
6. 500 agents receive, adopt technique
7. Exploit success rate jumps to 65%
8. OpenEvolve mutates v13 → v14 → v15...
9. Swarm evolves around the WAF in real-time
10. NOVEL BYPASS DISCOVERED that no human designed
```

---

*Document Status: Draft v2 – Code as Pheromone Architecture*
