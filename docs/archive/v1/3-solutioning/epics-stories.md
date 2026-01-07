# Epics & User Stories: Cyber-Red

**Version:** 1.0
**Date:** 2025-12-16
**Status:** Approved

## Epic 1: Infrastructure Foundation (INF)
**Goal:** Establish the runtime environment and communication backbone.

*   **Story INF-01: Docker Environment Setup**
    *   **As a:** Developer
    *   **I want to:** Start `docker-compose up` and have Redis and 10 Kali Linux containers running.
    *   **Acceptance Criteria:**
        *   `docker-compose.yml` defines `redis` and `kali-worker` services.
        *   `kali-worker` builds from a Dockerfile with `metasploit-framework`, `nmap`, etc. installed.
        *   Running the command results in 11 healthy containers.

*   **Story INF-02: Redis Event Bus**
    *   **As a:** Developer
    *   **I want to:** Publish messages from Python and have them received by other Python subscribers.
    *   **Acceptance Criteria:**
        *   `EventBus` class implements `publish()` and `subscribe()`.
        *   Unit test verifies message delivery via Redis.

*   **Story INF-03: Project Skeleton**
    *   **As a:** Developer
    *   **I want to:** Have the directory structure created so I can start coding modules.
    *   **Acceptance Criteria:**
        *   `src/`, `tests/`, `config/` folders created matching Architecture doc.

## Epic 2: The Execution Layer (HANDS)
**Goal:** Enable Python to execute commands in Docker containers.

*   **Story HANDS-01: Worker Pool Manager**
    *   **As a:** System
    *   **I want to:** Queue tasks when all containers are busy and execute them when one becomes free.
    *   **Acceptance Criteria:**
        *   `WorkerPool` class manages a queue.
        *   Tasks are executed in a `ThreadPoolExecutor`.
        *   System does not crash if >10 tasks are submitted simultaneously.

*   **Story HANDS-02: Metasploit MCP Adapter**
    *   **As a:** Developer
    *   **I want to:** Execute `msfconsole` commands via Python and get JSON output.
    *   **Acceptance Criteria:**
        *   `MsfAdapter` connects to `msfrpcd`.
        *   `execute_exploit()` returns Success/Fail status.
        *   Blocking calls do not freeze the main event loop.

*   **Story HANDS-03: Nmap MCP Adapter**
    *   **As a:** Developer
    *   **I want to:** Run Nmap scans and get parsed results.
    *   **Acceptance Criteria:**
        *   `NmapAdapter` runs `nmap -oX` (XML output).
        *   XML is parsed into a Python dictionary.

## Epic 3: The Cognitive Core (BRAIN)
**Goal:** Implement the intelligence and governance logic.

*   **Story BRAIN-01: NIM Throttler**
    *   **As a:** System
    *   **I want to:** Limit API calls to 30 RPM to avoid errors.
    *   **Acceptance Criteria:**
        *   `SwarmBrain` class uses `asyncio.Semaphore`.
        *   Burst of 50 requests takes > 1 minute to complete.

*   **Story BRAIN-02: Council of Experts**
    *   **As a:** System
    *   **I want to:** Have 3 different models vote on a strategy.
    *   **Acceptance Criteria:**
        *   `Council.decide()` triggers Strategist, Coder, and Critic.
        *   Critic Veto stops execution.

## Epic 4: The Command Center (FACE)
**Goal:** Visualize the swarm.

*   **Story FACE-01: Textual App Skeleton**
    *   **As a:** Operator
    *   **I want to:** See the TUI layout with 3 panes.
    *   **Acceptance Criteria:**
        *   App launches via SSH.
        *   Tree, Grid, and Log widgets are visible.

*   **Story FACE-02: Hive Matrix Integration**
    *   **As a:** Operator
    *   **I want to:** See agent colors change when they change state.
    *   **Acceptance Criteria:**
        *   Redis events trigger TUI updates.
        *   Grid updates in real-time (<200ms).
