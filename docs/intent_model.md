# Intent Model — IntentContract Specification

## Overview

The IntentContract is the foundational document of every GRID session. It captures the user's intent in a structured, machine-enforceable format **before** any agent begins operating.

The contract serves as the constitution that GRID enforces. Once signed (hashed), it becomes immutable — no agent can modify it.

---

## Design Philosophy

### Why Intent Contracts?

In traditional AI agent systems, the user provides a natural language instruction, and the agent interprets it. This creates a fundamental problem:

- **Ambiguity**: "Handle my NVDA position" could mean research, buy, sell, or hedge
- **Scope creep**: Agents may take actions beyond what the user contemplated
- **Implicit trust**: There's no verification that the agent's interpretation matches the user's actual intent

Intent Contracts solve this by requiring **explicit, bounded declarations** of what agents are allowed to do.

### Key Properties

| Property | Description |
|---|---|
| **Immutable** | Once signed, the contract cannot be modified by any agent |
| **Declarative** | Users specify what agents can do, not how |
| **Bounded** | Every permission has explicit quantitative limits |
| **Verifiable** | SHA-256 hash enables integrity verification at any time |
| **Complete** | All necessary constraints are specified upfront |

---

## Contract Schema

### Core Fields

```python
{
    "contract_id": "uuid4",           # Unique identifier
    "created_at": "ISO-8601",         # Creation timestamp
    "user_id": "string",              # Authorizing user
    "goal": "string",                 # Natural language intent
    "is_signed": true,                # Whether contract is signed
    "contract_hash": "sha256-hex",    # Integrity hash
}
```

### Trade Constraints

```python
"trade_constraints": {
    "allowed_tickers": ["AAPL", "GOOGL", "MSFT", "NVDA"],
    "max_order_value": 10000.0,       # USD per order
    "max_daily_value": 50000.0,       # USD per day (aggregate)
    "allowed_order_types": ["market", "limit"],
    "allowed_sides": ["buy"],         # buy, sell
    "market_hours_only": true         # Restrict to NYSE hours
}
```

### Data Constraints

```python
"data_constraints": {
    "allowed_directories": ["./market_data"],
    "allowed_endpoints": [],           # External APIs
    "deny_external_transfer": true     # Block outbound data
}
```

### Agent Permissions

```python
"agent_permissions": [
    {
        "role": "analyst",
        "allowed_tools": ["market_data", "get_position"],
        "can_delegate": false,
        "max_delegation_depth": 0
    },
    {
        "role": "trader",
        "allowed_tools": ["market_data", "place_order", "get_position"],
        "can_delegate": false,
        "max_delegation_depth": 0
    }
]
```

---

## Signing Process

1. User creates the contract with all constraints
2. The `sign()` method is called
3. Contract content (excluding hash fields) is serialized to JSON with sorted keys
4. SHA-256 hash is computed over the serialized content
5. Hash is stored in `contract_hash` field
6. `is_signed` is set to `true`
7. Any subsequent modification invalidates the hash

```python
contract = IntentContract(
    user_id="user_001",
    goal="Research and trade AAPL",
    trade_constraints=TradeConstraints(
        allowed_tickers=["AAPL"],
        max_order_value=10000.0,
    ),
)

# Sign the contract — makes it immutable
contract.sign()

# Verify integrity at any time
assert contract.verify_integrity() == True

# If tampered with, integrity check fails
contract.trade_constraints.max_order_value = 999999.0
assert contract.verify_integrity() == False  # TAMPERED
```

---

## Integrity Verification

The contract hash is verified at three critical points:

1. **PolicyEngine initialization** — Engine refuses to start with an invalid contract
2. **Every policy evaluation** — First rule in the chain is contract integrity
3. **On demand** — `verify_integrity()` can be called at any time

If integrity verification fails at any point, **all operations halt immediately.**

---

## Contract Lifecycle

```
┌──────────┐     sign()     ┌──────────┐     evaluate()    ┌──────────────┐
│  DRAFT   │ ────────────→  │  SIGNED  │ ────────────────→ │  ENFORCED    │
│          │                │  (locked) │                   │  (immutable) │
└──────────┘                └──────────┘                   └──────────────┘
     ↑                            │
     │                            │  verify_integrity()
     │                            │  ────────────────→ true/false
     │                            │
     └── CANNOT return to draft ──┘
```

---

## Usage Examples

### Minimal Contract
```python
contract = IntentContract(
    user_id="user_001",
    goal="Monitor AAPL price movements",
    trade_constraints=TradeConstraints(allowed_tickers=["AAPL"]),
    agent_permissions=[
        AgentPermissions(role="analyst", allowed_tools=["market_data"]),
    ],
).sign()
```

### Full Trading Contract
```python
contract = IntentContract(
    user_id="user_001",
    goal="Research and trade select tech stocks with risk controls",
    trade_constraints=TradeConstraints(
        allowed_tickers=["AAPL", "GOOGL", "MSFT", "NVDA"],
        max_order_value=10000.0,
        max_daily_value=50000.0,
        allowed_order_types=["market", "limit"],
        allowed_sides=["buy"],
        market_hours_only=True,
    ),
    data_constraints=DataConstraints(
        allowed_directories=["./market_data"],
        deny_external_transfer=True,
    ),
    agent_permissions=[
        AgentPermissions(role="analyst", allowed_tools=["market_data", "get_position"]),
        AgentPermissions(role="risk", allowed_tools=["market_data", "get_position", "get_portfolio"]),
        AgentPermissions(role="trader", allowed_tools=["market_data", "place_order", "get_position"]),
    ],
    max_delegation_depth=2,
).sign()
```
