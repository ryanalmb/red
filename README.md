# 🔴 Cyber-Red: HAMAS for Offensive Security

**Cyber-Red** is a Hierarchical Autonomous Multi-Agent System (HAMAS) designed to simulate nation-state level cyber attacks for defensive hardening.

![Status](https://img.shields.io/badge/Status-Operational-green)
![Build](https://img.shields.io/badge/Build-Docker-blue)
![Brain](https://img.shields.io/badge/AI-NVIDIA%20NIM-76b900)

## 🚀 Key Features
*   **Elastic Swarm:** Scales from 1 to 100+ agents using a "Worker Pool" architecture on a single node.
*   **Cognitive Core:** "Council of Experts" architecture using **Llama 3.1 405B** (Strategy) and **Codestral 22B** (Execution).
*   **Iron Triangle Governance:** Strict "Rules of Engagement" (RoE) enforcement via a dedicated AI Critic and Python Hard Gate.
*   **Command Center:** SSH-ready Textual TUI for real-time monitoring and Human-in-the-Loop control.

## 🛠️ Installation

### Prerequisites
*   Docker & Docker Compose (v2.0+)
*   Python 3.12+
*   NVIDIA NIM API Key

### Setup
1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-org/cyber-red.git
    cd cyber-red
    ```

2.  **Configure Environment:**
    Create a `.env` file:
    ```bash
    NVIDIA_API_KEY=nvapi-your-key-here
    NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
    ```

3.  **Start Infrastructure:**
    This spins up Redis, the Kali Worker Pool, and the Metasploitable Target.
    ```bash
    docker compose up -d
    ```

4.  **Install Python Dependencies:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

## 🎮 Usage

**Launch the War Room:**
```bash
source venv/bin/activate
python3 -m src.main
```

### Controls
*   `q`: Quit
*   `d`: Toggle Dark Mode
*   `F5`: Review Pending Approvals (HITL)
*   `p`: **PANIC** (Emergency Kill Switch)

## 🛡️ Configuration (Rules of Engagement)
Edit `config/roe.yaml` to define your scope.
**WARNING:** The system enforces these rules strictly.

```yaml
allowed_ips:
  - "172.20.0.3" # The target container IP
forbidden_ports:
  - 21
aggression_level: "HIGH"
```

## 🏗️ Architecture
*   **Brain:** `src/core/council.py`
*   **Hands:** `src/mcp/` (Metasploit/Nmap adapters)
*   **Face:** `src/ui/` (Textual App)

## ⚠️ Disclaimer
This tool is for **AUTHORIZED DEFENSIVE TESTING ONLY**. Misuse against unauthorized targets is illegal. The "Critic" module is designed to reject unethical commands, but the Operator bears full responsibility.
