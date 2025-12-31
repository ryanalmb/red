---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
inputDocuments:
  - docs/1-analysis/product-brief.md
  - docs/2-plan/prd.md
  - docs/3-solutioning/architecture.md
  - docs/archive/v1/2-plan/ux-design.md
workflowType: 'ux-design'
lastStep: 14
project_name: 'Cyber-Red'
user_name: 'root'
date: '2025-12-29'
version: '2.0'
---

# UX Design Specification: Cyber-Red v2.0

**Author:** root
**Date:** 2025-12-29

---

## Executive Summary

### Project Vision

Cyber-Red v2.0 is a stigmergic multi-agent offensive security platform — not a tool, but a *capability* that replaces hiring a 1,000-person red team. The platform deploys 10,000+ AI agents that coordinate through P2P communication to achieve mission objectives (e.g., "log in as admin and extract this data").

**Core Differentiators:**
- Objective-driven (completes missions, not just scans)
- 100% exploit verification (zero false positives)
- Emergent attack strategies via stigmergic coordination
- Multi-LLM Director Ensemble (DeepSeek, Kimi K2, MiniMax)
- Daemon-based execution (survives SSH disconnect)

### Target Users

**Primary: Root (The Operator)**
- Senior cybersecurity strategist with deep offensive expertise
- Sole operator of Cyber-Red — the human behind the swarm
- **Day-to-day:** Configures missions, monitors War Room, authorizes lateral movement, pauses/resumes engagements, manages multiple concurrent engagements
- **Success vision:** "This single tool makes possible what previously required an army"

**Key User Characteristics:**
- Extremely tech-savvy (expects Vim keybindings, terminal efficiency)
- Monitors for hours during engagements — needs restlessness→resolution emotional arc
- Values control (kill switch, scope enforcement, authorization gates)
- May disconnect SSH and return later — needs seamless attach/detach

### Key Design Challenges

| Challenge | Why It Matters |
|-----------|----------------|
| **10,000+ Agent Visualization** | Can't show all agents — need virtualized list + anomaly bubbling |
| **Daemon Attach/Detach** | TUI is a client, not host — state sync on attach, no data loss on detach |
| **Multi-Engagement Management** | Sessions list, switch between engagements, isolated views |
| **Authorization Flow** | WebSocket push for lateral movement — must interrupt without losing context |
| **Director Ensemble Display** | Show 3 LLM perspectives synthesizing — not overwhelming |
| **Long-Running Sessions** | Hours/days of engagement — prevent cognitive overload, surface what matters |
| **Kill Switch Accessibility** | <1s to halt — must be always visible, never more than 1 keypress |

### Design Opportunities

| Opportunity | Competitive Advantage |
|-------------|----------------------|
| **Anomaly Bubbling** | Surface agents needing attention without manual scanning |
| **Stigmergic Visualization** | Show emergent coordination (Hive Matrix connections) |
| **Incremental Win Celebration** | Each finding is an "aha moment" — make discoveries feel rewarding |
| **Contextual Authorization** | Show what was found, proposed action, constraints — fast decisions |
| **Pause/Resume Mental Model** | Visual clarity on engagement state (RUNNING/PAUSED/STOPPED) |
| **RAG Management Widget** | Update knowledge base mid-engagement — power user feature |

### Design Constraints

- **Terminal-based (Textual TUI)** — SSH compatible, no images
- **Dark mode** — "Command & Control" aesthetic
- **Keyboard-first** — Vim bindings, F-keys for panels
- **80x24 minimum** — responsive, 120x40 recommended
- **Standard ANSI codes only** — no heavy graphics

---

## Core User Experience

### Defining Experience

The core experience is **monitoring the War Room while the swarm executes** — watching findings stream in, responding to authorization requests, and feeling the restlessness→resolution emotional arc as objectives are achieved.

**Core Loop:** Watch swarm → Finding discovered → Authorization request → Quick decision → Swarm pivots → Objective achieved

### Platform Strategy

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Platform** | Terminal TUI (Textual) | SSH-accessible, works on servers |
| **Input** | Keyboard-first | Expert user, Vim muscle memory |
| **Offline** | Daemon continues | TUI can disconnect |
| **Device** | Any terminal | 80x24 min, scales to large monitors |

### Effortless Interactions

