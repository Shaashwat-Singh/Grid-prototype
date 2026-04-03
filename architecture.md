# GRID Architecture — Deep Dive

## Overview

GRID (Governance, Restriction, Intent, and Delegation) is a constitutional enforcement layer designed to sit between autonomous AI agent reasoning and financial execution. This document provides the complete technical specification.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         USER LAYER                                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   IntentContract                           │  │
│  │  - Allowed tickers: ["AAPL", "GOOGL", "MSFT", "NVDA"]    │  │
│  │  - Max per-order: $10,000                                  │  │
│  │  - Max daily: $50,000                                      │  │
│  │  - Allowed tools: [market_data, place_order, get_position] │  │
│  │  - Data scope: ./market_data/*                             │  │
│  │  - Delegation depth: 2                                     │  │
│  │  - Market hours only: true                                 │  │
│  │  - SHA-256 hash: locked at creation                        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   AGENT MESH (OpenClaw)                    │  │
│  │                                                            │  │
│  │  AnalystAgent ──→ RiskAgent ──→ TraderAgent               │  │
│  │  (research)       (validate)    (request)                  │  │
│  │                                                            │  │
│  │  Agents produce ActionRequests, never execute directly     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                    ActionRequest                                  │
│                              │                                    │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │               ENFORCEMENT GATE (GRID Core)                 │  │
│  │                                                            │  │
│  │  1. Validate agent identity & authorization                │  │
│  │  2. Check action against IntentContract                    │  │
│  │  3. Run PolicyEngine rule chain                            │  │
│  │  4. Log decision to AuditLog (before execution)            │  │
│  │  5. Execute via Alpaca API (if allowed)                    │  │
│  │  6. Return result to agent                                 │  │
│  │                                                            │  │
│  │  ⚠️  Gate holds all API credentials                        │  │
│  │  ⚠️  Agents have ZERO direct API access                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                          │          │                              │
│                    ┌─────┘          └─────┐                       │
│                    ▼                      ▼                       │
│  ┌──────────────────────┐  ┌──────────────────────────────┐     │
│  │    ALPACA PAPER API  │  │       AUDIT LOG              │     │
│  │    (execution layer) │  │   (append-only, hashed)      │     │
│  └──────────────────────┘  └──────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. IntentContract

The IntentContract is the **constitutional document** of a GRID session. It captures the user's intent before any agent begins operating.

**Properties:**
- **Immutability**: Once created, the contract is hashed (SHA-256). Any modification invalidates the hash and halts all operations.
- **Declarative**: Users declare what agents are allowed to do, not how.
- **Bounded**: Every permission has explicit limits.

**Schema:**
```python
{
    "contract_id": "uuid4",
    "created_at": "ISO-8601 timestamp",
    "user_id": "string",
    "goal": "Natural language description of intent",
    "constraints": {
        "allowed_tickers": ["AAPL", "GOOGL", ...],
        "max_order_value": 10000.0,
        "max_daily_value": 50000.0,
        "allowed_tools": ["market_data", "place_order", ...],
        "data_scope": "./market_data/*",
        "max_delegation_depth": 2,
        "market_hours_only": true,
        "allowed_order_types": ["market", "limit"]
    },
    "agent_permissions": {
        "analyst": ["market_data", "get_position"],
        "risk": ["market_data", "get_position", "get_portfolio"],
        "trader": ["market_data", "place_order", "get_position"]
    },
    "hash": "sha256-of-serialized-contract"
}
```

### 2. PolicyEngine

The PolicyEngine evaluates every ActionRequest against the IntentContract through a **deterministic rule chain**.

**Rule Evaluation Order:**
1. Agent authorization check
2. Ticker universe validation
3. Per-order size limit
4. Daily aggregate limit (cumulative tracking)
5. Tool permission check
6. Data access scope validation
7. Delegation depth check
8. Prompt injection detection
9. Market hours constraint
10. Order type validation

**Evaluation Logic:**
- **All rules must pass.** One failure = BLOCK.
- Rules are evaluated in order. First failure short-circuits.
- Each rule returns a `PolicyResult` with pass/fail and reason.
- The aggregate result includes all individual rule evaluations.

### 3. AuditLog

The AuditLog is an **append-only, integrity-verified** record of every policy evaluation.

**Properties:**
- **Append-only**: Entries can never be modified or deleted.
- **Hash-chained**: Each entry includes a hash of the previous entry, creating a tamper-evident chain.
- **Pre-execution**: Decisions are logged BEFORE any execution occurs.
- **Complete**: Both ALLOW and BLOCK decisions are logged with full context.

**Entry Schema:**
```python
{
    "entry_id": "uuid4",
    "timestamp": "ISO-8601",
    "previous_hash": "sha256-of-previous-entry",
    "agent_id": "string",
    "action_type": "trade | data_access | tool_use | delegation",
    "action_details": { ... },
    "contract_id": "uuid4",
    "policy_results": [
        {"rule": "ticker_check", "passed": true, "reason": "AAPL in allowed universe"},
        {"rule": "size_check", "passed": true, "reason": "$5000 <= $10000 limit"},
        ...
    ],
    "verdict": "ALLOW | BLOCK",
    "block_reason": "null | string",
    "entry_hash": "sha256-of-this-entry"
}
```

### 4. EnforcementGate

The EnforcementGate is the **single point of control** between agent reasoning and financial execution.

**Responsibilities:**
- Receive ActionRequests from agents
- Invoke PolicyEngine for evaluation
- Write decision to AuditLog
- Execute allowed actions via Alpaca API (gate holds credentials)
- Return results to requesting agent
- Block and log all denied actions

**Credential Isolation:**
- Only the EnforcementGate has access to Alpaca API credentials.
- Agents receive a reference to the gate, never to the API.
- The gate validates every request regardless of source.

---

## Security Model

### Threat Model

| Threat | Mitigation |
|---|---|
| Agent places unauthorized trade | PolicyEngine blocks actions outside IntentContract |
| Agent accesses restricted data | Data scope validation in policy chain |
| Agent self-escalates permissions | Contract is immutable, hash-verified |
| Prompt injection in agent reasoning | Injection pattern detection in policy engine |
| Agent delegates beyond authority | Delegation depth tracking and enforcement |
| Tampered audit log | Hash-chain integrity verification |
| Direct API access bypass | Credentials isolated to EnforcementGate only |

### Zero-Trust Principles

1. **No implicit trust**: Every action is validated, even from "trusted" agents.
2. **Least privilege**: Each agent gets minimum necessary permissions.
3. **Fail closed**: Any ambiguity or error defaults to BLOCK.
4. **Complete mediation**: Every action goes through the gate. No shortcuts.

---

## Data Flow

```
User Intent → IntentContract (immutable, hashed)
                    ↓
            Agent Mesh (OpenClaw)
            AnalystAgent: "AAPL looks strong, buy signal"
                    ↓
            RiskAgent: "Exposure acceptable, approved"
                    ↓
            TraderAgent: ActionRequest{buy AAPL, 50 shares, ~$8500}
                    ↓
            EnforcementGate.process(request)
                    ↓
            PolicyEngine.evaluate(request, contract)
                ├── agent_authorized? ✓
                ├── ticker_allowed? ✓ (AAPL in universe)
                ├── size_ok? ✓ ($8500 < $10000)
                ├── daily_ok? ✓ ($8500 < $50000)
                ├── tool_ok? ✓ (place_order allowed for trader)
                ├── delegation_ok? ✓ (depth 0)
                ├── injection_ok? ✓ (no patterns detected)
                └── market_hours? ✓
                    ↓
            Verdict: ALLOW
                    ↓
            AuditLog.record(decision)  ← logged BEFORE execution
                    ↓
            Alpaca API: execute trade
                    ↓
            Result returned to TraderAgent
```

---

## Future Roadmap

- [ ] Multi-user contract support with role-based access
- [ ] Real-time contract amendment with human-in-the-loop approval
- [ ] Integration with additional brokers (Interactive Brokers, TD Ameritrade)
- [ ] ML-based anomaly detection on top of deterministic rules
- [ ] Formal verification of policy engine rule completeness
- [ ] WebSocket-based real-time audit stream
- [ ] Contract templating for common financial workflows
