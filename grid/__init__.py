"""
GRID — Constitutional Enforcement Layer for Autonomous Financial Agents

Core enforcement engine that sits between AI agent reasoning and financial
execution. Every action must pass through GRID's policy gate before it can
touch the execution layer.
"""

from grid.intent_contract import IntentContract, create_demo_contract
from grid.policy_engine import PolicyEngine, ActionRequest, EnforcementDecision
from grid.audit_log import AuditLog
from grid.enforcement_gate import GRIDEnforcementGate

__version__ = "0.2.0"
__all__ = [
    "IntentContract",
    "create_demo_contract",
    "PolicyEngine",
    "ActionRequest",
    "EnforcementDecision",
    "AuditLog",
    "GRIDEnforcementGate",
]
