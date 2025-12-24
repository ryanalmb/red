# Cyber-Red Operator's Manual

## 1. System Overview
Cyber-Red operates on a "Cloud Brain / Local Hands" model.
*   **The Brain:** NVIDIA NIM APIs (Cloud).
*   **The Hands:** Docker Containers (Local).
*   **The Glue:** Redis (Local).

## 2. Configuration Guide

### The "Iron Triangle" (RoE)
Located at `config/roe.yaml`.

*   **`allowed_ips`**: A whitelist of IP addresses or CIDR ranges. The Swarm will **VETO** any attempt to touch an IP not in this list.
*   **`forbidden_ports`**: Ports to ignore (e.g., 21 if you don't want to crash an old FTP server).
*   **`aggression_level`**:
    *   `LOW`: Recon only. No exploits.
    *   `MEDIUM`: Safe exploits (no memory corruption).
    *   `HIGH`: Full exploitation (webshells allowed).

### The "Worker Pool"
Located at `docker-compose.yml`.
To scale the swarm, change `replicas: 10` to `replicas: 50`.
**Warning:** Each worker consumes ~500MB RAM.

## 3. The TUI (War Room)

### Views
*   **Target Tree (Left):** Shows the discovered attack surface.
*   **Hive Matrix (Center):** Shows what each of the 100 agents is doing.
    *   🔵 **Blue:** Scanning.
    *   🟡 **Yellow:** Thinking (Consulting Council).
    *   🔴 **Red:** Attacking.
    *   🟢 **Green:** Success (Shell).
    *   🟠 **Orange:** PAUSED (Needs Approval).

### Human-in-the-Loop (HITL)
If the **Critic** flags an action as "Risky" but "Possible", the Agent pauses.
1.  Press `F5` to open the Approval Queue.
2.  Read the Critic's Warning.
3.  Press `A` to Authorize or `D` to Deny.

## 4. Reporting
Reports are generated automatically at the end of a session or by calling:
```bash
python3 -c "from src.core.reporting import ReportGenerator..."
```
Output is saved to `reports/`.

## 5. Troubleshooting

**"Target Unreachable"**
*   Ensure the target is in the `red_net` network.
*   Check `docker ps` to ensure `red-metasploitable-1` is healthy.

**"NIM Rate Limit Error"**
*   Check `.env` for `NVIDIA_API_KEY`.
*   The system throttles to 30 RPM automatically. If you see 429s, lower the limit in `src/core/throttler.py`.
