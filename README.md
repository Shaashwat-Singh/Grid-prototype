# GRID — Constitutional Enforcement for Autonomous Financial Agents

> *"In financial systems, intent must be enforced, not inferred."*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ArmorIQ x OpenClaw Hackathon](https://img.shields.io/badge/Hackathon-ArmorIQ%20x%20OpenClaw-purple.svg)]()

---

## The Problem

Autonomous AI agents operating in financial environments introduce a fundamental security gap: **the model decides what to do, but nothing verifies that the decision matches what the user actually authorized.**

An agent told to *"look into NVDA and handle it"* might:
- Research the stock (intended)
- Place an unauthorized buy order (not intended)
- Forward portfolio data to an external endpoint (dangerous)
- Escalate its own authority and sub-delegate (policy violation)

Each interpretation carries different consequences. In financial systems, those consequences are measured in **dollars, compliance violations, and irreversible transactions.**

[OpenClaw](https://github.com/openclaw) demonstrated that autonomous agents can operate continuously in financial workflows. It also exposed a critical vulnerability: **there is no layer between what the LLM decides and what actually executes.**

**GRID is that layer.**

---

## What GRID Does

GRID is a **Constitutional Enforcement Layer** that sits between AI reasoning and financial execution. Every action an agent wants to take must pass through GRID's policy gate before it can touch the execution layer.

```
┌─────────────────────────────────────────────────────────────┐
│                    GRID ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  HUMAN INTENT DECLARATION                                   │
│  User defines: goal, trade limits, allowed tickers,         │
│  data access scope, tool permissions, delegation bounds      │
│  Stored as immutable IntentContract — agents cannot modify  │
│                                                             │
│  ↓                                                          │
│                                                             │
│  OPENCLAW AGENT MESH (Research Layer)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ Analyst     │→ │ Risk         │→ │ Trader          │   │
│  │ Agent       │  │ Agent        │  │ Agent           │   │
│  │ reads data  │  │ validates    │  │ requests trade  │   │
│  │ generates   │  │ exposure     │  │ (cannot execute │   │
│  │ signals     │  │ approves     │  │  directly)      │   │
│  └─────────────┘  └──────────────┘  └─────────────────┘   │
│                                                             │
│  ↓ ALL ACTION REQUESTS PASS THROUGH ↓                      │
│                                                             │
│  GRID ENFORCEMENT GATE (Constitutional Layer)               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ PolicyEngine.evaluate(action_request)                │  │
│  │                                                      │  │
│  │  ✓ agent authorized?                                 │  │
│  │  ✓ ticker in approved universe?                      │  │
│  │  ✓ order size within per-order limit?                │  │
│  │  ✓ daily aggregate within limit?                     │  │
│  │  ✓ tool in allowed set?                              │  │
│  │  ✓ file access within scoped directory?              │  │
│  │  ✓ delegation depth within bounds?                   │  │
│  │  ✓ no prompt injection patterns detected?            │  │
│  │  ✓ market hours constraint satisfied?                │  │
│  │                                                      │  │
│  │  All checks must pass. One failure = BLOCK.          │  │
│  │  Decision written to audit log before execution.     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ↓ ALLOW              ↓ BLOCK                              │
│                                                             │
│  ALPACA PAPER API    AUDIT LOG                             │
│  (gate holds creds)  (immutable, append-only)              │
│  agents have none    every decision logged                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Design Principles

### 1. Intent Contracts Are Immutable
The user declares their intent **before** agents start operating. This contract specifies:
- Allowed tickers, trade size limits, daily spend caps
- Which tools each agent can access
- File/data access boundaries
- Delegation depth limits
- Time-of-day constraints

Once signed, **no agent can modify the contract.** The contract is the constitution.

### 2. Reasoning Is Separated from Execution
Agents can research, analyze, and recommend — but they **cannot execute.** The enforcement gate holds all API credentials. Agents submit action requests; GRID evaluates them against the contract and either allows or blocks.

### 3. Every Decision Is Logged Before Execution
The audit log captures every policy evaluation — allowed and blocked — with full context: which agent, what action, which policy rules were checked, and the final verdict. This creates a complete forensic trail.

### 4. Fail-Closed by Default
If any policy check fails, the action is blocked. There is no "soft warning" mode for financial operations. Ambiguity defaults to denial.

---

## OpenClaw Integration

GRID extends [OpenClaw's](https://github.com/openclaw) autonomous agent framework by adding a constitutional enforcement layer:

| OpenClaw Capability | GRID Extension |
|---|---|
| Multi-agent coordination | Bounded authority per agent via IntentContract |
| Continuous financial workflows | Policy-gated execution with deterministic blocking |
| Tool-use orchestration | Tool access scoped per agent, validated per call |
| Agent delegation | Delegation depth limits with chain-of-authority tracking |
| Market data access | Data access scoped to approved directories and APIs |

GRID doesn't replace OpenClaw — it **makes OpenClaw safe for real money.**

---

## Project Structure

```
grid-prototype/
├── README.md                  # You are here
├── requirements.txt           # Dependencies
├── .env.example               # Environment variable template
├── architecture.md            # Deep-dive architecture document
├── grid/                      # Core enforcement engine
│   ├── intent_contract.py     # Immutable intent declaration
│   ├── policy_engine.py       # Constitutional policy evaluator
│   ├── audit_log.py           # Append-only audit trail
│   └── enforcement_gate.py    # The gate between reasoning and execution
├── agents/                    # OpenClaw-compatible agent mesh
│   ├── analyst_agent.py       # Research & signal generation
│   ├── risk_agent.py          # Exposure validation
│   └── trader_agent.py        # Trade request submission
├── demo/                      # Interactive demonstration
│   ├── run_demo.py            # Main demo runner
│   └── scenarios.py           # Pre-built test scenarios
├── dashboard/                 # Real-time monitoring
│   └── app.py                 # Streamlit dashboard
└── docs/                      # Technical documentation
    ├── intent_model.md        # Intent contract specification
    ├── policy_model.md        # Policy engine documentation
    └── enforcement_mechanism.md # Gate mechanism deep-dive
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- Alpaca Paper Trading API keys (free at [alpaca.markets](https://alpaca.markets))
- OpenAI API key (for agent reasoning)

### Installation

```bash
git clone https://github.com/yourusername/grid-prototype.git
cd grid-prototype
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Run the Demo

```bash
# Run the full enforcement demo with all scenarios
python -m demo.run_demo

# Launch the real-time monitoring dashboard
streamlit run dashboard/app.py
```

---

## Demo Scenarios

The demo includes **7 pre-built scenarios** that demonstrate GRID's enforcement capabilities:

| # | Scenario | Expected Result | Tests |
|---|---|---|---|
| 1 | Authorized AAPL buy within limits | ✅ ALLOW | Happy path |
| 2 | Unauthorized ticker (DOGE) | ❌ BLOCK | Ticker restriction |
| 3 | Order exceeds per-trade limit | ❌ BLOCK | Size constraint |
| 4 | Daily aggregate cap exceeded | ❌ BLOCK | Cumulative tracking |
| 5 | Unauthorized tool access | ❌ BLOCK | Tool scoping |
| 6 | Prompt injection attempt | ❌ BLOCK | Injection detection |
| 7 | Delegation depth violation | ❌ BLOCK | Authority bounds |

---

## Architecture Deep Dive

See [architecture.md](./architecture.md) for the complete technical specification, including:
- Intent Contract schema and validation
- Policy engine rule evaluation order
- Audit log format and tamper detection
- Enforcement gate credential isolation
- Agent authority model and delegation chains

---

## Why This Matters

| Without GRID | With GRID |
|---|---|
| Agent decides → Agent executes | Agent decides → GRID evaluates → Gate executes |
| Implicit trust in LLM output | Zero trust — every action validated |
| Post-hoc audit only | Pre-execution audit with block capability |
| No spending limits enforced | Hard limits per trade, per day, per agent |
| Agents can self-escalate | Authority bounded by immutable contract |
| One bad prompt = catastrophic loss | One bad prompt = blocked and logged |

---

## Technical Stack

- **Python 3.10+** — Core runtime
- **OpenClaw** — Agent orchestration framework
- **Alpaca Markets API** — Paper trading execution (credentials held by gate only)
- **OpenAI GPT-4** — Agent reasoning (replaceable with any LLM)
- **Streamlit** — Real-time monitoring dashboard
- **SHA-256 hashing** — Contract and log integrity verification

---

## Team

Built for the **ArmorIQ x OpenClaw Hackathon** by developers who believe that autonomous financial agents are inevitable — and that making them safe is non-negotiable.

---

## License

MIT License — See [LICENSE](./LICENSE) for details.

---

<p align="center">
  <strong>GRID</strong> — Because in finance, the cost of a missing guardrail is measured in dollars.
</p>
