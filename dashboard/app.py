"""
GRID Dashboard — Real-time monitoring and audit visualization.

Streamlit-based dashboard for monitoring GRID enforcement activity,
viewing audit logs, inspecting contract details, and running
enforcement scenarios interactively.

Usage:
    streamlit run dashboard/app.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from grid.intent_contract import (
    IntentContract,
    TradeConstraints,
    DataConstraints,
    AgentPermissions,
)
from grid.audit_log import AuditLog
from grid.enforcement_gate import EnforcementGate
from grid.policy_engine import ActionRequest
from demo.scenarios import get_all_scenarios


# ──────────────────────────────────────────────────────────────
# Page Configuration
# ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="GRID — Constitutional Enforcement Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .sub-header {
        color: #888;
        font-size: 1.1rem;
        margin-top: -10px;
    }
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #333;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .allow-badge {
        color: #00c853;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .block-badge {
        color: #ff1744;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1a2e;
        border-radius: 8px;
        padding: 8px 16px;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# Session State Initialization
# ──────────────────────────────────────────────────────────────

def init_session():
    """Initialize GRID components in session state."""
    if "initialized" not in st.session_state:
        # Create contract
        contract = IntentContract(
            user_id="dashboard_user",
            goal="Research and trade select tech stocks with bounded risk controls",
            trade_constraints=TradeConstraints(
                allowed_tickers=["AAPL", "GOOGL", "MSFT", "NVDA"],
                max_order_value=10000.0,
                max_daily_value=50000.0,
                allowed_order_types=["market", "limit"],
                allowed_sides=["buy"],
                market_hours_only=True,
            ),
            data_constraints=DataConstraints(
                allowed_directories=["./market_data"],
                deny_external_transfer=True,
            ),
            agent_permissions=[
                AgentPermissions(role="analyst", allowed_tools=["market_data", "get_position"]),
                AgentPermissions(role="risk", allowed_tools=["market_data", "get_position", "get_portfolio"]),
                AgentPermissions(role="trader", allowed_tools=["market_data", "place_order", "get_position"]),
            ],
            max_delegation_depth=2,
        )
        contract.sign()

        audit_log = AuditLog(log_dir="./audit_logs", log_file="dashboard_audit.jsonl")
        audit_log.clear()

        gate = EnforcementGate(contract=contract, audit_log=audit_log, dry_run=True)

        st.session_state.contract = contract
        st.session_state.audit_log = audit_log
        st.session_state.gate = gate
        st.session_state.scenario_results = []
        st.session_state.initialized = True


init_session()


# ──────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────

st.markdown('<p class="main-header">🛡️ GRID Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Constitutional Enforcement Layer — Real-time Monitoring</p>', unsafe_allow_html=True)
st.markdown("---")


# ──────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔒 System Status")

    integrity = st.session_state.gate.verify_system_integrity()
    overall_status = integrity["overall"]

    if overall_status == "HEALTHY":
        st.success("System: HEALTHY ✓")
    else:
        st.error("System: COMPROMISED ✗")

    st.markdown(f"- Contract: {integrity['contract_integrity']}")
    st.markdown(f"- Audit Chain: {integrity['audit_chain_integrity']}")
    st.markdown(f"- Credentials: {integrity['credentials_loaded']}")

    st.markdown("---")
    st.markdown("## 📋 Contract Info")
    st.markdown(f"**User:** {st.session_state.contract.user_id}")
    st.markdown(f"**Tickers:** {', '.join(st.session_state.contract.trade_constraints.allowed_tickers)}")
    st.markdown(f"**Max Order:** ${st.session_state.contract.trade_constraints.max_order_value:,.0f}")
    st.markdown(f"**Max Daily:** ${st.session_state.contract.trade_constraints.max_daily_value:,.0f}")
    st.markdown(f"**Delegation Limit:** {st.session_state.contract.max_delegation_depth}")

    st.markdown("---")
    if st.button("🔄 Reset Session", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ──────────────────────────────────────────────────────────────
# Main Tabs
# ──────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Overview",
    "🧪 Scenario Tester",
    "📝 Audit Log",
    "🔬 Custom Request",
])


# ──────────────────────────────────────────────────────────────
# Tab 1: Overview
# ──────────────────────────────────────────────────────────────

with tab1:
    stats = st.session_state.gate.get_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Requests", stats["total_requests"])
    with col2:
        st.metric("Allowed", stats["allowed"], delta=None)
    with col3:
        st.metric("Blocked", stats["blocked"], delta=None)
    with col4:
        st.metric("Block Rate", stats["block_rate"])

    st.markdown("---")

    if st.session_state.audit_log.entry_count > 0:
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("### Verdict Distribution")
            entries = st.session_state.audit_log.get_entries()
            verdicts = [e.verdict for e in entries]
            verdict_counts = {"ALLOW": verdicts.count("ALLOW"), "BLOCK": verdicts.count("BLOCK")}

            fig = go.Figure(data=[go.Pie(
                labels=list(verdict_counts.keys()),
                values=list(verdict_counts.values()),
                marker=dict(colors=["#00c853", "#ff1744"]),
                hole=0.5,
                textinfo="label+value",
                textfont=dict(size=16),
            )])
            fig.update_layout(
                showlegend=False,
                height=300,
                margin=dict(t=20, b=20, l=20, r=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.markdown("### Actions by Agent Role")
            roles = [e.agent_role for e in entries]
            role_verdicts = {}
            for e in entries:
                key = e.agent_role
                if key not in role_verdicts:
                    role_verdicts[key] = {"ALLOW": 0, "BLOCK": 0}
                role_verdicts[key][e.verdict] += 1

            df = pd.DataFrame([
                {"Role": role, "Verdict": verdict, "Count": count}
                for role, counts in role_verdicts.items()
                for verdict, count in counts.items()
            ])

            fig2 = px.bar(
                df, x="Role", y="Count", color="Verdict",
                color_discrete_map={"ALLOW": "#00c853", "BLOCK": "#ff1744"},
                barmode="group",
            )
            fig2.update_layout(
                height=300,
                margin=dict(t=20, b=20, l=20, r=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
            )
            st.plotly_chart(fig2, use_container_width=True)

        # Timeline
        st.markdown("### Decision Timeline")
        timeline_data = []
        for e in entries:
            timeline_data.append({
                "Time": e.timestamp,
                "Agent": e.agent_role,
                "Action": e.action_type,
                "Verdict": e.verdict,
                "Details": str(e.action_details.get("ticker", e.action_details.get("tool_name", "N/A"))),
            })

        df_timeline = pd.DataFrame(timeline_data)
        st.dataframe(df_timeline, use_container_width=True, hide_index=True)
    else:
        st.info("No audit entries yet. Run some scenarios in the **Scenario Tester** tab to populate data.")


# ──────────────────────────────────────────────────────────────
# Tab 2: Scenario Tester
# ──────────────────────────────────────────────────────────────

with tab2:
    st.markdown("### Run Enforcement Scenarios")
    st.markdown("Each scenario tests a specific GRID enforcement capability.")

    scenarios = get_all_scenarios()

    col_run_all, col_reset = st.columns([1, 1])
    with col_run_all:
        run_all = st.button("▶ Run All Scenarios", use_container_width=True, type="primary")
    with col_reset:
        if st.button("🔄 Reset & Run Fresh", use_container_width=True):
            st.session_state.audit_log.clear()
            st.session_state.gate.policy_engine.reset_daily_totals()
            st.session_state.gate._stats = {"total_requests": 0, "allowed": 0, "blocked": 0, "errors": 0}
            st.session_state.scenario_results = []
            st.rerun()

    if run_all:
        st.session_state.audit_log.clear()
        st.session_state.gate.policy_engine.reset_daily_totals()
        st.session_state.gate._stats = {"total_requests": 0, "allowed": 0, "blocked": 0, "errors": 0}
        st.session_state.scenario_results = []

        for i, scenario in enumerate(scenarios, 1):
            result = st.session_state.gate.process(scenario["request"])
            match = result.verdict == scenario["expected_verdict"]
            st.session_state.scenario_results.append({
                "number": i,
                "name": scenario["name"],
                "expected": scenario["expected_verdict"],
                "actual": result.verdict,
                "match": match,
                "result": result,
                "tests": scenario["tests"],
            })

    if st.session_state.scenario_results:
        for sr in st.session_state.scenario_results:
            i = sr["number"]
            scenario = scenarios[i - 1]
            result = sr["result"]
            match = sr["match"]

            icon = "✅" if match else "❌"
            verdict_icon = "🟢" if result.verdict == "ALLOW" else "🔴"

            with st.expander(f"{icon} Scenario {i}: {sr['name']} — {verdict_icon} {result.verdict}", expanded=not match):
                st.markdown(f"**Description:** {scenario['description']}")
                st.markdown(f"**Tests:** {sr['tests']}")
                st.markdown(f"**Expected:** `{sr['expected']}` | **Actual:** `{sr['actual']}` | **Match:** {'✓' if match else '✗'}")

                st.markdown("**Policy Rules:**")
                for rule in result.policy_result.rule_results:
                    r_icon = "✅" if rule.passed else "❌"
                    st.markdown(f"- {r_icon} **{rule.rule_name}**: {rule.reason}")

        # Summary
        passed = sum(1 for sr in st.session_state.scenario_results if sr["match"])
        total = len(st.session_state.scenario_results)
        if passed == total:
            st.success(f"All {total} scenarios passed! ✓")
        else:
            st.warning(f"{passed}/{total} scenarios passed.")


# ──────────────────────────────────────────────────────────────
# Tab 3: Audit Log
# ──────────────────────────────────────────────────────────────

with tab3:
    st.markdown("### Audit Log — Append-Only, Hash-Chained")

    entries = st.session_state.audit_log.get_entries()

    if entries:
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            filter_verdict = st.selectbox("Filter by Verdict", ["All", "ALLOW", "BLOCK"])
        with col_filter2:
            filter_role = st.selectbox("Filter by Agent Role", ["All"] + list(set(e.agent_role for e in entries)))

        filtered = entries
        if filter_verdict != "All":
            filtered = [e for e in filtered if e.verdict == filter_verdict]
        if filter_role != "All":
            filtered = [e for e in filtered if e.agent_role == filter_role]

        # Chain integrity
        chain_ok = st.session_state.audit_log.verify_chain()
        if chain_ok:
            st.success("🔗 Hash chain integrity: VERIFIED ✓")
        else:
            st.error("🔗 Hash chain integrity: BROKEN ✗")

        for entry in reversed(filtered):
            verdict_color = "🟢" if entry.verdict == "ALLOW" else "🔴"
            with st.expander(
                f"{verdict_color} #{entry.sequence_number} | {entry.agent_role} | {entry.action_type} | {entry.verdict}",
                expanded=False,
            ):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"**Entry ID:** `{entry.entry_id[:16]}...`")
                    st.markdown(f"**Timestamp:** {entry.timestamp}")
                    st.markdown(f"**Agent:** {entry.agent_id} ({entry.agent_role})")
                    st.markdown(f"**Action:** {entry.action_type}")
                with col_b:
                    st.markdown(f"**Verdict:** {entry.verdict}")
                    st.markdown(f"**Contract:** `{entry.contract_id[:16]}...`")
                    st.markdown(f"**Entry Hash:** `{entry.entry_hash[:24]}...`" if entry.entry_hash else "N/A")
                    st.markdown(f"**Prev Hash:** `{entry.previous_hash[:24]}...`" if entry.previous_hash else "Genesis entry")

                st.markdown("**Policy Results:**")
                for pr in entry.policy_results:
                    p_icon = "✅" if pr["passed"] else "❌"
                    st.markdown(f"- {p_icon} **{pr['rule']}**: {pr['reason']}")

                if entry.block_reasons:
                    st.error("**Block Reasons:** " + "; ".join(entry.block_reasons))

                if entry.execution_result:
                    st.json(entry.execution_result)
    else:
        st.info("No audit entries yet. Run scenarios to populate the audit log.")


# ──────────────────────────────────────────────────────────────
# Tab 4: Custom Request
# ──────────────────────────────────────────────────────────────

with tab4:
    st.markdown("### Submit a Custom Action Request")
    st.markdown("Test GRID enforcement with your own parameters.")

    col_left, col_right = st.columns(2)

    with col_left:
        agent_role = st.selectbox("Agent Role", ["trader", "analyst", "risk", "unknown_role"])
        action_type = st.selectbox("Action Type", ["trade", "tool_use", "data_access", "delegation"])
        agent_id = st.text_input("Agent ID", value=f"{agent_role}_custom")

    with col_right:
        ticker = st.text_input("Ticker", value="AAPL") if action_type == "trade" else None
        side = st.selectbox("Side", ["buy", "sell"]) if action_type == "trade" else None
        quantity = st.number_input("Quantity", min_value=1, value=50) if action_type == "trade" else None
        estimated_value = st.number_input("Estimated Value ($)", min_value=0.0, value=8625.0) if action_type == "trade" else None

    tool_name = None
    file_path = None
    delegation_depth = 0
    raw_reasoning = None

    if action_type == "tool_use":
        tool_name = st.selectbox("Tool", ["market_data", "place_order", "get_position", "get_portfolio", "send_email"])

    if action_type == "data_access":
        file_path = st.text_input("File Path", value="./market_data/prices.csv")

    if action_type == "delegation":
        delegation_depth = st.number_input("Delegation Depth", min_value=0, value=0)

    raw_reasoning = st.text_area("Raw Reasoning (optional — for injection detection)", value="", height=80)

    if st.button("🚀 Submit Request", type="primary", use_container_width=True):
        request = ActionRequest(
            agent_id=agent_id,
            agent_role=agent_role,
            action_type=action_type,
            ticker=ticker,
            side=side,
            quantity=quantity,
            estimated_value=estimated_value,
            tool_name=tool_name,
            file_path=file_path,
            delegation_depth=delegation_depth,
            raw_reasoning=raw_reasoning if raw_reasoning else None,
        )

        result = st.session_state.gate.process(request)

        if result.allowed:
            st.success(f"✅ ALLOWED — Action permitted by GRID policy")
        else:
            st.error(f"❌ BLOCKED — Action denied by GRID policy")

        st.markdown("**Policy Evaluation:**")
        for rule in result.policy_result.rule_results:
            r_icon = "✅" if rule.passed else "❌"
            st.markdown(f"- {r_icon} **{rule.rule_name}**: {rule.reason}")

        if result.execution_data:
            st.markdown("**Execution Result:**")
            st.json(result.execution_data)

        if result.policy_result.block_reasons:
            st.markdown("**Block Reasons:**")
            for reason in result.policy_result.block_reasons:
                st.markdown(f"- 🚫 {reason}")


# ──────────────────────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #666; font-size: 0.9rem;">'
    '🛡️ GRID — Constitutional Enforcement Layer for Autonomous Financial Agents<br>'
    'ArmorIQ x OpenClaw Hackathon'
    '</div>',
    unsafe_allow_html=True,
)
