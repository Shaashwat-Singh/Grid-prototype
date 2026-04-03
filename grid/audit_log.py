"""
AuditLog — Append-only, hash-chained audit trail for GRID.

Every policy evaluation is recorded before execution occurs. The audit log
provides a complete forensic trail of all agent actions — both allowed
and blocked.

Key properties:
    - Append-only: entries cannot be modified or deleted
    - Hash-chained: each entry includes hash of previous entry (tamper-evident)
    - Pre-execution: decisions logged BEFORE any action executes
    - Complete: both ALLOW and BLOCK decisions captured with full context
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    """A single entry in the GRID audit log."""
    
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique entry identifier")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 timestamp of the entry"
    )
    
    # Chain integrity
    sequence_number: int = Field(..., description="Sequential entry number")
    previous_hash: Optional[str] = Field(default=None, description="SHA-256 hash of the previous entry")
    
    # Action context
    agent_id: str = Field(..., description="ID of the requesting agent")
    agent_role: str = Field(..., description="Role of the requesting agent")
    action_type: str = Field(..., description="Type of action requested")
    action_details: Dict = Field(default_factory=dict, description="Full action request details")
    
    # Contract reference
    contract_id: str = Field(..., description="ID of the governing IntentContract")
    
    # Policy evaluation
    policy_results: List[Dict] = Field(default_factory=list, description="Individual rule evaluation results")
    verdict: str = Field(..., description="ALLOW or BLOCK")
    block_reasons: List[str] = Field(default_factory=list, description="Reasons for blocking (if blocked)")
    
    # Execution result (filled after execution, if allowed)
    execution_result: Optional[Dict] = Field(default=None, description="Result of execution (if allowed)")
    
    # Entry integrity
    entry_hash: Optional[str] = Field(default=None, description="SHA-256 hash of this entry")
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this entry (excluding the hash field itself)."""
        content = self.model_dump(exclude={"entry_hash"})
        serialized = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    
    def sign(self) -> "AuditEntry":
        """Compute and store the entry hash."""
        self.entry_hash = self.compute_hash()
        return self
    
    def verify(self) -> bool:
        """Verify the entry hash is correct."""
        if not self.entry_hash:
            return False
        return self.compute_hash() == self.entry_hash


