"""
IntentContract — Immutable declaration of user intent.

The IntentContract captures what the user authorizes before any agent begins
operating. Once created and signed (hashed), no agent can modify it.
The contract is the constitution that GRID enforces.

Key properties:
    - Immutable after creation (SHA-256 hash locks content)
    - Declarative (users say what, not how)
    - Bounded (every permission has explicit limits)
    - Verifiable (hash can be checked at any time)
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AgentPermissions(BaseModel):
    """Defines what tools a specific agent role is allowed to use."""
    role: str = Field(..., description="Agent role identifier (e.g., 'analyst', 'risk', 'trader')")
    allowed_tools: List[str] = Field(default_factory=list, description="Tools this agent may invoke")
    can_delegate: bool = Field(default=False, description="Whether this agent can delegate to sub-agents")
    max_delegation_depth: int = Field(default=0, description="Maximum delegation depth for this agent")


class TradeConstraints(BaseModel):
    """Financial constraints for trade operations."""
    allowed_tickers: List[str] = Field(default_factory=list, description="Universe of allowed ticker symbols")
    max_order_value: float = Field(default=0.0, description="Maximum value per individual order in USD")
    max_daily_value: float = Field(default=0.0, description="Maximum aggregate daily trading value in USD")
    allowed_order_types: List[str] = Field(
        default_factory=lambda: ["market", "limit"],
        description="Permitted order types"
    )
    allowed_sides: List[str] = Field(
        default_factory=lambda: ["buy"],
        description="Permitted trade sides (buy, sell)"
    )
    market_hours_only: bool = Field(default=True, description="Restrict trading to market hours")


class DataConstraints(BaseModel):
    """Constraints on data access for agents."""
    allowed_directories: List[str] = Field(
        default_factory=lambda: ["./market_data"],
        description="Directories agents are allowed to read from"
    )
    allowed_endpoints: List[str] = Field(
        default_factory=list,
        description="External API endpoints agents may access"
    )
    deny_external_transfer: bool = Field(
        default=True,
        description="Block all outbound data transfers"
    )


class IntentContract(BaseModel):
    """
    Immutable declaration of user intent for a GRID session.
    
    Once created and signed, this contract cannot be modified by any agent.
    The enforcement gate validates every action against this contract.
    
    Example:
        >>> contract = IntentContract(
        ...     user_id="user_001",
        ...     goal="Research and trade AAPL based on technical signals",
        ...     trade_constraints=TradeConstraints(
        ...         allowed_tickers=["AAPL"],
        ...         max_order_value=10000.0,
        ...         max_daily_value=50000.0,
        ...     ),
        ...     agent_permissions=[
        ...         AgentPermissions(role="analyst", allowed_tools=["market_data"]),
        ...         AgentPermissions(role="trader", allowed_tools=["market_data", "place_order"]),
        ...     ]
        ... )
        >>> signed = contract.sign()
        >>> signed.verify_integrity()
        True
    """
    
    # --- Identity ---
    contract_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique contract identifier")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 creation timestamp"
    )
    user_id: str = Field(..., description="Identifier of the authorizing user")
    
    # --- Intent ---
    goal: str = Field(..., description="Natural language description of the user's intent")
    
    # --- Constraints ---
    trade_constraints: TradeConstraints = Field(
        default_factory=TradeConstraints,
        description="Financial trading constraints"
    )
    data_constraints: DataConstraints = Field(
        default_factory=DataConstraints,
        description="Data access constraints"
    )
    
    # --- Agent Permissions ---
    agent_permissions: List[AgentPermissions] = Field(
        default_factory=list,
        description="Per-agent tool and delegation permissions"
    )
    max_delegation_depth: int = Field(default=2, description="Global maximum delegation depth")
    
    # --- Integrity ---
    contract_hash: Optional[str] = Field(default=None, description="SHA-256 hash of the signed contract")
    is_signed: bool = Field(default=False, description="Whether this contract has been signed")
    
    @field_validator("allowed_order_types", mode="before", check_fields=False)
    @classmethod
    def validate_order_types(cls, v):
        valid_types = {"market", "limit", "stop", "stop_limit", "trailing_stop"}
        for t in v:
            if t not in valid_types:
                raise ValueError(f"Invalid order type: {t}. Must be one of {valid_types}")
        return v
    
    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of the contract content (excluding hash fields)."""
        content = self.model_dump(exclude={"contract_hash", "is_signed"})
        serialized = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    
    def sign(self) -> "IntentContract":
        """
        Sign the contract by computing and storing its hash.
        
        Once signed, the contract is immutable. Any modification
        will cause verify_integrity() to fail.
        
        Returns:
            Self with hash and signed flag set.
            
        Raises:
            RuntimeError: If the contract is already signed.
        """
        if self.is_signed:
            raise RuntimeError("Contract is already signed. Cannot re-sign an immutable contract.")
        
        self.contract_hash = self._compute_hash()
        self.is_signed = True
        return self
    
    def verify_integrity(self) -> bool:
        """
        Verify that the contract has not been tampered with.
        
        Recomputes the hash and compares it to the stored hash.
        
        Returns:
            True if the contract is intact, False if tampered.
        """
        if not self.is_signed or not self.contract_hash:
            return False
        return self._compute_hash() == self.contract_hash
    
    def get_agent_permissions(self, role: str) -> Optional[AgentPermissions]:
        """
        Get permissions for a specific agent role.
        
        Args:
            role: The agent role to look up.
            
        Returns:
            AgentPermissions for the role, or None if not found.
        """
        for perm in self.agent_permissions:
            if perm.role == role:
                return perm
        return None
    
    def is_ticker_allowed(self, ticker: str) -> bool:
        """Check if a ticker is in the allowed universe."""
        return ticker.upper() in [t.upper() for t in self.trade_constraints.allowed_tickers]
    
    def is_tool_allowed(self, role: str, tool: str) -> bool:
        """Check if a specific tool is allowed for an agent role."""
        perms = self.get_agent_permissions(role)
        if perms is None:
            return False
        return tool in perms.allowed_tools
    
    def is_within_order_limit(self, value: float) -> bool:
        """Check if an order value is within the per-order limit."""
        return value <= self.trade_constraints.max_order_value
    
    def is_directory_allowed(self, path: str) -> bool:
        """Check if a file path is within the allowed data scope."""
        import os
        normalized = os.path.normpath(path)
        for allowed_dir in self.data_constraints.allowed_directories:
            allowed_normalized = os.path.normpath(allowed_dir)
            if normalized.startswith(allowed_normalized):
                return True
        return False
    
    def summary(self) -> Dict:
        """Return a human-readable summary of the contract."""
        return {
            "contract_id": self.contract_id,
            "user": self.user_id,
            "goal": self.goal,
            "allowed_tickers": self.trade_constraints.allowed_tickers,
            "max_per_order": f"${self.trade_constraints.max_order_value:,.2f}",
            "max_daily": f"${self.trade_constraints.max_daily_value:,.2f}",
            "agents": [p.role for p in self.agent_permissions],
            "signed": self.is_signed,
            "integrity_valid": self.verify_integrity() if self.is_signed else "unsigned",
        }
    
    def __str__(self) -> str:
        status = "SIGNED ✓" if self.is_signed else "UNSIGNED"
        return (
            f"IntentContract [{status}]\n"
            f"  ID: {self.contract_id}\n"
            f"  User: {self.user_id}\n"
            f"  Goal: {self.goal}\n"
            f"  Tickers: {self.trade_constraints.allowed_tickers}\n"
            f"  Max Order: ${self.trade_constraints.max_order_value:,.2f}\n"
            f"  Max Daily: ${self.trade_constraints.max_daily_value:,.2f}\n"
            f"  Agents: {[p.role for p in self.agent_permissions]}"
        )
