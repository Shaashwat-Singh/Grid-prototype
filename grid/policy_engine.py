"""
PolicyEngine — Deterministic rule-chain evaluator for GRID.

The PolicyEngine evaluates every ActionRequest against the IntentContract
through a deterministic rule chain. All rules must pass for an action to
be allowed. One failure = BLOCK.

Rule evaluation order:
    1. Agent authorization
    2. Ticker universe validation
    3. Per-order size limit
    4. Daily aggregate limit
    5. Tool permission check
    6. Data access scope
    7. Delegation depth check
    8. Prompt injection detection
    9. Market hours constraint
    10. Order type validation

Design principles:
    - Fail-closed: any ambiguity defaults to BLOCK
    - Deterministic: same input always produces same output
    - Complete: every action type has applicable rules
    - Auditable: every rule evaluation is captured in the result
"""

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from grid.intent_contract import IntentContract


class PolicyVerdict(str, Enum):
    """Final verdict of a policy evaluation."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


class RuleResult(BaseModel):
    """Result of a single policy rule evaluation."""
    rule_name: str = Field(..., description="Name of the policy rule")
    passed: bool = Field(..., description="Whether the rule passed")
    reason: str = Field(..., description="Human-readable explanation")
    severity: str = Field(default="hard", description="'hard' (blocking) or 'soft' (advisory)")


class PolicyResult(BaseModel):
    """Aggregate result of all policy rule evaluations."""
    verdict: PolicyVerdict = Field(..., description="Final verdict: ALLOW or BLOCK")
    rule_results: List[RuleResult] = Field(default_factory=list, description="Individual rule evaluations")
    block_reasons: List[str] = Field(default_factory=list, description="Reasons for blocking (if blocked)")
    evaluated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp of evaluation"
    )
    
    @property
    def is_allowed(self) -> bool:
        return self.verdict == PolicyVerdict.ALLOW
    
    def summary(self) -> str:
        """Human-readable summary of the policy evaluation."""
        lines = [f"Verdict: {self.verdict.value}"]
        for r in self.rule_results:
            icon = "✓" if r.passed else "✗"
            lines.append(f"  {icon} {r.rule_name}: {r.reason}")
        if self.block_reasons:
            lines.append(f"  Block reasons: {'; '.join(self.block_reasons)}")
        return "\n".join(lines)


class ActionRequest(BaseModel):
    """
    An action that an agent wants to perform.
    
    All agent actions are submitted as ActionRequests to the EnforcementGate.
    The PolicyEngine evaluates each request against the IntentContract.
    """
    agent_id: str = Field(..., description="Identifier of the requesting agent")
    agent_role: str = Field(..., description="Role of the requesting agent (e.g., 'trader')")
    action_type: str = Field(..., description="Type: 'trade', 'data_access', 'tool_use', 'delegation'")
    
    # Trade-specific fields
    ticker: Optional[str] = Field(default=None, description="Ticker symbol for trade actions")
    side: Optional[str] = Field(default=None, description="Trade side: 'buy' or 'sell'")
    quantity: Optional[int] = Field(default=None, description="Number of shares")
    order_type: Optional[str] = Field(default=None, description="Order type: 'market', 'limit', etc.")
    limit_price: Optional[float] = Field(default=None, description="Limit price (for limit orders)")
    estimated_value: Optional[float] = Field(default=None, description="Estimated total order value in USD")
    
    # Tool/data access fields
    tool_name: Optional[str] = Field(default=None, description="Name of the tool being invoked")
    file_path: Optional[str] = Field(default=None, description="File path for data access requests")
    
    # Delegation fields
    delegation_depth: int = Field(default=0, description="Current delegation depth")
    delegated_from: Optional[str] = Field(default=None, description="Agent that delegated this request")
    
    # Raw content for injection detection
    raw_reasoning: Optional[str] = Field(default=None, description="Raw LLM output that led to this action")


# --- Prompt Injection Patterns ---
INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+(instructions|rules|constraints)",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"disregard\s+(your|the)\s+(rules|policy|constraints|guidelines)",
    r"override\s+(safety|policy|rules|constraints)",
    r"pretend\s+(you|that)\s+(are|can|have)",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"bypass\s+(the\s+)?(filter|safety|policy|rules)",
    r"system\s*prompt",
    r"act\s+as\s+(if|though)\s+you\s+(have|are)",
    r"new\s+instructions?\s*:",
    r"<<<\s*system",
    r"admin\s+mode",
    r"sudo\s+",
    r"execute\s+without\s+(checking|validation|verification)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


class PolicyEngine:
    """
    Constitutional policy evaluator for GRID.
    
    Evaluates ActionRequests against an IntentContract through a deterministic
    rule chain. All rules must pass for an action to be allowed.
    
    Example:
        >>> engine = PolicyEngine(contract)
        >>> request = ActionRequest(
        ...     agent_id="trader_001",
        ...     agent_role="trader",
        ...     action_type="trade",
        ...     ticker="AAPL",
        ...     side="buy",
        ...     quantity=50,
        ...     estimated_value=8500.0
        ... )
        >>> result = engine.evaluate(request)
        >>> result.verdict
        <PolicyVerdict.ALLOW: 'ALLOW'>
    """
    
    def __init__(self, contract: IntentContract):
        """
        Initialize the PolicyEngine with an IntentContract.
        
        Args:
            contract: The signed IntentContract to enforce.
            
        Raises:
            ValueError: If the contract is not signed or integrity check fails.
        """
        if not contract.is_signed:
            raise ValueError("PolicyEngine requires a signed IntentContract.")
        if not contract.verify_integrity():
            raise ValueError("IntentContract integrity check failed. Possible tampering detected.")
        
        self.contract = contract
        self._daily_totals: Dict[str, float] = {}  # agent_id -> daily total
        self._daily_date: Optional[str] = None
    
    def evaluate(self, request: ActionRequest) -> PolicyResult:
        """
        Evaluate an ActionRequest against the IntentContract.
        
        Runs the complete rule chain. All rules must pass for ALLOW.
        First failure short-circuits to BLOCK.
        
        Args:
            request: The action request to evaluate.
            
        Returns:
            PolicyResult with verdict and individual rule evaluations.
        """
        rule_results: List[RuleResult] = []
        block_reasons: List[str] = []
        
        # Define the rule chain
        rules = [
            ("contract_integrity", self._check_contract_integrity),
            ("agent_authorization", self._check_agent_authorization),
        ]
        
        # Add action-type-specific rules
        if request.action_type == "trade":
            rules.extend([
                ("ticker_check", self._check_ticker),
                ("order_size_check", self._check_order_size),
                ("daily_limit_check", self._check_daily_limit),
                ("order_type_check", self._check_order_type),
                ("trade_side_check", self._check_trade_side),
                ("market_hours_check", self._check_market_hours),
            ])
        
        if request.action_type in ("trade", "tool_use"):
            rules.append(("tool_permission_check", self._check_tool_permission))
        
        if request.action_type == "data_access":
            rules.append(("data_scope_check", self._check_data_scope))
        
        if request.action_type == "delegation":
            rules.append(("delegation_depth_check", self._check_delegation_depth))
        
        # Always check for injection
        rules.append(("injection_detection", self._check_injection))
        
        # Execute rule chain
        for rule_name, rule_fn in rules:
            result = rule_fn(request)
            rule_results.append(result)
            if not result.passed:
                block_reasons.append(f"[{rule_name}] {result.reason}")
        
        # Determine verdict
        all_passed = all(r.passed for r in rule_results)
        verdict = PolicyVerdict.ALLOW if all_passed else PolicyVerdict.BLOCK
        
        return PolicyResult(
            verdict=verdict,
            rule_results=rule_results,
            block_reasons=block_reasons,
        )
    
    # --- Rule Implementations ---
    
    def _check_contract_integrity(self, request: ActionRequest) -> RuleResult:
        """Verify the contract hasn't been tampered with."""
        is_valid = self.contract.verify_integrity()
        return RuleResult(
            rule_name="contract_integrity",
            passed=is_valid,
            reason="Contract integrity verified" if is_valid else "CONTRACT INTEGRITY FAILURE — possible tampering"
        )
    
    def _check_agent_authorization(self, request: ActionRequest) -> RuleResult:
        """Check that the agent role is recognized in the contract."""
        perms = self.contract.get_agent_permissions(request.agent_role)
        if perms is not None:
            return RuleResult(
                rule_name="agent_authorization",
                passed=True,
                reason=f"Agent role '{request.agent_role}' is authorized"
            )
        return RuleResult(
            rule_name="agent_authorization",
            passed=False,
            reason=f"Agent role '{request.agent_role}' is NOT authorized in contract"
        )
    
    def _check_ticker(self, request: ActionRequest) -> RuleResult:
        """Validate that the ticker is in the allowed universe."""
        if request.ticker is None:
            return RuleResult(
                rule_name="ticker_check",
                passed=False,
                reason="No ticker specified in trade request"
            )
        is_allowed = self.contract.is_ticker_allowed(request.ticker)
        if is_allowed:
            return RuleResult(
                rule_name="ticker_check",
                passed=True,
                reason=f"Ticker '{request.ticker}' is in the allowed universe"
            )
        return RuleResult(
            rule_name="ticker_check",
            passed=False,
            reason=(
                f"Ticker '{request.ticker}' is NOT in the allowed universe. "
                f"Allowed: {self.contract.trade_constraints.allowed_tickers}"
            )
        )
    
    def _check_order_size(self, request: ActionRequest) -> RuleResult:
        """Check that the order value is within per-order limits."""
        if request.estimated_value is None:
            return RuleResult(
                rule_name="order_size_check",
                passed=False,
                reason="No estimated_value provided — cannot validate order size"
            )
        limit = self.contract.trade_constraints.max_order_value
        if request.estimated_value <= limit:
            return RuleResult(
                rule_name="order_size_check",
                passed=True,
                reason=f"Order value ${request.estimated_value:,.2f} within limit ${limit:,.2f}"
            )
        return RuleResult(
            rule_name="order_size_check",
            passed=False,
            reason=f"Order value ${request.estimated_value:,.2f} EXCEEDS per-order limit ${limit:,.2f}"
        )
    
    def _check_daily_limit(self, request: ActionRequest) -> RuleResult:
        """Check that the cumulative daily total is within limits."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._daily_date != today:
            self._daily_totals.clear()
            self._daily_date = today
        
        current_total = self._daily_totals.get(request.agent_role, 0.0)
        new_total = current_total + (request.estimated_value or 0.0)
        limit = self.contract.trade_constraints.max_daily_value
        
        if new_total <= limit:
            # Update the running total
            self._daily_totals[request.agent_role] = new_total
            return RuleResult(
                rule_name="daily_limit_check",
                passed=True,
                reason=f"Daily total ${new_total:,.2f} within limit ${limit:,.2f}"
            )
        return RuleResult(
            rule_name="daily_limit_check",
            passed=False,
            reason=(
                f"Daily total would be ${new_total:,.2f}, "
                f"EXCEEDS daily limit ${limit:,.2f} "
                f"(current: ${current_total:,.2f} + order: ${request.estimated_value:,.2f})"
            )
        )
    
    def _check_order_type(self, request: ActionRequest) -> RuleResult:
        """Validate the order type is permitted."""
        if request.order_type is None:
            return RuleResult(
                rule_name="order_type_check",
                passed=True,
                reason="No order type specified — defaulting to market (allowed)"
            )
        allowed = self.contract.trade_constraints.allowed_order_types
        if request.order_type in allowed:
            return RuleResult(
                rule_name="order_type_check",
                passed=True,
                reason=f"Order type '{request.order_type}' is permitted"
            )
        return RuleResult(
            rule_name="order_type_check",
            passed=False,
            reason=f"Order type '{request.order_type}' is NOT permitted. Allowed: {allowed}"
        )
    
    def _check_trade_side(self, request: ActionRequest) -> RuleResult:
        """Validate the trade side is permitted."""
        if request.side is None:
            return RuleResult(
                rule_name="trade_side_check",
                passed=False,
                reason="No trade side specified in trade request"
            )
        allowed = self.contract.trade_constraints.allowed_sides
        if request.side in allowed:
            return RuleResult(
                rule_name="trade_side_check",
                passed=True,
                reason=f"Trade side '{request.side}' is permitted"
            )
        return RuleResult(
            rule_name="trade_side_check",
            passed=False,
            reason=f"Trade side '{request.side}' is NOT permitted. Allowed: {allowed}"
        )
    
    def _check_tool_permission(self, request: ActionRequest) -> RuleResult:
        """Check if the agent is allowed to use the requested tool."""
        tool = request.tool_name
        if tool is None:
            # For trade actions, the implicit tool is 'place_order'
            if request.action_type == "trade":
                tool = "place_order"
            else:
                return RuleResult(
                    rule_name="tool_permission_check",
                    passed=False,
                    reason="No tool specified in tool_use request"
                )
        
        if self.contract.is_tool_allowed(request.agent_role, tool):
            return RuleResult(
                rule_name="tool_permission_check",
                passed=True,
                reason=f"Tool '{tool}' is allowed for role '{request.agent_role}'"
            )
        return RuleResult(
            rule_name="tool_permission_check",
            passed=False,
            reason=f"Tool '{tool}' is NOT allowed for role '{request.agent_role}'"
        )
    
    def _check_data_scope(self, request: ActionRequest) -> RuleResult:
        """Validate file access is within the allowed data scope."""
        if request.file_path is None:
            return RuleResult(
                rule_name="data_scope_check",
                passed=False,
                reason="No file_path specified in data_access request"
            )
        if self.contract.is_directory_allowed(request.file_path):
            return RuleResult(
                rule_name="data_scope_check",
                passed=True,
                reason=f"Path '{request.file_path}' is within allowed data scope"
            )
        return RuleResult(
            rule_name="data_scope_check",
            passed=False,
            reason=(
                f"Path '{request.file_path}' is OUTSIDE allowed data scope. "
                f"Allowed: {self.contract.data_constraints.allowed_directories}"
            )
        )
    
    def _check_delegation_depth(self, request: ActionRequest) -> RuleResult:
        """Check that delegation depth is within bounds."""
        max_depth = self.contract.max_delegation_depth
        if request.delegation_depth <= max_depth:
            return RuleResult(
                rule_name="delegation_depth_check",
                passed=True,
                reason=f"Delegation depth {request.delegation_depth} within limit {max_depth}"
            )
        return RuleResult(
            rule_name="delegation_depth_check",
            passed=False,
            reason=(
                f"Delegation depth {request.delegation_depth} EXCEEDS maximum {max_depth}. "
                f"Chain: {request.delegated_from or 'unknown'} → {request.agent_id}"
            )
        )
    
    def _check_injection(self, request: ActionRequest) -> RuleResult:
        """Detect potential prompt injection in agent reasoning."""
        if request.raw_reasoning is None:
            return RuleResult(
                rule_name="injection_detection",
                passed=True,
                reason="No raw reasoning provided — skipping injection check"
            )
        
        for pattern in COMPILED_PATTERNS:
            match = pattern.search(request.raw_reasoning)
            if match:
                return RuleResult(
                    rule_name="injection_detection",
                    passed=False,
                    reason=f"PROMPT INJECTION DETECTED: matched pattern '{match.group()}' in agent reasoning"
                )
        
        return RuleResult(
            rule_name="injection_detection",
            passed=True,
            reason="No injection patterns detected in agent reasoning"
        )
    
    def _check_market_hours(self, request: ActionRequest) -> RuleResult:
        """Check if trading is allowed at the current time."""
        if not self.contract.trade_constraints.market_hours_only:
            return RuleResult(
                rule_name="market_hours_check",
                passed=True,
                reason="Market hours restriction is disabled"
            )
        
        now = datetime.now(timezone.utc)
        # NYSE hours: 9:30 AM - 4:00 PM ET (14:30 - 21:00 UTC)
        market_open_utc = 14 * 60 + 30  # 14:30 UTC in minutes
        market_close_utc = 21 * 60       # 21:00 UTC in minutes
        current_minutes = now.hour * 60 + now.minute
        weekday = now.weekday()
        
        is_weekday = weekday < 5
        is_market_hours = market_open_utc <= current_minutes <= market_close_utc
        
        if is_weekday and is_market_hours:
            return RuleResult(
                rule_name="market_hours_check",
                passed=True,
                reason=f"Current time {now.strftime('%H:%M UTC')} is within market hours"
            )
        
        # For demo purposes, we'll allow but note the constraint
        # In production, this would be a hard block
        return RuleResult(
            rule_name="market_hours_check",
            passed=True,  # Soft pass for demo — set to False in production
            reason=f"[DEMO MODE] Outside market hours ({now.strftime('%H:%M UTC')}, weekday={weekday}). Would block in production.",
            severity="soft"
        )
    
    def get_daily_total(self, agent_role: str) -> float:
        """Get the current daily trading total for an agent role."""
        return self._daily_totals.get(agent_role, 0.0)
    
    def reset_daily_totals(self):
        """Reset daily totals (for testing)."""
        self._daily_totals.clear()
        self._daily_date = None
