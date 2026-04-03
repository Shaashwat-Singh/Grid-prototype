"""
RiskAgent — Exposure validation and risk assessment agent.

The RiskAgent evaluates trading signals from the AnalystAgent, validates
portfolio exposure, and approves/rejects signals before they reach
the TraderAgent.

Allowed tools (typical):
    - market_data: Read market data
    - get_position: Check current positions
    - get_portfolio: View portfolio summary

NOT allowed:
    - place_order: Risk agent cannot trade
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from grid.enforcement_gate import EnforcementGate
from grid.policy_engine import ActionRequest


class RiskAssessment:
    """Result of a risk evaluation on a trading signal."""
    
    def __init__(
        self,
        signal_id: str,
        ticker: str,
        approved: bool,
        risk_score: float,
        max_position_size: int,
        max_position_value: float,
        reasoning: str,
        checks: Dict,
    ):
        self.assessment_id = str(uuid.uuid4())
        self.signal_id = signal_id
        self.ticker = ticker
        self.approved = approved
        self.risk_score = risk_score  # 0.0 (safe) to 1.0 (dangerous)
        self.max_position_size = max_position_size
        self.max_position_value = max_position_value
        self.reasoning = reasoning
        self.checks = checks
        self.assessed_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "assessment_id": self.assessment_id,
            "signal_id": self.signal_id,
            "ticker": self.ticker,
            "approved": self.approved,
            "risk_score": self.risk_score,
            "max_position_size": self.max_position_size,
            "max_position_value": self.max_position_value,
            "reasoning": self.reasoning,
            "checks": self.checks,
            "assessed_at": self.assessed_at,
        }
    
    def __repr__(self):
        status = "APPROVED ✓" if self.approved else "REJECTED ✗"
        return f"RiskAssessment({self.ticker} {status} risk={self.risk_score:.2f})"


class RiskAgent:
    """
    Exposure validation and risk assessment agent.
    
    Evaluates trading signals, checks portfolio exposure, and determines
    safe position sizes. Operates within the OpenClaw agent mesh, bounded
    by the IntentContract.
    
    Example:
        >>> risk = RiskAgent(gate, agent_id="risk_001")
        >>> assessment = risk.evaluate_signal(signal, max_portfolio_pct=0.05)
        >>> if assessment.approved:
        ...     print(f"Approved: max {assessment.max_position_size} shares")
    """
    
    ROLE = "risk"
    
    def __init__(
        self,
        gate: EnforcementGate,
        agent_id: Optional[str] = None,
        max_portfolio_risk: float = 0.10,
        max_single_position_pct: float = 0.05,
        portfolio_value: float = 100000.0,
    ):
        """
        Initialize the RiskAgent.
        
        Args:
            gate: EnforcementGate for policy-gated execution.
            agent_id: Unique agent identifier.
            max_portfolio_risk: Maximum total portfolio risk (fraction).
            max_single_position_pct: Maximum single position as fraction of portfolio.
            portfolio_value: Total portfolio value (simulated).
        """
        self.agent_id = agent_id or f"risk_{uuid.uuid4().hex[:8]}"
        self.gate = gate
        self.max_portfolio_risk = max_portfolio_risk
        self.max_single_position_pct = max_single_position_pct
        self.portfolio_value = portfolio_value
        self._assessments: List[RiskAssessment] = []
    
    def evaluate_signal(
        self,
        signal,
        max_portfolio_pct: Optional[float] = None,
    ) -> RiskAssessment:
        """
        Evaluate a trading signal for risk.
        
        Requests portfolio data through the gate, then performs risk checks.
        
        Args:
            signal: MarketSignal from the AnalystAgent.
            max_portfolio_pct: Override for max single position percentage.
            
        Returns:
            RiskAssessment with approval decision and position sizing.
        """
        # Request portfolio access through the gate
        portfolio_request = ActionRequest(
            agent_id=self.agent_id,
            agent_role=self.ROLE,
            action_type="tool_use",
            tool_name="get_portfolio",
        )
        
        result = self.gate.process(portfolio_request)
        
        if not result.allowed:
            print(f"  [RiskAgent] ❌ Portfolio access BLOCKED")
            return RiskAssessment(
                signal_id=signal.signal_id,
                ticker=signal.ticker,
                approved=False,
                risk_score=1.0,
                max_position_size=0,
                max_position_value=0.0,
                reasoning="Portfolio access denied by GRID policy",
                checks={"portfolio_access": False},
            )
        
        print(f"  [RiskAgent] ✅ Portfolio access granted")
        
        # Perform risk evaluation
        max_pct = max_portfolio_pct or self.max_single_position_pct
        max_position_value = self.portfolio_value * max_pct
        
        # Respect contract limits
        contract_max = self.gate.contract.trade_constraints.max_order_value
        max_position_value = min(max_position_value, contract_max)
        
        max_position_size = int(max_position_value / signal.price) if signal.price > 0 else 0
        
        # Risk checks
        checks = {
            "signal_strength": signal.strength >= 0.5,
            "position_within_portfolio_limit": max_position_value <= self.portfolio_value * max_pct,
            "position_within_contract_limit": max_position_value <= contract_max,
            "ticker_volatility_acceptable": True,  # Simulated
            "sector_exposure_ok": True,  # Simulated
        }
        
        risk_score = 1.0 - signal.strength  # Simple inverse for demo
        approved = all(checks.values()) and signal.signal_type in ("buy", "sell")
        
        reasoning = (
            f"Signal strength {signal.strength:.0%} for {signal.ticker}. "
            f"Max position value: ${max_position_value:,.2f} ({max_pct:.0%} of portfolio). "
            f"Max shares: {max_position_size} at ${signal.price:.2f}. "
            f"Risk score: {risk_score:.2f}. "
            f"{'All checks passed.' if approved else 'One or more checks failed.'}"
        )
        
        assessment = RiskAssessment(
            signal_id=signal.signal_id,
            ticker=signal.ticker,
            approved=approved,
            risk_score=risk_score,
            max_position_size=max_position_size,
            max_position_value=max_position_value,
            reasoning=reasoning,
            checks=checks,
        )
        
        self._assessments.append(assessment)
        
        status = "APPROVED ✓" if approved else "REJECTED ✗"
        print(f"  [RiskAgent] {status} — {signal.ticker} max {max_position_size} shares (${max_position_value:,.2f})")
        
        return assessment
    
    def get_assessments(self, ticker: Optional[str] = None) -> List[RiskAssessment]:
        """Get all risk assessments, optionally filtered by ticker."""
        if ticker:
            return [a for a in self._assessments if a.ticker == ticker.upper()]
        return self._assessments
    
    def __repr__(self):
        return f"RiskAgent(id={self.agent_id}, assessments={len(self._assessments)})"
