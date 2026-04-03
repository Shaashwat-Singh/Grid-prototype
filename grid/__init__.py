"""
GRID — Constitutional Enforcement Layer for Autonomous Financial Agents

Core enforcement engine that sits between AI agent reasoning and financial
execution. Every action must pass through GRID's policy gate before it can
touch the execution layer.
"""

from grid.intent_contract import IntentContract
from grid.policy_engine import PolicyEngine, PolicyResult, PolicyVerdict
from grid.audit_log import AuditLog, AuditEntry
from grid.enforcement_gate import EnforcementGate

__version__ = "0.1.0"
__all__ = [
    "IntentContract",
    "PolicyEngine",
    "PolicyResult",
    "PolicyVerdict",
    "AuditLog",
    "AuditEntry",
    "EnforcementGate",
]
