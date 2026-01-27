# The Evolution Module: AlphaEvolve Integration & Mechanics

## 1. The Core Philosophy: "FunSearch" for Offensive Security

Standard LLMs suffer from "Reversion to the Mean." If you ask DeepSeek for an SQL injection, it gives you the most statistically probable answer from its training data (`' OR 1=1 --`). Security systems are trained to block exactly these probable answers.

**AlphaEvolve/OpenEvolve (integrated as the Evolution Module)** moves beyond simple mutation. It implements the mechanics of **DeepMind's FunSearch** (Function Search) and **Map-Elites** (Quality Diversity) to evolve not just payloads, but the *algorithms* used to generate them.

### The Mechanics of "FunSearch" in Cyber-Red

*Based on: Romera-Paredes et al. (2023) - Mathematical discoveries from program search.*

Instead of evolving a text string (payload), we evolve **Python Code**.

1.  **Seed Program:** A function `generate_attack_vector(context)`.
2.  **The Mutator (LLM):** The Evolution Module asks the LLM: *"Rewrite this function to prioritize a new obfuscation technique while maintaining valid syntax."*
3.  **The Evaluator (Sandbox):** The new function is executed against a local target or simulation.
4.  **The Feedback:** Only functions that produce *novel* and *successful* outputs are added back to the pool.

**Outcome:** The system builds a library of **Algorithmic Weapons**—functions that dynamically generate WAF-bypassing payloads—mathematically proven to be more effective than static tool templates.

---

## 2. Quality-Diversity: The "Map-Elites" Archive

*Based on: MAP-Elites with LLMs (Lupu et al., 2024)*

Optimization algorithms usually converge to a single "best" solution. This is fatal in hacking because defenses patch the "best" attack. We need a **diverse arsenal**.

### The "Archive of Novelty"
We replace a simple "Success/Fail" list with a multi-dimensional **Behavioral Map**:

*   **Dimension 1:** Payload Length (Short vs. Long)
*   **Dimension 2:** Obfuscation Level (Plain vs. Heavy)
*   **Dimension 3:** Response Characteristic (403 vs 500 vs 200)

**The Process:**
The system proactively tries to fill *every cell* in this map.
*   *"I have a Short/Plain exploit. Now I need a Long/Heavy exploit."*
*   The LLM is forced to generate "weird" solutions to fill the empty cells.

**Outcome:** A robust arsenal. If the WAF patches "Hex Encoding" (one cluster), the system instantly switches to "Comment Splitting" (a different cluster).

---

## 3. Meta-Optimization: The "Lion" Mechanics

*Based on: DeepMind Lion Optimizer (Chen et al., 2023)*

The system doesn't just evolve attacks; it evolves its own **behavioral hyperparameters**.

*   **Target:** The Director Ensemble's "Strategy Weights" (e.g., Aggression, Stealth, Risk Tolerance).
*   **Mechanism:**
    *   The swarm operates with set parameters.
    *   AlphaEvolve runs a meta-evolution loop: *"If we increase Aggression by 10% on Subnet B, does capture rate improve?"*
*   **Outcome:** The swarm **auto-tunes** its psychology. It becomes aggressive when defenses are weak and stealthy when defenses are hardened, without human intervention.

---

## 4. Architecture Debate: Why separate "Evolution" from the "Director"?

**The Upside of Integration:**
*   Simplicity. One "Brain" module.
*   Tighter context loop.

**The Fatal Downside: "Thinking" vs. "Learning"**
The Director is your **General**. The Evolution Module is your **R&D Lab**.

| Feature | Director Ensemble (The General) | Evolution Module (The Lab) |
| :--- | :--- | :--- |
| **Time Scale** | Seconds (Real-time decisions) | Minutes/Hours (Deep iteration) |
| **Compute** | Low (Single inference pass) | Massive (1,000s of generations) |
| **Role** | "Attack Port 80." | "Invent a key for Port 80." |
| **State** | Stateless (mostly) | Stateful (Population history / Map-Elites Archive) |

**If you integrate them:**
The Director freezes. While it is running 50 generations of genetic algorithms to crack one specific lock, the rest of the war (10,000 agents) is ignored. The General stops commanding the army to fiddle with a lockpick.

**By separating them:**
1.  **Asynchronous Power:** The Director flags a hard target and keeps moving. "Agent 42 is stuck on Target X. Evolution Module, spin up a thread for Target X."
2.  **Specialization:** The Director uses models optimized for *Reasoning* (DeepSeek/Kimi). The Evolution Module can use smaller, faster models optimized for *Code Mutation* (DeepSeek-Coder/Nemotron) to run generations faster.

---

## 5. How this drives Novel Discovery

This architecture creates a **Novelty Search Engine**.

1.  **Breaking Local Minima:**
    Standard automated tools get stuck in "Local Minima." If `nmap` fails, they stop.
    Evolutionary algorithms have a "temperature." If progress stops, they drastically increase mutation rates (saltation). They try "crazy" things—malformed packets, illegal headers, non-standard encodings—that a sane LLM would never suggest.

2.  **Hallucination as a Feature, not a Bug:**
    In a chat bot, hallucination is bad. In `openevolve`, hallucination is **Mutation**.
    When the LLM hallucinates a non-existent SQL flag, the sandbox tests it. 99% fail. But the 1% that works? That is a **Zero-Day** in the parser logic that no one knew existed. You are literally weaponizing AI hallucination to find parser bugs.

3.  **The Stigmergic Multiplier:**
    Because you have 10,000 agents, you have 10,000 "sensors" finding hard targets. The Evolution Module isn't guessing; it is being fed concrete, failed test cases from the field. It evolves solutions for *real* defenses, not theoretical ones.

**Conclusion:**
The Evolution Module sits outside the Director because it is a **compute-heavy optimization engine**. It takes the "impossible" problems the Director identifies and grinds them through a genetic algorithm (FunSearch + Map-Elites) until a novel solution emerges.