- **Kill Switch** — ESC key (+ multi-path alternatives), always visible via sticky button, <1s response
- **Authorization** — Y/N with optional constraints, no navigation
- **Pause/Resume** — Single keypress, instant, visual confirmation
- **Attach** — Immediate state sync on reconnect + Catch-up Mode (chronological replay of missed events) + state checksum validation ("State may be stale — refresh?" if mismatch)
- **Findings** — Auto-stream, color-coded, no refresh needed
- **Anomalies** — Bubble to top automatically

### Critical Success Moments

1. **First Finding** — "It's working!" visual feedback
2. **Authorization Decision** — Fast, contextual, acknowledged
3. **Objective Achieved** — Celebration, audit trail, deliverables ready
4. **Attach After Disconnect** — Seamless state restoration + Catch-up Mode
5. **Catch-up Mode** — Chronological replay of missed events during disconnect
6. **Kill Switch** — Immediate halt with confirmation

### Experience Principles

1. **Control is Sacred** — Kill switch, pause, scope always accessible
2. **Attention on Demand** — Surface what matters, hide noise
3. **State is Visible** — Always know engagement status
4. **Decisions are Fast** — Context + Y/N + constraints
5. **Findings are Rewards** — Visual celebration on discovery
6. **Persistence is Invisible** — Attach/detach just works

---

## Desired Emotional Response

### Primary Emotional Goals

| Emotional State | When It Should Occur |
|-----------------|---------------------|
| **Restlessness/Anticipation** | During active engagement |
| **Control/Power** | Always — "I command an army" feeling |
| **Resolution/Satisfaction** | When objective is achieved |
| **Trust/Confidence** | When authorizing actions |

The defining emotion: Root should feel like a **general commanding an army**.

### Emotional Journey Mapping

| Stage | Emotional State |
|-------|-----------------|
| **First Launch** | Anticipation, slight nervousness |
| **Swarm Initializing** | Building excitement |
| **Active Engagement** | Restlessness, focus |
| **Finding Discovered** | Micro-burst of satisfaction |
| **Authorization Request** | Brief tension → quick resolution |
| **Objective Achieved** | Deep satisfaction, resolution |
| **Disconnect/Reconnect** | Seamless, no anxiety |
| **Kill Switch** | Relief, control |

### Micro-Emotions

- **Build:** Confidence, Trust, Accomplishment
- **Moderate:** Urgency (not alarm)
- **Avoid:** Anxiety, Frustration, Confusion, Overwhelm

### Emotional Design Principles

1. **Restlessness is Good** — Active engagement should feel alive
2. **Control Prevents Anxiety** — Visible kill switch and pause
3. **Findings are Dopamine** — Each discovery triggers micro-reward
4. **Trust Through Transparency** — Show scope enforcement
5. **Resolution is Earned** — Objective completion feels like mission accomplished
6. **No Surprises** — Predictable behavior builds confidence

---

## UX Pattern Analysis & Inspiration

### Inspiring Products Analysis

| Product | Key Pattern | Applicable To |
|---------|-------------|---------------|
| **Textual Framework** | Rich TUI with mouse+keyboard | Foundation for v2 (already used in v1) |
| **htop/btop** | Virtualized real-time list | 10K agent visualization |
| **tmux** | Detach/attach persistence | Daemon TUI model |
| **msfconsole** | Hierarchical navigation | Target → Agent flow |
| **Vim** | Modal interface, keyboard-first | Expert user efficiency |

### Transferable UX Patterns

**Navigation:** F-key quick actions, clickable tabs, modal switching, hierarchical navigation
**Interaction:** Virtualized scrolling, real-time streaming, dual-path (keyboard + mouse)
**Visual:** Color-coded status, TCSS styling, CSS animations for feedback, status bar

### Framework Choice: Textual

v1 already uses Textual (`src/ui/app.py`). Key capabilities for v2:

| Feature | Application |
|---------|-------------|
| **DataTable** | Virtualized 10K agent list with click-to-select |
| **Tree** | Target → Port → Agent hierarchy |
| **Modal Screens** | Authorization pop-overs |
| **TCSS Styling** | "Command & Control" dark aesthetic |
| **CSS Animations** | Finding pulse, status transitions |
| **Hybrid Input** | Mouse + keyboard natively supported |

### Input Model: Dual-Path

Every action accessible via BOTH keyboard AND mouse:

