# Product Brief: Cyber-Red

**Version:** 1.0
**Date:** 2025-12-16
**Status:** Draft

## 1. Executive Summary
**Cyber-Red** is a Hierarchical Autonomous Multi-Agent System (HAMAS) designed to simulate nation-state level cyber offensive operations. It solves the "Asymmetric Deficit" in cyber defense—where attackers have infinite time and automation, while defenders have limited attention—by deploying an elastic swarm of AI agents.

Unlike traditional scanners that run linear scripts, Cyber-Red functions as a "Hive Mind," orchestrating hundreds or thousands of specialized micro-agents to perform complex, multi-step exploitation chains in parallel. It serves as a defensive weapon for large organizations, governments, and institutions to harden their infrastructure against sophisticated threats.

## 2. Problem Statement
*   **The Coverage Gap:** Human red teams cannot physically test every port, API endpoint, and parameter on a massive network simultaneously.
*   **The Skill Bottleneck:** No single human expert is a master of every domain (SQLi, Cloud, AD, IoT, Wireless).
*   **Linear Fragility:** Traditional tools (scanners) follow linear logic and break easily. They lack the reasoning to "pivot" or "adapt" when a WAF blocks them.

## 3. Product Vision & Value Proposition
**"The Army in a Box."**
Cyber-Red provides the cognitive diversity and operational scale of a massive, expert-level red team in a single deployable system.

*   **Elastic Scalability:** Capable of scaling from 10 to 10,000+ agents depending on hardware and scope.
*   **Domain Expertise:** Utilizes a "Council of Experts" architecture where specialized AI models (Strategist, Coder, Critic) collaborate to solve specific problems.
*   **Total Exhaustion:** The goal is not just to find *one* way in, but to find *every* way in.

## 4. Target Audience
*   **Primary:** Enterprise and Government Security Teams (Red/Purple Teams).
*   **Secondary:** Managed Security Service Providers (MSSPs) and elite security consultancies.
*   **Context:** Used for validating live sites, infrastructure, and codebases within authorized environments.

## 5. Core Features

### A. The Swarm Engine (Architecture)
*   **Cloud Brain / Local Hands:** High-intelligence planning via NVIDIA NIM (Llama 3.1) coupled with local execution via Dockerized Kali Linux containers.
*   **Worker Pool Pattern:** Optimizes resource usage (e.g., 32GB RAM) by separating "Ghost Agents" (Logic) from "Titan Containers" (Execution).
*   **Asynchronous Pipelining:** Uses `asyncio` to mask AI inference latency, ensuring maximum network and CPU utilization.

### B. The Governance Layer (Safety)
*   **The "Iron Triangle":**
    1.  **Hard Gate (Python):** Deterministic enforcement of Time, IP Scope, and Protocols.
    2.  **AI Critic (Llama 3 70B):** Semantic analysis of intent (e.g., "Is this payload too aggressive?").
    3.  **Kill Switch:** Emergency abort mechanisms.
*   **Dynamic RoE:** The Rules of Engagement are defined per project. Once set, they are the **Immutable Law**. Scope expansion (finding new subdomains) triggers a "Request Permission" event, never automatic unauthorized attacks.

### C. The War Room (UX)
*   **Interface:** `Textual` based TUI (Terminal User Interface) optimized for SSH access on VPS/Bare-metal.
*   **Visuals:** Fractal Tree (Attack Surface), Hive Matrix (Swarm Status), and Kill Chain (Milestones).
*   **Human-in-the-Loop:** Real-time ability to "Approve" or "Abort" specific agent actions via the UI.

## 6. Success Metrics
*   **Exploit Verification:** 100% of reported vulnerabilities must be "Proven" (e.g., shell access, data extraction) via the MCP bridge, eliminating false positives.
*   **Stability:** Zero unauthorized Denial of Service (DoS) events during testing.
*   **Coverage:** 100% traversal of the defined scope (all open ports/services analyzed).

## 7. Risks & Mitigations
*   **Risk:** Runaway costs/rate-limits on NVIDIA NIM.
    *   *Mitigation:* Token Bucket Throttler and caching of common decision patterns (Redis "Hive Memory").
*   **Risk:** AI Hallucination (Running dangerous commands).
    *   *Mitigation:* The "Critic" model vetoes unsafe commands, and the MCP bridge verifies syntax before execution.
