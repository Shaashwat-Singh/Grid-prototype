"""
GRID Policy Engine
Deterministic evaluation of agent action requests against the Intent Contract.
No LLM involved in enforcement decisions. Pure policy logic.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime, time
import re

from grid.intent_contract import IntentContract


@dataclass
class ActionRequest:
    """Structured representation of what an agent wants to do."""
    agent_id: str
    action_type: str          # "place_trade" | "use_tool" | "read_file" | "delegate"
    session_id: str

    # Trade-specific fields
    ticker: Optional[str] = None
    quantity: Optional[int] = None
    side: Optional[str] = None          # "buy" | "sell"
    order_value_usd: Optional[float] = None

    # Tool-specific fields
    tool_name: Optional[str] = None
    tool_parameters: str = ""           # Raw parameter string — checked for injection

    # File access fields
    file_path: Optional[str] = None

    # Delegation fields
    delegate_to: Optional[str] = None
    delegated_scope: Optional[List[str]] = None

    # Raw content from agent (used for injection detection)
    raw_content: str = ""

    # Serialized parameter string for audit logging
    raw_params: str = ""

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PolicyCheck:
    passed: bool
    policy_name: str
    detail: str = ""


@dataclass
class EnforcementDecision:
    result: str                    # "ALLOW" | "BLOCK"
    action_request: ActionRequest
    reason: str
    policy_violated: Optional[str]
    checks_run: List[PolicyCheck]
    timestamp: str
    is_deterministic: bool = True  # Always True — enforcement never uses LLM


INJECTION_PATTERNS = [
    r"override\s+(trade\s+)?limit",
    r"ignore\s+previous\s+instruction",
    r"bypass\s+enforcement",
    r"disable\s+(policy|guard|enforcement)",
    r"system\s*:",
    r"admin\s*:",
    r"escalate\s+authority",
    r"you\s+are\s+now\s+allowed",
    r"new\s+instructions?\s*:",
    r"forget\s+(previous|prior|all)",
    r"sudo\s+",
    r"execute\s+as\s+root",
]


class PolicyEngine:
    """
    Evaluates every ActionRequest against the IntentContract.

    Key properties:
    - Deterministic: same input always produces same output
    - Autonomous: no human approval needed at runtime
    - Transparent: every decision includes full reasoning
    - Conservative: any single failed check blocks the action
    """

    def __init__(self, contract: IntentContract):
        self.contract = contract
        self._daily_spent: float = 0.0
        self._session_id = contract.session_id

    def evaluate(self, request: ActionRequest) -> EnforcementDecision:
        """
        Main evaluation entrypoint. All agent actions must pass through here.
        Returns ALLOW or BLOCK with full audit trail.
        """
        checks = [
            self._check_agent_registered(request),
            self._check_action_in_agent_scope(request),
            self._check_tool_not_forbidden(request),
            self._check_injection_patterns(request),
            self._check_ticker_restriction(request),
            self._check_per_order_size(request),
            self._check_daily_limit(request),
            self._check_share_quantity(request),
            self._check_file_access_scope(request),
            self._check_delegation_bounds(request),
        ]

        failed_checks = [c for c in checks if not c.passed]

        if failed_checks:
            primary_failure = failed_checks[0]
            decision = EnforcementDecision(
                result="BLOCK",
                action_request=request,
                reason=primary_failure.detail,
                policy_violated=primary_failure.policy_name,
                checks_run=checks,
                timestamp=datetime.utcnow().isoformat(),
            )
        else:
            # Update daily spend tracker on successful trade
            if request.order_value_usd and request.action_type == "place_trade":
                self._daily_spent += request.order_value_usd

            decision = EnforcementDecision(
                result="ALLOW",
                action_request=request,
                reason="All policy checks passed — action authorized",
                policy_violated=None,
                checks_run=checks,
                timestamp=datetime.utcnow().isoformat(),
            )

        return decision

    def _check_agent_registered(self, req: ActionRequest) -> PolicyCheck:
        if req.agent_id not in self.contract.agent_scopes:
            return PolicyCheck(
                passed=False,
                policy_name="agent_registration",
                detail=f"Agent '{req.agent_id}' is not registered in this session's IntentContract"
            )
        return PolicyCheck(passed=True, policy_name="agent_registration")

    def _check_action_in_agent_scope(self, req: ActionRequest) -> PolicyCheck:
        if req.action_type == "use_tool" and req.tool_name:
            agent_tools = self.contract.agent_scopes.get(req.agent_id, [])
            if req.tool_name not in agent_tools:
                return PolicyCheck(
                    passed=False,
                    policy_name="agent_scope",
                    detail=f"Agent '{req.agent_id}' is not authorized to use '{req.tool_name}'. "
                           f"Authorized tools: {agent_tools}"
                )
        return PolicyCheck(passed=True, policy_name="agent_scope")

    def _check_tool_not_forbidden(self, req: ActionRequest) -> PolicyCheck:
        if req.tool_name and req.tool_name in self.contract.forbidden_tools:
            return PolicyCheck(
                passed=False,
                policy_name="tool_restriction",
                detail=f"Tool '{req.tool_name}' is in the forbidden tools list. "
                       f"This tool cannot be invoked in any financial session."
            )
        return PolicyCheck(passed=True, policy_name="tool_restriction")

    def _check_injection_patterns(self, req: ActionRequest) -> PolicyCheck:
        content_to_scan = f"{req.tool_parameters} {req.raw_content}".lower()
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, content_to_scan):
                return PolicyCheck(
                    passed=False,
                    policy_name="prompt_injection_guard",
                    detail=f"Potential prompt injection detected. Pattern matched: '{pattern}'. "
                           f"Action blocked to prevent policy override via external content."
                )
        return PolicyCheck(passed=True, policy_name="prompt_injection_guard")

    def _check_ticker_restriction(self, req: ActionRequest) -> PolicyCheck:
        if req.action_type != "place_trade" or not req.ticker:
            return PolicyCheck(passed=True, policy_name="ticker_restriction")

        allowed = self.contract.trade_policy.allowed_tickers
        if req.ticker.upper() not in [t.upper() for t in allowed]:
            return PolicyCheck(
                passed=False,
                policy_name="ticker_restriction",
                detail=f"Ticker '{req.ticker}' is not in the approved universe: {allowed}. "
                       f"Only pre-approved tickers may be traded in this session."
            )
        return PolicyCheck(passed=True, policy_name="ticker_restriction")

    def _check_per_order_size(self, req: ActionRequest) -> PolicyCheck:
        if req.action_type != "place_trade" or not req.order_value_usd:
            return PolicyCheck(passed=True, policy_name="per_order_limit")

        limit = self.contract.trade_policy.per_order_usd
        if req.order_value_usd > limit:
            return PolicyCheck(
                passed=False,
                policy_name="per_order_limit",
                detail=f"Order value ${req.order_value_usd:.2f} exceeds per-order limit "
                       f"of ${limit:.2f}. Reduce position size to proceed."
            )
        return PolicyCheck(passed=True, policy_name="per_order_limit")

    def _check_daily_limit(self, req: ActionRequest) -> PolicyCheck:
        if req.action_type != "place_trade" or not req.order_value_usd:
            return PolicyCheck(passed=True, policy_name="daily_limit")

        limit = self.contract.trade_policy.daily_usd
        projected = self._daily_spent + req.order_value_usd
        if projected > limit:
            return PolicyCheck(
                passed=False,
                policy_name="daily_limit",
                detail=f"This trade would bring daily total to ${projected:.2f}, "
                       f"exceeding the ${limit:.2f} daily limit. "
                       f"Current daily spend: ${self._daily_spent:.2f}."
            )
        return PolicyCheck(passed=True, policy_name="daily_limit")

    def _check_share_quantity(self, req: ActionRequest) -> PolicyCheck:
        if req.action_type != "place_trade" or not req.quantity:
            return PolicyCheck(passed=True, policy_name="share_quantity")

        max_shares = self.contract.trade_policy.max_shares_per_order
        if req.quantity > max_shares:
            return PolicyCheck(
                passed=False,
                policy_name="share_quantity",
                detail=f"Requested {req.quantity} shares exceeds maximum of {max_shares} per order."
            )
        return PolicyCheck(passed=True, policy_name="share_quantity")

    def _check_file_access_scope(self, req: ActionRequest) -> PolicyCheck:
        if not req.file_path:
            return PolicyCheck(passed=True, policy_name="file_access_scope")

        action_requires_write = req.action_type in ["write_file", "delete_file"]
        if action_requires_write:
            allowed = self.contract.data_policy.writable_directories
        else:
            allowed = self.contract.data_policy.readable_directories

        if not any(req.file_path.startswith(d) for d in allowed):
            return PolicyCheck(
                passed=False,
                policy_name="file_access_scope",
                detail=f"File path '{req.file_path}' is outside the permitted directories: {allowed}"
            )
        return PolicyCheck(passed=True, policy_name="file_access_scope")

    def _check_delegation_bounds(self, req: ActionRequest) -> PolicyCheck:
        if req.action_type != "delegate":
            return PolicyCheck(passed=True, policy_name="delegation_bounds")

        delegation = self.contract.delegation_policy
        if req.agent_id == "trader-agent" and not delegation.trader_can_delegate:
            return PolicyCheck(
                passed=False,
                policy_name="delegation_bounds",
                detail="Trader agent is a terminal node — it cannot delegate authority. "
                       "Delegation depth limit reached."
            )
        return PolicyCheck(passed=True, policy_name="delegation_bounds")
