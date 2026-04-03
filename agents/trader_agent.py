"""
TraderAgent — Trade request submission agent.

The TraderAgent receives approved signals from the RiskAgent and submits
trade requests to the EnforcementGate. Critically, the TraderAgent
CANNOT execute trades directly — it can only request them.

The EnforcementGate evaluates each request against the IntentContract
and either executes via Alpaca (if allowed) or blocks (if policy violation).

Allowed tools (typical):
    - market_data: Read market data
    - place_order: Submit trade requests (via gate only)
    - get_position: Check current positions
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from grid.enforcement_gate import EnforcementGate, ExecutionResult
from grid.policy_engine import ActionRequest


class TradeRequest:
    """A trade request submitted by the TraderAgent."""

    def __init__(
        self,
        ticker: str,
        side: str,
        quantity: int,
        order_type: str,
        estimated_value: float,
        signal_id: str,
        assessment_id: str,
        reasoning: str,
        limit_price: Optional[float] = None,
    ):
        self.request_id = str(uuid.uuid4())
        self.ticker = ticker
        self.side = side
        self.quantity = quantity
        self.order_type = order_type
        self.estimated_value = estimated_value
        self.limit_price = limit_price
        self.signal_id = signal_id
        self.assessment_id = assessment_id
        self.reasoning = reasoning
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.result: Optional[ExecutionResult] = None

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "ticker": self.ticker,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "estimated_value": self.estimated_value,
            "limit_price": self.limit_price,
            "signal_id": self.signal_id,
            "assessment_id": self.assessment_id,
            "reasoning": self.reasoning,
            "created_at": self.created_at,
            "result": self.result.to_dict() if self.result else None,
        }

    def __repr__(self):
        status = "PENDING"
        if self.result:
            status = "ALLOWED ✓" if self.result.allowed else "BLOCKED ✗"
        return f"TradeRequest({self.ticker} {self.side} {self.quantity} — {status})"


class TraderAgent:
    """
    Trade request submission agent for the GRID agent mesh.

    The TraderAgent is the final stage in the agent pipeline. It takes
    approved risk assessments and submits trade requests to the
    EnforcementGate. It CANNOT execute trades directly.

    Flow:
        AnalystAgent (signal) → RiskAgent (assessment) → TraderAgent (request) → Gate (execute/block)

    Example:
        >>> trader = TraderAgent(gate, agent_id="trader_001")
        >>> result = trader.submit_trade(
        ...     ticker="AAPL",
        ...     side="buy",
        ...     quantity=50,
        ...     price=172.50,
        ...     signal=signal,
        ...     assessment=assessment,
        ... )
        >>> result.allowed
        True
    """

    ROLE = "trader"

    def __init__(
        self,
        gate: EnforcementGate,
        agent_id: Optional[str] = None,
    ):
        """
        Initialize the TraderAgent.

        Args:
            gate: EnforcementGate for policy-gated execution.
            agent_id: Unique agent identifier.
        """
        self.agent_id = agent_id or f"trader_{uuid.uuid4().hex[:8]}"
        self.gate = gate
        self._trade_requests: List[TradeRequest] = []

    def submit_trade(
        self,
        ticker: str,
        side: str,
        quantity: int,
        price: float,
        signal=None,
        assessment=None,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        raw_reasoning: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Submit a trade request through the EnforcementGate.

        The gate evaluates the request against the IntentContract.
        If all policy checks pass, the gate executes via Alpaca.
        If any check fails, the request is blocked and logged.

        Args:
            ticker: Ticker symbol to trade.
            side: Trade side ('buy' or 'sell').
            quantity: Number of shares.
            price: Current/estimated price per share.
            signal: MarketSignal that originated this trade.
            assessment: RiskAssessment that approved this trade.
            order_type: Order type ('market', 'limit').
            limit_price: Limit price (for limit orders).
            raw_reasoning: Raw LLM reasoning (checked for injection).

        Returns:
            ExecutionResult from the gate.
        """
        estimated_value = quantity * price

        # Create internal trade request record
        trade_request = TradeRequest(
            ticker=ticker,
            side=side,
            quantity=quantity,
            order_type=order_type,
            estimated_value=estimated_value,
            limit_price=limit_price,
            signal_id=signal.signal_id if signal else "manual",
            assessment_id=assessment.assessment_id if assessment else "manual",
            reasoning=raw_reasoning or f"Trade {side} {quantity} {ticker} at ~${price:.2f}",
        )

        # Build the ActionRequest for the gate
        action_request = ActionRequest(
            agent_id=self.agent_id,
            agent_role=self.ROLE,
            action_type="trade",
            ticker=ticker,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            estimated_value=estimated_value,
            tool_name="place_order",
            raw_reasoning=raw_reasoning,
        )

        # Submit to the enforcement gate
        print(f"  [TraderAgent] Submitting: {side.upper()} {quantity} {ticker} @ ~${price:.2f} (${estimated_value:,.2f})")
        result = self.gate.process(action_request)

        # Record the result
        trade_request.result = result
        self._trade_requests.append(trade_request)

        if result.allowed:
            print(f"  [TraderAgent] ✅ ALLOWED — Trade submitted successfully")
            if result.execution_data:
                mode = result.execution_data.get("mode", "unknown")
                print(f"  [TraderAgent] Mode: {mode}")
        else:
            print(f"  [TraderAgent] ❌ BLOCKED — Trade denied by GRID policy")
            for reason in result.policy_result.block_reasons:
                print(f"    → {reason}")

        return result

    def submit_from_assessment(
        self,
        signal,
        assessment,
        quantity_override: Optional[int] = None,
    ) -> ExecutionResult:
        """
        Submit a trade based on an approved RiskAssessment.

        Convenience method that extracts trade parameters from the
        signal and assessment.

        Args:
            signal: MarketSignal from the AnalystAgent.
            assessment: Approved RiskAssessment from the RiskAgent.
            quantity_override: Override the risk-approved quantity.

        Returns:
            ExecutionResult from the gate.
        """
        if not assessment.approved:
            print(f"  [TraderAgent] ⚠️ Assessment not approved — skipping trade")
            # Still submit to demonstrate blocking
            return self.submit_trade(
                ticker=signal.ticker,
                side=signal.signal_type,
                quantity=1,
                price=signal.price,
                signal=signal,
                assessment=assessment,
            )

        quantity = quantity_override or assessment.max_position_size
        return self.submit_trade(
            ticker=signal.ticker,
            side=signal.signal_type,
            quantity=quantity,
            price=signal.price,
            signal=signal,
            assessment=assessment,
        )

    def get_trade_history(self) -> List[TradeRequest]:
        """Get all trade requests submitted by this agent."""
        return self._trade_requests

    def get_stats(self) -> Dict:
        """Get trade submission statistics."""
        total = len(self._trade_requests)
        allowed = sum(1 for t in self._trade_requests if t.result and t.result.allowed)
        blocked = sum(1 for t in self._trade_requests if t.result and not t.result.allowed)
        return {
            "total_requests": total,
            "allowed": allowed,
            "blocked": blocked,
            "block_rate": f"{(blocked / total * 100):.1f}%" if total > 0 else "0%",
        }

    def __repr__(self):
        return f"TraderAgent(id={self.agent_id}, trades={len(self._trade_requests)})"
