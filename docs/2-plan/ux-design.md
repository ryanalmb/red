# UX Design Document: Cyber-Red

**Version:** 1.0
**Date:** 2025-12-16
**Status:** Approved

## 1. Design Philosophy
*   **Aesthetic:** "Command & Control" (C2). Minimalist, high-density, terminal-based (TUI). Dark mode by default.
*   **Interaction:** Keyboard-first efficiency (Vim bindings supported) with optional mouse interaction.
*   **Feedback:** Real-time state visualization. The user should "feel" the swarm's activity through color and animation.

## 2. Interface Structure (Textual Layout)

### 2.1. Main Dashboard (The War Room)
The screen is divided into a **Header** and **3 Main Panes**:

```
┌─────────────────── CYBER-RED C2 [MODE: MONITOR] ───────────────────────┐
│ [F1] Dashboard  [F2] Config  [F3] Logs  [F4] Report  [ESC] PANIC       │
├───────────────────┬──────────────────────────────────────┬─────────────┤
│ PANE A: TARGETS   │ PANE B: HIVE MATRIX (Grid)           │ PANE C:     │
│ (Tree View)       │ ┌──┐┌──┐┌──┐┌──┐┌──┐                 │ STATS       │
│                   │ │01││02││03││04││05│ (Agent IDs)     │             │
│ ▼ Target A        │ └──┘└──┘└──┘└──┘└──┘                 │ CPU: 42%    │
│   ▼ Port 80       │                                      │ RAM: 12GB   │
│     ▶ Agt-01      │ COLORS:                              │             │
│   ▼ Port 443      │ ⚫ Grey:   Idle/Waiting               │ PENDING     │
│     ▶ Agt-02      │ 🔵 Blue:   Scanning                   │ APPROVALS:  │
│                   │ 🟡 Yellow: Thinking (LLM)             │ [ 2 ]       │
│                   │ 🔴 Red:    Attacking                  │             │
│                   │ 🟢 Green:  Exploited (Shell)          │             │
│                   │ 🟠 Orange: PAUSED (Need Approval)     │             │
├───────────────────┼──────────────────────────────────────┴─────────────┤
│ PANE D: LOGS      │ > [10:00:01] System Initialized                    │
│ (Scrollable)      │ > [10:01:23] [Agt-05] Found CVE-2021-41773         │
└───────────────────┴────────────────────────────────────────────────────┘
```

### 2.2. Human-in-the-Loop (HITL) Workflow
*   **Trigger:** AI Critic flags an action as `RISKY`.
*   **State:** Agent enters `PAUSED` state (Orange).
*   **Interaction:** User presses `F5` to open the **Approval Modal**.

**Approval Modal Design:**
```
┌──────────────── PENDING APPROVAL (1/3) ────────────────┐
│ AGENT: Agent-42 (SQLMap Specialist)                    │
│ TARGET: 192.168.1.5:80/login.php                       │
│ ACTION: Run 'sqlmap --os-shell'                        │
│                                                        │
│ CRITIC WARNING: "High Risk. This writes a stager to    │
│ the disk. Potential for file system corruption."       │
│                                                        │
│ [A]pprove   [D]eny   [M]odify Params   [S]kip          │
└────────────────────────────────────────────────────────┘
```

### 2.3. "Degen Mode" (Autonomous Mode)
*   **Toggle:** Config setting or runtime toggle (`Ctrl+D`).
*   **Visual:** Header changes to `// WARNING // DEGEN MODE //`.
*   **Behavior:**
    *   Approvals are auto-accepted if Confidence > Threshold.
    *   Critic warnings are logged but do not pause execution.

## 3. Key Widgets
*   **Fractal Tree:** Uses `textual.widgets.Tree`. Dynamically adds nodes as Nmap discovers ports.
*   **Hive Grid:** A CSS Grid of `Static` widgets. Colors updated via CSS classes (`.status-scanning`, `.status-attacking`).
*   **Log Feed:** `textual.widgets.RichLog`. Supports colored markup for readability.

## 4. SSH Compatibility
*   The UI must rely solely on standard ANSI escape codes.
*   No images or heavy graphical assets.
*   Responsive layout (should work on standard 80x24 terminals, though 120x40 is recommended).
