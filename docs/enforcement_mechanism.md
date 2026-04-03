# Enforcement Mechanism — Gate Architecture Deep Dive

## Overview

The EnforcementGate is the **single point of control** between AI agent reasoning and financial execution. It is the core of GRID's security model — the component that ensures no action reaches the execution layer without passing through constitutional validation.

---

## Core Invariant

> **Agents NEVER have direct API access. The EnforcementGate is the only component with execution credentials.**

This is the fundamental security property of GRID. Agents receive a reference to the gate, never to the Alpaca API or any execution endpoint. The gate mediates all interactions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EnforcementGate                           │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ PolicyEngine │  │  AuditLog    │  │  Alpaca Client   │  │
│  │              │  │  (append-    │  │  (credentials    │  │
│  │  evaluates   │  │   only,      │  │   isolated here  │  │
│  │  requests    │  │   hashed)    │  │   ONLY)          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────────┘  │
│         │                 │                  │              │
│         └────────┬────────┘──────────────────┘              │
│                  │                                          │
│         ┌────────▼────────┐                                 │
│         │  process()      │  ← SINGLE ENTRY POINT           │
│         │                 │                                 │
│         │  1. Evaluate    │                                 │
│         │  2. Log         │  ← BEFORE execution             │
│         │  3. Execute/    │                                 │
│         │     Block       │                                 │
│         │  4. Return      │                                 │
│         └─────────────────┘                                 │
│                                                             │
│  IN:  ActionRequest (from agent)                            │
│  OUT: ExecutionResult (verdict + data)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Processing Flow

### Step 1: Policy Evaluation

```python
policy_result = self.policy_engine.evaluate(request)
```

The PolicyEngine runs the complete rule chain against the IntentContract. This is a pure function — no side effects, no API calls, no state changes other than daily total tracking.

### Step 2: Pre-Execution Audit Logging

```python
self.audit_log.record(
    agent_id=request.agent_id,
    agent_role=request.agent_role,
    action_type=request.action_type,
    action_details=action_details,
    contract_id=self.contract.contract_id,
    policy_results=policy_results,
    verdict=policy_result.verdict.value,
    block_reasons=policy_result.block_reasons,
)
```

**Critical**: The decision is logged BEFORE any execution occurs. This ensures that:
- Even if execution fails, the decision is recorded
- The audit trail is always ahead of the execution state
- Crash recovery can verify what was authorized vs. what executed

### Step 3: Conditional Execution

```python
if policy_result.is_allowed:
    if request.action_type == "trade":
        execution_data = self._execute_trade(request)
```

Only ALLOWED trade actions trigger Alpaca API calls. The gate holds the credentials and makes the API call on behalf of the agent.

### Step 4: Result Return

```python
return ExecutionResult(
    allowed=policy_result.is_allowed,
    verdict=policy_result.verdict.value,
    policy_result=policy_result,
    execution_data=execution_data,
    error=error,
)
```

The agent receives the verdict, policy details, and execution data (if applicable). The agent **never** sees API credentials.

---

## Credential Isolation

### How It Works

```python
class EnforcementGate:
    def __init__(self, contract, ...):
        # Credentials stored as private attributes
        self._alpaca_api_key = os.getenv("ALPACA_API_KEY")
        self._alpaca_secret_key = os.getenv("ALPACA_SECRET_KEY")
        self._alpaca_base_url = os.getenv("ALPACA_BASE_URL")
        
        # Client initialized lazily
        self._alpaca_client = None
```

### Security Properties

| Property | Implementation |
|---|---|
| **Private storage** | Credentials stored as `_private` attributes |
| **No getter methods** | No public API exposes credentials |
| **Lazy initialization** | Client created only when needed |
| **Environment sourced** | Credentials loaded from env vars, never hardcoded |
| **Agent isolation** | Agents receive gate reference, never credentials |

### What Agents See

```python
# Agent code
class TraderAgent:
    def __init__(self, gate: EnforcementGate):
        self.gate = gate  # Reference to gate, NOT to API
    
    def submit_trade(self, ticker, side, quantity, price):
        request = ActionRequest(...)
        result = self.gate.process(request)  # Gate decides
        return result  # Agent gets result, never touches API
```

