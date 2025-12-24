# Product Requirements Document (PRD): Cyber-Red

**Version:** 1.0
**Date:** 2025-12-16
**Status:** Approved

## 1. Introduction
Cyber-Red is a Hierarchical Autonomous Multi-Agent System (HAMAS) for offensive security. It simulates a nation-state level swarm attack to perform Total Attack Surface Exhaustion.

## 2. Goals & Objectives
*   **Primary:** Automate complex, multi-step exploitation chains using an elastic swarm of AI agents.
*   **Secondary:** Provide a "Human-in-the-Loop" governance layer to ensure authorized, safe execution.
*   **Technical:** Run effectively on a single high-spec workstation (32GB RAM) using a "Worker Pool" architecture.

## 3. User Personas
*   **The Operator:** A senior security professional (Red Teamer/CISO) who defines the scope, monitors the "War Room," and authorizes high-risk actions.

## 4. Functional Requirements

### 4.1. Core Engine (The Brain)
*   **FR-CORE-01 (Council of Experts):** The system MUST implement a 3-model voting architecture for every high-risk decision:
    *   *Strategist:* Proposes attack vector.
    *   *Coder:* Generates syntax.
    *   *Critic:* Vetoes based on RoE.
*   **FR-CORE-02 (Throttling):** The system MUST implement a Token Bucket Rate Limiter to cap external API calls (NVIDIA NIM) at 30 RPM (configurable).
*   **FR-CORE-03 (Persistence):** The system MUST persist session data (Scan Results, Agent Logs) to a local Dockerized database (Redis/MongoDB) to allow pausing/resuming.

### 4.2. Agent System (The Hands)
*   **FR-AGENT-01 (Worker Pool):** The system MUST decouple "Agent Logic" (Ghosts) from "Execution Containers" (Titans). 100 Ghost Agents share a pool of ~10 Execution Containers.
*   **FR-AGENT-02 (Tool Suite):** The system MUST support the following tools via custom MCP Adapters:
    *   **Recon:** Nmap, Naabu, WhatWeb.
    *   **Web:** Nuclei, Ffuf.
    *   **Exploit:** SQLMap, Hydra, Metasploit (via `pymetasploit3` RPC).
*   **FR-AGENT-03 (Result Verification):** The system MUST parse tool output into structured JSON. "Vulnerable" status is only assigned if the tool returns a verified positive result.

### 4.3. User Interface (The Face)
*   **FR-UI-01 (Textual Dashboard):** The system MUST provide a TUI accessible via SSH.
*   **FR-UI-02 (Hive Matrix):** A 10x10 grid visualizing agent status (Scanning, Thinking, Attacking, Done).
*   **FR-UI-03 (Intervention):** The Operator MUST be able to Pause, Resume, or Kill specific agents via the TUI.
*   **FR-UI-04 (Approval Queue):** The UI MUST display a queue of "Pending Approvals" for actions vetoed by the Critic but potentially valid (User override).

### 4.4. Reporting
*   **FR-RPT-01:** The system MUST generate a final `Report.md` containing:
    *   Executive Summary.
    *   Attack Graph (Visualizing the path to compromise).
    *   Verified Vulnerabilities List.

## 5. Non-Functional Requirements
*   **NFR-01 (Performance):** The system MUST handle 100 concurrent agent threads without exceeding 32GB RAM usage.
*   **NFR-02 (Latency):** UI updates MUST be <200ms lag from the backend state.
*   **NFR-03 (Safety):** The system MUST fail-safe (abort all attacks) if the "Kill Switch" is triggered or network heartbeats fail.

## 6. Assumptions & Constraints
*   **Constraint:** NVIDIA NIM Free Tier limits.
*   **Assumption:** User provides a Docker-capable environment (Linux).
*   **Constraint:** "Proof of Exploitation" is limited to non-destructive actions (e.g., `whoami`, `cat /etc/passwd`), NOT `rm -rf`.

## 7. Tech Stack
*   **Language:** Python 3.12+
*   **UI Framework:** Textual (TUI)
*   **AI Models:** NVIDIA NIM (Llama 3.1, Mistral, Llama 3 70B)
*   **Database:** Redis (Queue/Cache), MongoDB (Persistence)
*   **Infrastructure:** Docker Compose
