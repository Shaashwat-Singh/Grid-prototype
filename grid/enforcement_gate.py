"""
EnforcementGate — The single point of control between reasoning and execution.

The EnforcementGate is the core of GRID. It:
    1. Receives ActionRequests from agents
    2. Invokes the PolicyEngine for evaluation
    3. Writes the decision to the AuditLog (BEFORE execution)
    4. Executes allowed actions via the Alpaca API (gate holds all credentials)
    5. Returns results to the requesting agent
    6. Blocks and logs all denied actions

Key invariant: Agents NEVER have direct API access.
The gate is the only component with execution credentials.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from grid.audit_log import AuditLog
from grid.intent_contract import IntentContract
from grid.policy_engine import ActionRequest, PolicyEngine, PolicyResult, PolicyVerdict

load_dotenv()


class ExecutionResult:
    """Result of processing an action request through the gate."""
    
    def __init__(
        self,
        allowed: bool,
        verdict: str,
        policy_result: PolicyResult,
        execution_data: Optional[Dict] = None,
        error: Optional[str] = None,
    ):
        self.allowed = allowed
        self.verdict = verdict
        self.policy_result = policy_result
        self.execution_data = execution_data
        self.error = error
    
    def __repr__(self):
        return (
            f"ExecutionResult(allowed={self.allowed}, verdict={self.verdict}, "
            f"data={self.execution_data}, error={self.error})"
        )
    
    def to_dict(self) -> Dict:
        return {
            "allowed": self.allowed,
            "verdict": self.verdict,
            "policy_summary": self.policy_result.summary(),
            "execution_data": self.execution_data,
            "error": self.error,
        }


class EnforcementGate:
    """
    Constitutional enforcement gate for GRID.
    
    All agent action requests must pass through this gate. The gate:
    - Evaluates requests against the IntentContract via PolicyEngine
    - Logs all decisions to the AuditLog before execution
    - Executes allowed trade actions via Alpaca Paper API
    - Blocks and logs all denied actions
    
    The gate holds all API credentials. Agents receive a reference
    to the gate, never to the API directly.
    
    Example:
        >>> gate = EnforcementGate(contract, audit_log)
        >>> request = ActionRequest(
        ...     agent_id="trader_001",
        ...     agent_role="trader",
        ...     action_type="trade",
        ...     ticker="AAPL",
        ...     side="buy",
        ...     quantity=50,
        ...     estimated_value=8500.0
        ... )
        >>> result = gate.process(request)
        >>> result.allowed
        True
    """
    
    def __init__(
        self,
        contract: IntentContract,
        audit_log: Optional[AuditLog] = None,
        alpaca_api_key: Optional[str] = None,
        alpaca_secret_key: Optional[str] = None,
        alpaca_base_url: Optional[str] = None,
        dry_run: bool = True,
    ):
        """
        Initialize the EnforcementGate.
        
        Args:
            contract: The signed IntentContract to enforce.
            audit_log: AuditLog instance (creates default if None).
            alpaca_api_key: Alpaca API key (falls back to env var).
            alpaca_secret_key: Alpaca secret key (falls back to env var).
            alpaca_base_url: Alpaca base URL (falls back to env var).
            dry_run: If True, simulate execution without hitting Alpaca API.
        """
        # Validate contract
        if not contract.is_signed:
            raise ValueError("EnforcementGate requires a signed IntentContract.")
        if not contract.verify_integrity():
            raise ValueError("Contract integrity verification failed.")
        
        self.contract = contract
        self.policy_engine = PolicyEngine(contract)
        self.audit_log = audit_log or AuditLog()
        self.dry_run = dry_run
        
        # Credential isolation: only the gate holds API keys
        self._alpaca_api_key = alpaca_api_key or os.getenv("ALPACA_API_KEY")
        self._alpaca_secret_key = alpaca_secret_key or os.getenv("ALPACA_SECRET_KEY")
        self._alpaca_base_url = alpaca_base_url or os.getenv(
            "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
        )
        
        # Initialize Alpaca client (lazy)
        self._alpaca_client = None
        
        # Statistics
        self._stats = {
            "total_requests": 0,
            "allowed": 0,
            "blocked": 0,
            "errors": 0,
        }
    
    def _get_alpaca_client(self):
        """Lazy-initialize the Alpaca trading client."""
        if self._alpaca_client is None and not self.dry_run:
            try:
                import alpaca_trade_api as tradeapi
                self._alpaca_client = tradeapi.REST(
                    key_id=self._alpaca_api_key,
                    secret_key=self._alpaca_secret_key,
                    base_url=self._alpaca_base_url,
                )
            except ImportError:
                raise RuntimeError(
                    "alpaca-trade-api is required for live execution. "
                    "Install with: pip install alpaca-trade-api"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Alpaca client: {e}")
        return self._alpaca_client
    
    def process(self, request: ActionRequest) -> ExecutionResult:
        """
        Process an action request through the enforcement gate.
        
        This is the main entry point. The flow is:
        1. Evaluate against PolicyEngine
        2. Log decision to AuditLog (BEFORE execution)
        3. If allowed and trade: execute via Alpaca
        4. Return result
        
        Args:
            request: The ActionRequest from an agent.
            
        Returns:
            ExecutionResult with verdict, policy details, and execution data.
        """
        self._stats["total_requests"] += 1
        
        # Step 1: Evaluate against policy engine
        policy_result = self.policy_engine.evaluate(request)
        
        # Step 2: Determine action details for logging
        action_details = {
            "agent_id": request.agent_id,
            "agent_role": request.agent_role,
            "action_type": request.action_type,
            "ticker": request.ticker,
            "side": request.side,
            "quantity": request.quantity,
            "order_type": request.order_type,
            "estimated_value": request.estimated_value,
            "tool_name": request.tool_name,
            "file_path": request.file_path,
            "delegation_depth": request.delegation_depth,
        }
        
        policy_results_dicts = [
            {
                "rule": r.rule_name,
                "passed": r.passed,
                "reason": r.reason,
            }
            for r in policy_result.rule_results
        ]
        
        execution_data = None
        error = None
        
        if policy_result.is_allowed:
            self._stats["allowed"] += 1
            
            # Step 3: Execute if allowed and it's a trade
            if request.action_type == "trade":
                try:
                    execution_data = self._execute_trade(request)
                except Exception as e:
                    error = str(e)
                    self._stats["errors"] += 1
            elif request.action_type == "data_access":
                execution_data = {"status": "data_access_granted", "path": request.file_path}
            elif request.action_type == "tool_use":
                execution_data = {"status": "tool_use_granted", "tool": request.tool_name}
            else:
                execution_data = {"status": "action_allowed"}
        else:
            self._stats["blocked"] += 1
        
        # Step 4: Log to audit trail (BEFORE returning result)
        self.audit_log.record(
            agent_id=request.agent_id,
            agent_role=request.agent_role,
            action_type=request.action_type,
            action_details=action_details,
            contract_id=self.contract.contract_id,
            policy_results=policy_results_dicts,
            verdict=policy_result.verdict.value,
            block_reasons=policy_result.block_reasons,
            execution_result=execution_data,
        )
        
        return ExecutionResult(
            allowed=policy_result.is_allowed,
            verdict=policy_result.verdict.value,
            policy_result=policy_result,
            execution_data=execution_data,
            error=error,
        )
    
    def _execute_trade(self, request: ActionRequest) -> Dict:
        """
        Execute a trade via the Alpaca Paper API.
        
        Only called for ALLOWED trade requests. The gate holds the credentials.
        
        Args:
            request: The validated ActionRequest.
            
        Returns:
            Execution result dictionary.
        """
        if self.dry_run:
            return {
                "status": "simulated",
                "mode": "dry_run",
                "ticker": request.ticker,
                "side": request.side,
                "quantity": request.quantity,
                "order_type": request.order_type or "market",
                "estimated_value": request.estimated_value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"[DRY RUN] Would place {request.side} order for {request.quantity} shares of {request.ticker}",
            }
        
        # Live execution via Alpaca
        client = self._get_alpaca_client()
        if client is None:
            return {
                "status": "error",
                "message": "Alpaca client not available",
            }
        
        try:
            order = client.submit_order(
                symbol=request.ticker,
                qty=request.quantity,
                side=request.side,
                type=request.order_type or "market",
                time_in_force="day",
                limit_price=request.limit_price if request.order_type == "limit" else None,
            )
            
            return {
                "status": "executed",
                "mode": "paper",
                "order_id": str(order.id),
                "ticker": request.ticker,
                "side": request.side,
                "quantity": request.quantity,
                "order_type": request.order_type or "market",
                "order_status": str(order.status),
                "submitted_at": str(order.submitted_at),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "status": "execution_error",
                "error": str(e),
                "ticker": request.ticker,
                "side": request.side,
                "quantity": request.quantity,
            }
    
    def get_stats(self) -> Dict:
        """Get gate processing statistics."""
        return {
            **self._stats,
            "block_rate": (
                f"{(self._stats['blocked'] / self._stats['total_requests'] * 100):.1f}%"
                if self._stats["total_requests"] > 0 else "0%"
            ),
            "audit_entries": self.audit_log.entry_count,
            "chain_integrity": self.audit_log.verify_chain(),
            "dry_run_mode": self.dry_run,
        }
    
    def get_audit_stats(self) -> Dict:
        """Get audit log statistics."""
        return self.audit_log.get_stats()
    
    def verify_system_integrity(self) -> Dict:
        """
        Run a complete system integrity check.
        
        Verifies:
        1. Contract integrity (hash)
        2. Audit chain integrity (hash chain)
        3. Gate credential status
        
        Returns:
            Dictionary with integrity check results.
        """
        contract_ok = self.contract.verify_integrity()
        chain_ok = self.audit_log.verify_chain()
        creds_present = bool(self._alpaca_api_key and self._alpaca_secret_key)
        
        return {
            "contract_integrity": "✓ VALID" if contract_ok else "✗ TAMPERED",
            "audit_chain_integrity": "✓ VALID" if chain_ok else "✗ BROKEN",
            "credentials_loaded": "✓ YES" if creds_present else "○ NO (dry run only)",
            "overall": "HEALTHY" if (contract_ok and chain_ok) else "COMPROMISED",
        }
