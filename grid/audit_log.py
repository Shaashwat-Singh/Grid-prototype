"""
GRID Audit Log
Immutable append-only record of every enforcement decision.
Every action — allowed and blocked — is logged before execution.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from grid.policy_engine import EnforcementDecision


class AuditLog:
    """
    Append-only enforcement decision log.

    Design principles:
    - Immutable: entries cannot be modified or deleted
    - Complete: every decision (ALLOW and BLOCK) is recorded
    - Attributable: every entry includes agent ID, timestamp, and policy context
    - Interpretable: human-readable reason for every enforcement decision
    """

    def __init__(self, db_path: str = "grid_audit.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS enforcement_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT NOT NULL,
                session_id   TEXT NOT NULL,
                agent_id     TEXT NOT NULL,
                action_type  TEXT NOT NULL,
                result       TEXT NOT NULL CHECK(result IN ('ALLOW', 'BLOCK')),
                reason       TEXT NOT NULL,
                policy_violated TEXT,
                ticker       TEXT,
                order_value  REAL,
                tool_name    TEXT,
                raw_params   TEXT,
                checks_json  TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, decision: EnforcementDecision) -> int:
        """Record an enforcement decision. Returns the log entry ID."""
        req = decision.action_request
        checks_json = json.dumps([
            {"policy": c.policy_name, "passed": c.passed, "detail": c.detail}
            for c in decision.checks_run
        ])

        conn = self._connect()
        cursor = conn.execute("""
            INSERT INTO enforcement_log
            (timestamp, session_id, agent_id, action_type, result, reason,
             policy_violated, ticker, order_value, tool_name, raw_params, checks_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            decision.timestamp,
            req.session_id,
            req.agent_id,
            req.action_type,
            decision.result,
            decision.reason,
            decision.policy_violated,
            req.ticker,
            req.order_value_usd,
            req.tool_name,
            req.raw_params[:500] if req.raw_params else None,
            checks_json
        ))
        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return entry_id

    def get_recent(self, limit: int = 50, session_id: Optional[str] = None) -> List[Dict]:
        conn = self._connect()
        if session_id:
            rows = conn.execute(
                "SELECT * FROM enforcement_log WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM enforcement_log ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        conn = self._connect()
        if session_id:
            where = f"WHERE session_id='{session_id}'"
        else:
            where = ""

        total = conn.execute(f"SELECT COUNT(*) FROM enforcement_log {where}").fetchone()[0]
        allowed = conn.execute(
            f"SELECT COUNT(*) FROM enforcement_log {where} "
            f"{'AND' if where else 'WHERE'} result='ALLOW'"
        ).fetchone()[0]
        blocked = conn.execute(
            f"SELECT COUNT(*) FROM enforcement_log {where} "
            f"{'AND' if where else 'WHERE'} result='BLOCK'"
        ).fetchone()[0]

        blocked_by_policy = conn.execute(f"""
            SELECT policy_violated, COUNT(*) as count
            FROM enforcement_log {where} {'AND' if where else 'WHERE'} result='BLOCK'
            GROUP BY policy_violated ORDER BY count DESC
        """).fetchall()

        conn.close()
        return {
            "total": total,
            "allowed": allowed,
            "blocked": blocked,
            "block_rate": f"{(blocked/total*100):.1f}%" if total > 0 else "0%",
            "blocked_by_policy": [dict(r) for r in blocked_by_policy]
        }
