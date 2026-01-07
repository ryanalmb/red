# Brainstorming Session: Cyber-Red (HAMAS for Offensive Security)
**Date:** 2025-12-16
**Status:** Completed

## 1. Executive Summary
**Cyber-Red** is a Hierarchical Autonomous Multi-Agent System (HAMAS) designed to simulate nation-state level cyber attacks.
*   **Core Goal:** Total Attack Surface Exhaustion through recursive swarming.
*   **Architecture:** "Cloud Brain" (NVIDIA NIM) + "Local Hands" (Dockerized Kali).
*   **Ethical Constraint:** "Hard Authorization" governance layer (Hybrid RoE).

## 2. Key Architectural Decisions

### A. The "Council of Experts" (Cognitive Architecture)
*   **Concept:** A multi-model consensus engine to reduce hallucinations and ensure safety.
*   **Roles:**
    *   **The Strategist:** Llama-3.1-405B (Plan/Strategy).
    *   **The Coder:** Mistral-Codestral / StarCoder2 (Syntax/Tooling).
    *   **The Critic:** Llama-3-70B (Safety/RoE Veto).
*   **Workflow:** Proposal -> Code Generation -> Hard Gate (Python) -> Semantic Gate (Critic) -> Execution.

### B. The "Worker Pool" (Infrastructure)
*   **Constraint:** 32GB RAM Server limits purely independent agents.
*   **Solution:** Worker Pool Pattern.
    *   **100 "Ghost" Agents:** Lightweight Python logic (Swarm state).
    *   **10 "Titan" Containers:** Heavy Kali Linux Docker instances (Execution).
*   **Rate Limiting:** Token Bucket Throttler (50 RPM) to manage NVIDIA NIM free tier limits.

### C. The "War Room" (UX/UI)
*   **Technology:** Python `Textual` (TUI) for SSH compatibility.
*   **Components:**
    *   **Hive Matrix:** 10x10 Status Grid.
    *   **Fractal Tree:** Hierarchical view of Target -> Port -> Vuln.
    *   **Kill Chain:** Filtered milestone log.
    *   **Thought Bubble:** Real-time agent monologue with **Human-in-the-Loop** controls (Approve/Abort).

### D. Tooling & Integration
*   **MCP Bridge:** Custom fork of `HexStrike AI`.
*   **Metasploit:** Use `pymetasploit3` to talk to `msfrpcd` (RPC) for structured JSON output, avoiding raw shell parsing fragility.
*   **Orchestration:** Python `asyncio` + Redis (Hive Memory).

## 3. Immediate Next Steps
1.  **Product Brief:** Formalize the scope, authorization boundaries, and "Iron Triangle" governance.
2.  **Research:**
    *   Prototype the `pymetasploit3` RPC connection.
    *   Test NVIDIA NIM Rate Limits with a simple `asyncio` script.
3.  **Prototype:** Scaffold the Textual TUI with the Worker Pool logic.
