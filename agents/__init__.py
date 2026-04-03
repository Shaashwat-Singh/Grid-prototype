"""
GRID Agents — OpenClaw-compatible agent mesh for financial workflows.

Each agent operates within bounded authority defined by the IntentContract.
Agents produce ActionRequests but cannot execute directly. All execution
goes through the EnforcementGate.
"""

from agents.analyst_agent import AnalystAgent
from agents.risk_agent import RiskAgent
from agents.trader_agent import TraderAgent

__all__ = ["AnalystAgent", "RiskAgent", "TraderAgent"]
