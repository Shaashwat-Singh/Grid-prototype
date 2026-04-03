"""
GRID Enforcement Gate
The only path between agent action requests and financial execution.
Agents have NO direct access to Alpaca. The gate holds all credentials.
"""

import os
import alpaca_trade_api as tradeapi
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from grid.intent_contract import IntentContract
from grid.policy_engine import PolicyEngine, ActionRequest, EnforcementDecision
from grid.audit_log import AuditLog

load_dotenv()


class GRIDEnforcementGate:
    """
    Constitutional enforcement gate for financial AI agents.

    Architectural guarantees:
    1. No agent holds Alpaca credentials — only the gate does
    2. Every action_request is evaluated against IntentContract before execution
    3. Every decision (ALLOW and BLOCK) is written to audit log
    4. Blocked actions never reach the execution layer
    5. The gate cannot be instructed to bypass its own enforcement
    """

    def __init__(self, contract: IntentContract):
        if not contract.verify_integrity():
            raise ValueError("IntentContract integrity check failed — contract may have been tampered with")

        self.contract = contract
        self.policy = PolicyEngine(contract)
        self.audit = AuditLog()

        # Gate holds all execution credentials — agents never see these
        self._alpaca = tradeapi.REST(
            os.getenv("ALPACA_API_KEY", ""),
            os.getenv("ALPACA_SECRET_KEY", ""),
            os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        )

        print(f"[GRID] Gate initialized for session: {contract.session_id}")
        print(f"[GRID] Contract hash: {contract.compute_hash()}")
        print(f"[GRID] Paper trading only: {contract.paper_trading_only}")

    def request_market_data(self, agent_id: str, ticker: str) -> Dict[str, Any]:
        """Read-only market data — always permitted for registered agents."""
        req = ActionRequest(
            agent_id=agent_id,
            action_type="use_tool",
            tool_name="get_market_data",
            session_id=self.contract.session_id,
            ticker=ticker,
            raw_params=f"ticker={ticker}"
        )

        decision = self.policy.evaluate(req)
        self.audit.record(decision)

        if decision.result == "BLOCK":
            return {"status": "BLOCKED", "reason": decision.reason}

        try:
            bar = self._alpaca.get_latest_bar(ticker)
            latest_trade = self._alpaca.get_latest_trade(ticker)
            return {
                "status": "ALLOWED",
                "ticker": ticker,
                "price": float(latest_trade.price),
                "close": float(bar.c),
                "volume": int(bar.v),
                "timestamp": str(bar.t)
            }
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def request_trade(
        self,
        agent_id: str,
        ticker: str,
        quantity: int,
        side: str,
        price_hint: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Submit a trade request through the enforcement gate.
        The gate evaluates the request, then — only if approved — executes via Alpaca.
        """
        # Estimate order value for policy evaluation
        try:
            if price_hint is None:
                latest = self._alpaca.get_latest_trade(ticker)
                price_hint = float(latest.price)
        except Exception:
            price_hint = 150.0  # Conservative fallback for demo

        order_value = price_hint * quantity

        req = ActionRequest(
            agent_id=agent_id,
            action_type="place_trade",
            session_id=self.contract.session_id,
            ticker=ticker,
            quantity=quantity,
            side=side,
            order_value_usd=order_value,
            raw_params=f"ticker={ticker} qty={quantity} side={side} est_value=${order_value:.2f}"
        )

        decision = self.policy.evaluate(req)
        self.audit.record(decision)

        if decision.result == "BLOCK":
            return {
                "status": "BLOCKED",
                "reason": decision.reason,
                "policy_violated": decision.policy_violated,
                "requested": {"ticker": ticker, "quantity": quantity, "side": side}
            }

        # Execute only after enforcement approval
        try:
            order = self._alpaca.submit_order(
                symbol=ticker,
                qty=quantity,
                side=side,
                type="market",
                time_in_force="day"
            )
            return {
                "status": "EXECUTED",
                "order_id": str(order.id),
                "ticker": ticker,
                "quantity": quantity,
                "side": side,
                "estimated_value": f"${order_value:.2f}",
                "alpaca_status": order.status
            }
        except Exception as e:
            return {"status": "EXECUTION_ERROR", "message": str(e)}

    def request_tool(
        self,
        agent_id: str,
        tool_name: str,
        parameters: str = "",
        raw_content: str = ""
    ) -> Dict[str, Any]:
        """
        Request to invoke a tool. Gate evaluates against tool restrictions
        and injection patterns before any execution.
        """
        req = ActionRequest(
            agent_id=agent_id,
            action_type="use_tool",
            session_id=self.contract.session_id,
            tool_name=tool_name,
            tool_parameters=parameters,
            raw_content=raw_content,
            raw_params=f"tool={tool_name} params={parameters[:200]}"
        )

        decision = self.policy.evaluate(req)
        self.audit.record(decision)

        return {
            "status": decision.result,
            "reason": decision.reason,
            "policy_violated": decision.policy_violated
        }

    def request_delegation(
        self,
        from_agent: str,
        to_agent: str,
        scope: list
    ) -> Dict[str, Any]:
        """
        Request to delegate authority from one agent to another.
        Delegation bounds are enforced by policy.
        """
        req = ActionRequest(
            agent_id=from_agent,
            action_type="delegate",
            session_id=self.contract.session_id,
            delegate_to=to_agent,
            delegated_scope=scope,
            raw_params=f"from={from_agent} to={to_agent} scope={scope}"
        )

        decision = self.policy.evaluate(req)
        self.audit.record(decision)

        return {
            "status": decision.result,
            "reason": decision.reason,
            "delegation": {"from": from_agent, "to": to_agent, "scope": scope}
        }

    def get_portfolio(self, agent_id: str) -> Dict[str, Any]:
        """Retrieve current paper portfolio."""
        req = ActionRequest(
            agent_id=agent_id,
            action_type="use_tool",
            tool_name="get_portfolio",
            session_id=self.contract.session_id,
        )
        decision = self.policy.evaluate(req)
        self.audit.record(decision)

        if decision.result == "BLOCK":
            return {"status": "BLOCKED", "reason": decision.reason}

        try:
            account = self._alpaca.get_account()
            positions = self._alpaca.list_positions()
            return {
                "status": "ALLOWED",
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "positions": [
                    {
                        "ticker": p.symbol,
                        "qty": int(p.qty),
                        "market_value": float(p.market_value),
                        "unrealized_pl": float(p.unrealized_pl)
                    }
                    for p in positions
                ]
            }
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def get_audit_log(self, limit: int = 20) -> list:
        return self.audit.get_recent(limit=limit, session_id=self.contract.session_id)

    def get_stats(self) -> dict:
        return self.audit.get_stats(session_id=self.contract.session_id)
