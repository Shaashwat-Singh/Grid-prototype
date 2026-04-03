# Policy Model — PolicyEngine Specification

## Overview

The PolicyEngine is GRID's deterministic rule-chain evaluator. It evaluates every ActionRequest against the IntentContract through a fixed sequence of policy rules. **All rules must pass for an action to be allowed. One failure = BLOCK.**

---

## Design Principles

| Principle | Implementation |
|---|---|
| **Fail-closed** | Any ambiguity, error, or missing data defaults to BLOCK |
| **Deterministic** | Same input always produces the same output — no probabilistic reasoning |
| **Complete** | Every action type has applicable rules; no unchecked paths |
| **Ordered** | Rules execute in a fixed sequence; first failure short-circuits |
| **Auditable** | Every individual rule evaluation is captured in the PolicyResult |

---

## Rule Chain

The PolicyEngine evaluates rules in this exact order:

### Universal Rules (All Actions)

| # | Rule | Description | Failure Impact |
|---|---|---|---|
| 1 | `contract_integrity` | Verify IntentContract hash hasn't been tampered | HALT — all operations blocked |
| 2 | `agent_authorization` | Check agent role exists in the contract | BLOCK — unrecognized agent |

### Trade-Specific Rules

| # | Rule | Description | Failure Impact |
|---|---|---|---|
| 3 | `ticker_check` | Validate ticker is in the allowed universe | BLOCK — unauthorized asset |
| 4 | `order_size_check` | Verify order value ≤ per-order limit | BLOCK — oversized order |
| 5 | `daily_limit_check` | Verify cumulative daily total ≤ daily cap | BLOCK — daily cap exceeded |
| 6 | `order_type_check` | Validate order type is permitted | BLOCK — unauthorized order type |
| 7 | `trade_side_check` | Validate trade side (buy/sell) is permitted | BLOCK — unauthorized side |
| 8 | `market_hours_check` | Verify trading during market hours (if required) | BLOCK — outside market hours |

### Tool & Data Rules

| # | Rule | Description | Failure Impact |
|---|---|---|---|
| 9 | `tool_permission_check` | Verify agent role has access to the tool | BLOCK — unauthorized tool |
| 10 | `data_scope_check` | Validate file path is within allowed directories | BLOCK — outside data scope |

### Delegation Rules

| # | Rule | Description | Failure Impact |
|---|---|---|---|
| 11 | `delegation_depth_check` | Verify delegation depth ≤ contract maximum | BLOCK — depth exceeded |

### Security Rules

| # | Rule | Description | Failure Impact |
|---|---|---|---|
| 12 | `injection_detection` | Scan raw reasoning for prompt injection patterns | BLOCK — injection detected |

---

## Rule Evaluation Flow

```
ActionRequest arrives
        │
        ▼
┌─ contract_integrity ─┐
│  Hash match?          │──── NO ──→ BLOCK (CRITICAL)
└─────── YES ──────────┘
        │
        ▼
┌─ agent_authorization ─┐
│  Role in contract?     │──── NO ──→ BLOCK
└─────── YES ───────────┘
        │
        ▼
┌─ [action-specific rules] ─┐
│  All pass?                  │──── NO ──→ BLOCK
└───────── YES ──────────────┘
        │
        ▼
┌─ injection_detection ─┐
│  Clean reasoning?       │──── NO ──→ BLOCK
└─────── YES ────────────┘
        │
        ▼
    ALLOW ✓
```

---

## Daily Aggregate Tracking

The PolicyEngine maintains a running total of daily trading values per agent role. This enables enforcement of daily spending caps that span multiple individual trades.

```python
# Internal state
_daily_totals: Dict[str, float] = {}  # agent_role -> cumulative USD
_daily_date: str = "2024-01-15"        # resets on date change

# Evaluation
current_total = _daily_totals.get("trader", 0.0)  # e.g., $8,625
new_total = current_total + request.estimated_value  # + $9,964 = $18,589
limit = contract.trade_constraints.max_daily_value   # $50,000

# $18,589 <= $50,000 → ALLOW (update total)
# if new_total > limit → BLOCK (do not update total)
```

Key behaviors:
- Totals reset at the start of each UTC day
- Only ALLOWED trades increment the running total
- BLOCKED trades do not affect the daily counter
- Each agent role has its own counter

---

## Prompt Injection Detection

The PolicyEngine includes pattern-based detection for common prompt injection techniques:

### Detected Patterns

```
ignore previous instructions
ignore all rules
disregard your policy
override safety
pretend you are
jailbreak
do anything now
bypass the filter
system prompt
act as if you have
new instructions:
<<< system
admin mode
sudo
execute without checking
```

### Detection Process

1. If `raw_reasoning` is provided in the ActionRequest, it is scanned
2. Each pattern is evaluated as a case-insensitive regex
3. First match triggers BLOCK with pattern identification
4. If no `raw_reasoning` is provided, the check is skipped (pass)

### Limitations

Pattern-based detection catches known injection templates but is not comprehensive. Future versions will integrate:
- Semantic similarity detection
- LLM-based reasoning analysis
- Behavioral anomaly detection

---

## PolicyResult Structure

Every evaluation produces a detailed `PolicyResult`:

```python
PolicyResult(
    verdict=PolicyVerdict.ALLOW,  # or BLOCK
    rule_results=[
        RuleResult(rule_name="contract_integrity", passed=True, reason="Contract integrity verified"),
        RuleResult(rule_name="agent_authorization", passed=True, reason="Agent role 'trader' is authorized"),
        RuleResult(rule_name="ticker_check", passed=True, reason="Ticker 'AAPL' is in the allowed universe"),
        RuleResult(rule_name="order_size_check", passed=True, reason="Order value $8,625.00 within limit $10,000.00"),
        RuleResult(rule_name="daily_limit_check", passed=True, reason="Daily total $8,625.00 within limit $50,000.00"),
        # ... all rules
    ],
    block_reasons=[],  # empty if allowed; populated if blocked
    evaluated_at="2024-01-15T14:30:00Z",
)
```

---

## Action Types

The PolicyEngine supports four action types, each with different applicable rules:

| Action Type | Applicable Rules |
|---|---|
| `trade` | All universal + trade-specific + tool permission + injection |
| `tool_use` | Universal + tool permission + injection |
| `data_access` | Universal + data scope + injection |
| `delegation` | Universal + delegation depth + injection |

---

## Error Handling

The PolicyEngine follows strict error handling:

- **Missing fields**: If a required field (e.g., `ticker` for a trade) is missing, the relevant rule fails with a descriptive reason
- **Invalid contract**: If the contract hash is invalid, the first rule fails and short-circuits
- **Exceptions**: Any exception during rule evaluation results in a BLOCK verdict
- **Unknown action types**: Only universal rules and injection detection apply