---

## Audit Log Integration

### Hash Chain

Each audit entry includes:
1. **Entry hash**: SHA-256 of the entry content
2. **Previous hash**: SHA-256 of the previous entry
3. **Sequence number**: Monotonically increasing counter

This creates a tamper-evident chain:

```
Entry 0: hash=abc123, prev=null,    seq=0
Entry 1: hash=def456, prev=abc123,  seq=1
Entry 2: hash=ghi789, prev=def456,  seq=2
```

If any entry is modified, its hash changes, breaking the chain for all subsequent entries.

### Verification

```python
def verify_chain(self) -> bool:
    for i, entry in enumerate(entries):
        # Verify entry hash
        if entry.compute_hash() != entry.entry_hash:
            return False  # Entry tampered
        
        # Verify chain link
        if i > 0 and entry.previous_hash != entries[i-1].entry_hash:
            return False  # Chain broken
        
        # Verify sequence
        if entry.sequence_number != i:
            return False  # Sequence gap
    
    return True  # Chain intact
```

---

## Execution Modes

### Dry Run (Default)

```python
gate = EnforcementGate(contract=contract, dry_run=True)
```

- All policy evaluation runs normally
- All audit logging runs normally
- Trade execution is **simulated** — no API calls
- Returns simulated execution data
- Ideal for demos and testing

### Paper Trading

```python
gate = EnforcementGate(
    contract=contract,
    dry_run=False,
    alpaca_api_key="...",
    alpaca_secret_key="...",
    alpaca_base_url="https://paper-api.alpaca.markets",
)
```

- Full policy evaluation and audit logging
- Actual API calls to Alpaca Paper Trading
- Real order submission with paper money
- No real financial risk

### Production (Future)

In a production deployment:
- `alpaca_base_url` would point to the live API
- Additional safety layers (human-in-the-loop, rate limiting) would be added
- Multi-signature contract approval would be required
- Real-time monitoring and alerting would be active

---

## System Integrity Verification

The gate provides a comprehensive integrity check:

```python
gate.verify_system_integrity()
# Returns:
{
    "contract_integrity": "✓ VALID",         # SHA-256 hash match
    "audit_chain_integrity": "✓ VALID",      # Hash chain intact
    "credentials_loaded": "✓ YES",           # API keys present
    "overall": "HEALTHY"                     # All checks pass
}
```

This should be called:
- At system startup
- Periodically during operation
- After any suspicious activity
- Before high-value operations

---

## Error Handling

| Error | Behavior |
|---|---|
| Contract integrity failure | BLOCK all operations, log critical alert |
| PolicyEngine exception | BLOCK the request, log the error |
| Alpaca API failure | Log the error, return error in ExecutionResult |
| Audit log write failure | Halt operation (fail-closed) |
| Missing credentials | Reject live execution, allow dry run |

---

## Performance Characteristics

| Operation | Expected Latency |
|---|---|
| Policy evaluation | < 1ms (pure computation) |
| Audit log write | < 5ms (file append) |
| Alpaca API call | 50-200ms (network) |
| Integrity verification | < 10ms (hash computation) |
| **Total gate processing** | **< 250ms per request** |

The gate adds minimal overhead to the execution path. Policy evaluation and audit logging are designed to be fast enough that they don't meaningfully delay legitimate operations.

---

## Comparison: With vs. Without GRID

| Aspect | Without GRID | With GRID |
|---|---|---|
| Agent → Execution | Direct API call | Gate-mediated, policy-checked |
| Credential access | Agent holds keys | Gate holds keys exclusively |
| Audit trail | Optional, post-hoc | Mandatory, pre-execution, hash-chained |
| Spending limits | Trust-based | Deterministically enforced |
| Unauthorized actions | Detected after damage | Blocked before execution |
| Prompt injection | Undetected | Pattern-matched and blocked |
| Agent escalation | Unconstrained | Bounded by immutable contract |
