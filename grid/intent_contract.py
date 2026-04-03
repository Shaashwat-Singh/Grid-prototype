"""
GRID Intent Contract
The immutable declaration of what an agent session is authorized to do.
Declared once by the user. Cannot be modified by agents at runtime.
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional
from datetime import datetime
import hashlib
import json


class TradePolicy(BaseModel):
    per_order_usd: float = Field(default=500.0, description="Max USD value per single order")
    daily_usd: float = Field(default=1000.0, description="Max total USD traded per day")
    max_shares_per_order: int = Field(default=50, description="Max shares in a single order")
    allowed_tickers: List[str] = Field(default=["NVDA", "AAPL"], description="Approved ticker universe")
    allowed_sides: List[str] = Field(default=["buy", "sell"])
    market_hours_only: bool = Field(default=True)


class DataPolicy(BaseModel):
    readable_directories: List[str] = Field(default=["/data/market/", "/reports/"])
    writable_directories: List[str] = Field(default=["/reports/output/"])
    forbidden_endpoints: List[str] = Field(default=[], description="External URLs agents cannot reach")


class DelegationPolicy(BaseModel):
    analyst_can_delegate: bool = Field(default=True, description="Can pass recommendations to risk")
    risk_can_delegate: bool = Field(default=True, description="Can pass approvals to trader")
    trader_can_delegate: bool = Field(default=False, description="Trader is terminal — cannot sub-delegate")
    max_depth: int = Field(default=2, description="Maximum delegation hops from orchestrator")


class IntentContract(BaseModel):
    session_id: str
    declared_goal: str = Field(description="Human-readable statement of what this session should accomplish")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    trade_policy: TradePolicy = Field(default_factory=TradePolicy)
    data_policy: DataPolicy = Field(default_factory=DataPolicy)
    delegation_policy: DelegationPolicy = Field(default_factory=DelegationPolicy)

    allowed_tools: List[str] = Field(
        default=["get_market_data", "get_portfolio", "generate_report", "place_trade"],
        description="Complete list of tools any agent may invoke"
    )
    forbidden_tools: List[str] = Field(
        default=["shell_exec", "send_email", "http_post", "webhook_trigger", "file_delete"],
        description="Tools that are explicitly blocked regardless of agent"
    )

    agent_scopes: Dict[str, List[str]] = Field(
        default={
            "analyst-agent": ["get_market_data", "generate_report"],
            "risk-agent": ["get_portfolio", "generate_report"],
            "trader-agent": ["place_trade", "get_portfolio"]
        },
        description="Per-agent tool authorization — each agent can only use its listed tools"
    )

    paper_trading_only: bool = Field(default=True)
    _contract_hash: Optional[str] = None

    def compute_hash(self) -> str:
        payload = self.model_dump(exclude={"_contract_hash"})
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()

    def seal(self) -> "IntentContract":
        """Compute and store hash. Once sealed, any field change invalidates the hash."""
        self._contract_hash = self.compute_hash()
        return self

    def verify_integrity(self) -> bool:
        if self._contract_hash is None:
            return False
        return self.compute_hash() == self._contract_hash


def create_demo_contract() -> IntentContract:
    """Create the standard demo intent contract used in hackathon submission."""
    contract = IntentContract(
        session_id="grid-demo-001",
        declared_goal=(
            "Research NVDA fundamentals. If P/E ratio is below 35 and risk agent "
            "approves portfolio exposure, execute a market buy within defined limits. "
            "Maximum $500 per order, $1000 daily, NVDA only."
        ),
        trade_policy=TradePolicy(
            per_order_usd=500.0,
            daily_usd=1000.0,
            max_shares_per_order=50,
            allowed_tickers=["NVDA", "AAPL"],
            market_hours_only=False  # disabled for demo so we can run anytime
        ),
    )
    return contract.seal()