class AuditLog:
    """
    Append-only, hash-chained audit log for GRID.
    
    Records every policy evaluation with full context. Entries are chained
    via SHA-256 hashes to provide tamper evidence.
    
    Example:
        >>> log = AuditLog("./audit_logs")
        >>> entry = log.record(
        ...     agent_id="trader_001",
        ...     agent_role="trader",
        ...     action_type="trade",
        ...     action_details={"ticker": "AAPL", "side": "buy", "qty": 50},
        ...     contract_id="contract-uuid",
        ...     policy_results=[{"rule": "ticker_check", "passed": True}],
        ...     verdict="ALLOW"
        ... )
        >>> log.verify_chain()
        True
    """
    
    def __init__(self, log_dir: str = "./audit_logs", log_file: str = "grid_audit.jsonl"):
        """
        Initialize the AuditLog.
        
        Args:
            log_dir: Directory for audit log files.
            log_file: Name of the JSONL log file.
        """
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / log_file
        self._entries: List[AuditEntry] = []
        self._sequence_counter: int = 0
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing entries if any
        self._load_existing()
    
    def _load_existing(self):
        """Load existing entries from the log file."""
        if self.log_file.exists():
            with open(self.log_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            entry = AuditEntry(**data)
                            self._entries.append(entry)
                            self._sequence_counter = max(self._sequence_counter, entry.sequence_number + 1)
                        except (json.JSONDecodeError, Exception):
                            continue
    
    def record(
        self,
        agent_id: str,
        agent_role: str,
        action_type: str,
        action_details: Dict,
        contract_id: str,
        policy_results: List[Dict],
        verdict: str,
        block_reasons: Optional[List[str]] = None,
        execution_result: Optional[Dict] = None,
    ) -> AuditEntry:
        """
        Record a new audit entry.
        
        The entry is hash-chained to the previous entry and persisted
        to the log file before returning.
        
        Args:
            agent_id: ID of the requesting agent.
            agent_role: Role of the requesting agent.
            action_type: Type of action (trade, data_access, tool_use, delegation).
            action_details: Full details of the action request.
            contract_id: ID of the governing IntentContract.
            policy_results: List of individual rule evaluation results.
            verdict: "ALLOW" or "BLOCK".
            block_reasons: Reasons for blocking (if verdict is BLOCK).
            execution_result: Result of execution (if verdict is ALLOW).
            
        Returns:
            The signed AuditEntry.
        """
        # Get previous hash for chain
        previous_hash = None
        if self._entries:
            previous_hash = self._entries[-1].entry_hash
        
        # Create entry
        entry = AuditEntry(
            sequence_number=self._sequence_counter,
            previous_hash=previous_hash,
            agent_id=agent_id,
            agent_role=agent_role,
            action_type=action_type,
            action_details=action_details,
            contract_id=contract_id,
            policy_results=policy_results,
            verdict=verdict,
            block_reasons=block_reasons or [],
            execution_result=execution_result,
        )
        
        # Sign the entry
        entry.sign()
        
        # Append to in-memory list
        self._entries.append(entry)
        self._sequence_counter += 1
        
        # Persist to file
        self._persist_entry(entry)
        
        return entry
    
    def _persist_entry(self, entry: AuditEntry):
        """Append an entry to the log file (append-only)."""
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry.model_dump(), default=str) + "\n")
    
    def verify_chain(self) -> bool:
        """
        Verify the integrity of the entire audit chain.
        
        Checks that:
        1. Each entry's hash is valid.
        2. Each entry's previous_hash matches the prior entry's hash.
        3. Sequence numbers are continuous.
        
        Returns:
            True if the chain is intact, False if tampered.
        """
        if not self._entries:
            return True
        
        for i, entry in enumerate(self._entries):
            # Verify entry hash
            if not entry.verify():
                return False
            
            # Verify chain link
            if i == 0:
                if entry.previous_hash is not None:
                    return False
            else:
                if entry.previous_hash != self._entries[i - 1].entry_hash:
                    return False
            
            # Verify sequence
            if entry.sequence_number != i:
                return False
        
        return True
    
    def get_entries(
        self,
        agent_role: Optional[str] = None,
        verdict: Optional[str] = None,
        action_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[AuditEntry]:
        """
        Query audit entries with optional filters.
        
        Args:
            agent_role: Filter by agent role.
            verdict: Filter by verdict ("ALLOW" or "BLOCK").
            action_type: Filter by action type.
            limit: Maximum number of entries to return.
            
        Returns:
            List of matching AuditEntry objects.
        """
        results = self._entries
        
        if agent_role:
            results = [e for e in results if e.agent_role == agent_role]
        if verdict:
            results = [e for e in results if e.verdict == verdict]
        if action_type:
            results = [e for e in results if e.action_type == action_type]
        
        if limit:
            results = results[-limit:]
        
        return results
    
    def get_stats(self) -> Dict:
        """Get summary statistics of the audit log."""
        total = len(self._entries)
        allowed = sum(1 for e in self._entries if e.verdict == "ALLOW")
        blocked = sum(1 for e in self._entries if e.verdict == "BLOCK")
        
        by_agent = {}
        for entry in self._entries:
            role = entry.agent_role
            if role not in by_agent:
                by_agent[role] = {"allowed": 0, "blocked": 0}
            if entry.verdict == "ALLOW":
                by_agent[role]["allowed"] += 1
            else:
                by_agent[role]["blocked"] += 1
        
        by_type = {}
        for entry in self._entries:
            t = entry.action_type
            if t not in by_type:
                by_type[t] = 0
            by_type[t] += 1
        
        return {
            "total_entries": total,
            "allowed": allowed,
            "blocked": blocked,
            "block_rate": f"{(blocked / total * 100):.1f}%" if total > 0 else "0%",
            "by_agent_role": by_agent,
            "by_action_type": by_type,
            "chain_integrity": self.verify_chain(),
        }
    
    @property
    def entry_count(self) -> int:
        """Total number of audit entries."""
        return len(self._entries)
    
    @property
    def last_entry(self) -> Optional[AuditEntry]:
        """Most recent audit entry."""
        return self._entries[-1] if self._entries else None
    
    def clear(self):
        """Clear all entries (for testing only). Removes the log file."""
        self._entries.clear()
        self._sequence_counter = 0
        if self.log_file.exists():
            os.remove(self.log_file)