| Action | Keyboard | Mouse |
|--------|----------|-------|
| Kill Switch | `ESC` | Click [KILL] button |
| Authorize | `Y` / `N` | Click [Yes] / [No] |
| Select Agent | `j/k` + `Enter` | Click row |
| Pause/Resume | `F5` / `F6` | Click button |
| Switch Pane | `F1-F4` | Click tab |

### Environment Adaptive

- **Local terminal:** Full 24-bit color, mouse, Unicode, rich visuals
- **SSH:** Degrades gracefully to 256-color, mouse often works
- **Design for both:** User chooses connection method, TUI adapts

### Anti-Patterns to Avoid

- **GUI-only** — Must work in terminal
- **Polling refresh** — Use WebSocket push
- **Hidden kill switch** — Always visible
- **Session loss on disconnect** — Daemon persistence
- **Complex nested menus** — Flat, fast access

### Design Inspiration Strategy

**Adopt:** Textual DataTable, TCSS theming, dual-path input, tmux attach/detach
**Adapt:** msfconsole hierarchy → Target tree, htop bars → severity indicators
**Avoid:** GUI-only C2, complex nested menus, auto-dismiss notifications

---

## Design System Foundation

### Design System Choice

**Custom TCSS Theme with Design Tokens** — extending v1's proven approach with structured semantic tokens for v2's expanded complexity.

### Rationale for Selection

1. **v1 Foundation** — `style.tcss` already exists and works
2. **Textual-native** — TCSS is the right tool for Textual
3. **Semantic Tokens** — Enable consistent theming across 10+ widget types
4. **"Command & Control"** — Dark, cyber-aesthetic matches product identity

### Color Token System

| Category | Tokens |
|----------|--------|
| **Backgrounds** | `$bg-primary`, `$bg-secondary`, `$bg-elevated` |
| **Text** | `$text-primary`, `$text-muted` |
| **Semantic** | `$accent`, `$danger`, `$warning`, `$success`, `$info` |
| **Agent Status** | `$status-idle`, `$status-scanning`, `$status-thinking`, `$status-attacking`, `$status-exploited`, `$status-paused` |

### Widget Pattern Library

- **Pane Title** — Section headers with accent color
- **Status Badge** — Color-coded agent/engagement state
- **Action Button** — Keyboard hint visible, clickable
- **Modal Screen** — Elevated background, focused interaction
- **Data Table** — Virtualized, hover/select states

### Implementation Approach

1. Extract and document v1's `style.tcss`
2. Define CSS variables for all tokens
3. Create reusable component classes
4. Document usage patterns for consistency

---

## Defining Experience

### The Core Interaction

**"Watch your AI army discover and exploit targets while you command from the War Room."**

Root tells others: "I give it a target and an objective, then watch hundreds of agents coordinate to break in. When they need permission to pivot, I approve with a keystroke."

### User Mental Model

- **From:** "I am the pentester using tools"
- **To:** "I am the general commanding a red team army"

**Familiar Metaphors:** RTS games, stock trading terminals, air traffic control

### Success Criteria

| Criterion | Indicator |
|-----------|-----------|
| "It's working" | First finding <60s |
| "I'm in control" | Kill switch <1s |
| "This is smart" | Unexpected attack paths discovered |
| "Fast decisions" | Authorization <5s |
| "Mission complete" | Clear achievement + deliverables |

### Novel UX Patterns

**Authorization Flow** — The core novel interaction:
- Agent proposes action with full context
- Root sees: target, action, risk, constraints
- Response: Y (approve) / N (deny) / M (modify) / S (skip)

### Experience Mechanics

**Initiation:** NL directive → scope config → START
**Interaction:** Monitor (watch) → Authorize (Y/N) → Control (pause/resume/kill)
**Feedback:** Color status, pulse animations, log entries, celebrations
**Completion:** "OBJECTIVE ACHIEVED" → summary → deliverables → session saved

---

## Visual Design Foundation

### Color System

