# Research Findings: Cyber-Red

**Date:** 2025-12-16
**Status:** Completed

## 1. Objectives
*   Validate `pymetasploit3` integration for async swarms.
*   Validate NVIDIA NIM rate limit handling.
*   Confirm "Worker Pool" architecture feasibility.

## 2. Findings

### A. Metasploit RPC Bridge
*   **Challenge:** `pymetasploit3` is synchronous (blocking).
*   **Solution:** Validated usage of `loop.run_in_executor()` to wrap blocking RPC calls.
*   **Result:** Prototype `research/msf_wrapper.py` successfully executed 5 parallel tasks in 2 seconds (vs 10s sequential).
*   **Architecture Decision:** The "Worker Pool" will use a `ThreadPoolExecutor` to handle the heavy lifting of RPC communication.

### B. NVIDIA NIM Throttling
*   **Challenge:** Free tier has ~40-60 RPM limit. Swarm bursts will exceed this instantly.
*   **Solution:** Validated `asyncio.Semaphore` (Token Bucket) pattern.
*   **Result:** Prototype `research/nim_throttle_poc.py` processed 50 requests in 7.27s with a concurrency limit of 10, proving effective queue management.
*   **Configuration:** Production `SEMAPHORE_LIMIT` should be set to **30** (conservative) to avoid HTTP 429 errors.

## 3. Recommendations for PRD
*   **Tech Stack:** Python 3.12+, `asyncio`, `pymetasploit3`.
*   **Performance:** Implement a global `RateLimiter` class in the Core module.
*   **Infrastructure:** The `MsfRpcClient` must be instantiated *once* per thread or guarded by a lock if not thread-safe (further testing required during implementation).