**Backgrounds:** `$bg-primary` (#0a0a0a) → `$bg-elevated` (#2a2a2a)
**Text:** `$text-primary` (#e0e0e0) → `$text-muted` (#606060)
**Semantic:** `$accent` (cyber-green), `$danger` (red), `$warning` (orange), `$info` (blue), `$success` (green)
**Agent Status:** Idle (grey), Scanning (blue), Thinking (yellow), Attacking (red), Exploited (green), Paused (orange)

### Typography System

- Monospace only (terminal-dependent)
- Hierarchy via color + bold/italic
- Title: accent + bold | Body: primary | Muted: secondary

### Layout Foundation

**Header Row 1:** [F1] Dashboard [F2] Config [F3] Logs [F4] Report [F5] Stats | [ESC] KILL
**Header Row 2:** MODE | ENGAGEMENT | STATE | [AUTH: n]

**Three-Pane Layout:**

| Pane | Content |
|------|---------|
| **Left** | TARGETS (tree view) |
| **Middle** | HIVE MATRIX (agent grid + status colors) |
| **Right** | STRATEGY STREAM (Director Ensemble + Stigmergic activity) |

**Bottom:** TERMINAL (raw tool output, scrollable)

### Strategy Stream Panel (New for v2)

Combines Director Ensemble output + Stigmergic activity:
- Director re-plan blocks with trigger reason
- Current strategy + confidence % (with tooltip showing historical accuracy calibration)
- 3 LLM perspectives (⚡DeepSeek 🎯Kimi 🧠MiniMax)
- Stigmergic causality (🔗 agent acting on signals)
- Finding propagation (💡📢)

### Animation & Feedback

- Instant color transitions on state change
- Pulse effect on finding discovery
- Blink on authorization request
- Heartbeat indicator for C2 (5s pulse cycle) with latency granularity: ● healthy (<500ms) | ◐ degraded (500-2000ms) | ○ critical (>2000ms)

### Accessibility

- 4.5:1 contrast ratios
- Color + text labels (no color-only info)
- Full keyboard + mouse accessibility

---

## Design Direction Decision

### Design Directions Explored

| Direction | Description | Verdict |
|-----------|-------------|---------|
| D1 Dense | v1 evolution, maximum info density | Base chosen |
| D2 Spacious | More whitespace, strategy-focused | Too sparse for War Room |
| D3 Tabs | Tab-based screens | F-key screens only |
| D4 Target-Centric | Strategy follows selected target | Loses swarm overview |

### Chosen Direction: D1 Dense Hybrid

Three-pane War Room layout with enhancements:

**Header:**
- F-key bar: [F1]Dash [F2]Cfg [F3]Log [F4]Rpt [F5]Stats [F6]Drop
- Status: ●/◐/○ C2 heartbeat (latency indicator) | [AUTH: n] | [ESC] KILL
- Info: MODE | ENGAGEMENT | STATE

**Three-Pane Layout:**
- **Left:** TARGETS (tree view)
- **Middle:** HIVE MATRIX (agent grid + status colors + agent/anomaly count + filter bar)
- **Right:** STRATEGY STREAM (Director Ensemble + Stigmergic activity)

**Bottom:** TERMINAL (raw tool output)

**F-Key Screens (separate from War Room):**
- F2: Config screen
- F3: Logs screen
- F6: Drop Box setup/status screen

### Design Rationale

1. **Maintains v1 familiarity** — Evolution, not revolution
2. **Everything visible at once** — "General commanding army" feel
3. **Strategy Stream prominent** — Director thinking always visible
4. **Drop Box accessible** — F6 + header heartbeat indicator
5. **PRD compliant** — FR7, FR10, FR11, FR12 all satisfied
6. **Implementation proven** — v1 code migration path clear

### Implementation Approach

- Base layout from v1 `app.py`
- Enhance Strategy Stream widget (taller, structured)
- Add C2 heartbeat indicator to header
- Add F6 Drop Box screen
- Keep F1-F5 as existing pattern

---

## User Journey Flows

### Journey 1: Standard Engagement

**Entry:** `cyber-red new` or TUI "New Engagement"

**Flow:**
1. Enter NL directive → Parse & validate
2. Scope configuration (targets, constraints, RoE)
3. Pre-flight checks → Confirm & Start
4. **War Room Monitoring Loop:**
   - Watch Hive Matrix
   - See Director strategies
   - Findings stream in (💡)
   - Authorization requests appear
5. Handle interrupts: AUTH (Y/N/M/S), KILL, PAUSE, SCOPE_EDIT
6. Live scope modification (expand/contract targets without restart) — requires confirmation modal with target preview ("Adding 10.0.2.0/24 — 254 new targets. Confirm?") + 5s countdown for production ranges + 10s undo window
7. Objective achieved → Summary & Deliverables → Export

**Key UX:** NL directive parsing feedback, findings pulse, auth modal with swarm state snapshot, live scope editing

### Journey 2: Drop Box Deployment

**Entry:** F6 Drop Box screen

**Flow:**
1. NL Setup Wizard ("I need to deploy a drop box...")
2. System responds with download link + instructions
3. Wait for connection (timeout → retry)
4. Connection detected → Pre-flight protocol:
   - ✓ PING → ✓ EXEC_TEST → ✓ STREAM_TEST → ✓ NET_ENUM → ✓ READY
5. Drop Box ready (●C2 heartbeat in header)
6. Return to War Room (WiFi pivot enabled)
7. Monitor C2 health (lost → alert, retry 30s)

**Key UX:** Conversational setup, visual checkmarks, persistent heartbeat indicator

### Journey 3: Blocked Path / Edge Case

**Entry:** During engagement, swarm hits resistance

**Flow:**
1. Swarm hits resistance (WAF, firewall, dead end)
2. Strategy Stream shows attempts + failures
3. Director re-plans (triggered by repeated_failures)
4. 3 perspectives shown (⚡🎯🧠)
5. Swarm pivots automatically OR auth for novel approach
6. Progress resumes (or escalate to RAG)

**Key UX:** Failure visible (not hidden), Director reasoning shown, RAG escalation transparent

### Journey Patterns

**Navigation:** F-key screens, modal overlays, tree drill-down, stream scroll
**Decision:** Y/N/M/S for auth, confirm only critical, auto-proceed for status
**Feedback:** Progress checkmarks, pulse on discovery, heartbeat indicator, instant color change

### Flow Optimization Principles

1. **Minimize steps to value** — NL to swarm running in <5 clicks
2. **Never silent failure** — Error shows what + recovery path
3. **Context at decision** — Auth requests show full context inline
4. **Progressive disclosure** — Details on demand
5. **Interruptible** — Pause/Kill always accessible

---

## Component Strategy

### Textual Built-in Components

| Component | Usage |
|-----------|-------|
| `Header` | Top bar with F-keys, status |
| `Footer` | Keybinding hints |
| `DataTable` | Virtualized lists (agents, findings) |
| `Tree` | Target hierarchy base |
| `Button` | Kill switch, auth buttons |
| `Input` | NL directive, search |
| `TextLog` | Terminal output base |
| `ProgressBar` | Pre-flight progress |
| `Modal` | Authorization overlay base |

### Custom Components

| Component | Purpose |
|-----------|---------|
| `HiveMatrix` | 10K agent grid with status colors, anomaly bubbling, filter bar (by state/target/kill chain phase), priority queue for critical events, critical finding override (objective-relevant findings ignore filters), filter warning indicator ("N findings hidden by current filter") |
| `StrategyStream` | Director Ensemble + Stigmergic activity unified |
| `AuthorizationModal` | Y/N/M/S with full context display + Swarm State Snapshot showing agent distribution at request time + auth batching ("Approve all similar?") + 3s cooldown on consecutive approvals to prevent auth fatigue + configurable auth timeout (default: 30min auto-deny) |
| `HeartbeatIndicator` | C2 status with latency granularity (●/◐/○) |
| `PreflightProgress` | Drop box pre-flight checkmarks |
| `StatusBadge` | Colored state indicator |
| `TargetTree` | Extended Tree with port/agent hierarchy |
| `FindingPulse` | Discovery celebration animation |
| `TimelineScrubber` | Engagement history review — scroll through past events, replay what happened during disconnect |
| `StickyKillButton` | Always-visible kill control regardless of scroll position |
| `ExternalNotifier` | Optional webhook/email alerts for pending auth requests when disconnected |

### Component Implementation Strategy

- Extend Textual widgets, don't replace
- Use TCSS tokens for consistent styling
- Support both keyboard and mouse
- Implement accessibility (ARIA, screen reader)

### Implementation Roadmap

**Phase 1 — Core:** HiveMatrix, StrategyStream, AuthorizationModal, StatusBadge
**Phase 2 — Drop Box:** HeartbeatIndicator, PreflightProgress, TargetTree
**Phase 3 — Polish:** FindingPulse, accessibility, 10K+ performance optimization

---

## UX Consistency Patterns

### Action Hierarchy

| Level | Style | Examples | Keyboard |
|-------|-------|----------|----------|
| **Primary** | `$accent` bg, bold | Start, Approve | `Enter` |
| **Secondary** | `$bg-elevated`, border | Pause, Export | F-key |
| **Destructive** | `$danger` bg | Kill, Wipe | `ESC`, confirm |
| **Ghost** | Text only, muted | Cancel, Skip | `Q`, `N` |

### Feedback Patterns

| Type | Color | Duration | Example |
|------|-------|----------|---------|
| **Success** | `$success` | Flash 1s | Finding discovered |
| **Error** | `$danger` | Persist | Connection failed |
| **Warning** | `$warning` | Persist | C2 reconnecting |
| **Info** | `$info` | 3s auto | Config saved |
| **Progress** | `$accent` | Until done | Pre-flight |
| **Audio Alert** | Terminal bell | Optional | Critical auth requests (configurable) |

### Navigation Patterns

| Pattern | Trigger | Behavior |
|---------|---------|----------|
| **F-key screens** | F1-F6 | Switch screen, preserve state |
| **Modal overlay** | Action | Focus trap, ESC to close |
| **Tree navigation** | j/k ↑/↓ | Move selection, Enter expand |
| **Pane focus** | Tab/click | Cycle between panes |

### Input Patterns

| Type | Widget | Validation |
|------|--------|------------|
| **NL Directive** | Multi-line Input | Parse + confirm |
| **Scope Config** | Form fields | Real-time validation |
| **Authorization** | Y/N/M/S buttons | Instant response |
| **Confirmation** | Modal Y/N | Explicit choice required |

### State Patterns

| State | Visual | Action |
|-------|--------|--------|
| **Loading** | Spinner `⋯` | Wait or Cancel |
| **Empty** | Muted text | Contextual hint |
| **Error** | `$danger` border | Retry or Dismiss |
| **Disconnected** | `$warning` header | Auto-retry |
| **Stale State** | `$warning` + timestamp | "No activity for 60s" warning; refresh prompt |
| **Target Unreachable** | `$warning` | Auto-pause swarm + alert; prevents blind continuation |

### Keyboard Consistency

| Action | Key | Global |
|--------|-----|--------|
| Kill switch | `ESC` / `Ctrl+C` / `k` / `Ctrl+\` | Yes (multi-path for tmux/screen compatibility; Ctrl+\ as SIGQUIT last resort) |
| Approve | `Y` | Auth modal |
| Deny | `N` | Auth modal |
| Pause | `F5` | Yes |
| Resume | `F6` | Yes |
| Help | `?` | Yes |
| Quit | `Ctrl+Q` | Yes (confirm) |

### Animation Consistency

| Animation | Duration | Usage |
|-----------|----------|-------|
| Color transition | Instant | Status change |
| Pulse/flash | 500ms | Finding discovery |
| Blink | 1s cycle | Pending auth (persists until acknowledged, ignores other events) |
| Heartbeat | 5s cycle | C2 connection |

---

## Responsive Design & Accessibility

### Responsive Strategy (Terminal Sizes)

| Terminal Size | Layout | Priority |
|---------------|--------|----------|
| **80x24** (Minimum) | Compact — single pane focus, tabs (wireframe validation required) | Must work |
| **100x30** (Standard) | Balanced — all panes visible | Default |
| **120x40+** (Optimal) | Full — expanded content | Recommended |

### Breakpoint Strategy

| Breakpoint | Width | Behavior |
|------------|-------|----------|
| **Compact** | <100 cols | Single pane + tabs (must preserve situational awareness) |
| **Standard** | 100-119 cols | Three panes, compressed |
| **Optimal** | 120+ cols | Full layout |

### Accessibility Strategy

**Target:** WCAG 2.1 Level AA equivalent

| Requirement | Implementation |
|-------------|----------------|
| Keyboard Navigation | All actions via keyboard |
| Screen Reader | Textual announcements |
| Color Contrast | 4.5:1 ratio |
| No Color-Only | Status = color + text |
| Focus Indicators | Visible focus ring |

### Testing Strategy

- Terminal size testing (80x24 to 200x60)
- Keyboard-only navigation
- Screen reader testing
- SSH vs local terminal
- High contrast themes

### Implementation Guidelines

**Responsive:** Use Textual grid/dock, set constraints, graceful degradation
**Accessibility:** Clear labels, announce state changes, never color-only

