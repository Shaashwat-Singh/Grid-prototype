"""
GRID — Constitutional Enforcement Dashboard
TRON-level 3D interface with White & Orange theme.
Real-time visibility into every enforcement decision.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import time
from datetime import datetime

from grid.audit_log import AuditLog
from grid.intent_contract import create_demo_contract

# ═══════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="GRID — Constitutional Enforcement",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════════════════════════════
#  TRON CSS — 3D Design, White & Orange, Neon Grid
# ═══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ─── Google Fonts ──────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ─── Root Variables ────────────────────────────────────────── */
:root {
    --tron-bg: #080810;
    --tron-surface: #0D0D1A;
    --tron-card: #111125;
    --tron-orange: #FF6B00;
    --tron-orange-light: #FF8C38;
    --tron-orange-glow: rgba(255, 107, 0, 0.4);
    --tron-orange-subtle: rgba(255, 107, 0, 0.08);
    --tron-white: #FFFFFF;
    --tron-white-dim: rgba(255, 255, 255, 0.7);
    --tron-white-muted: rgba(255, 255, 255, 0.4);
    --tron-green: #00FF88;
    --tron-green-glow: rgba(0, 255, 136, 0.3);
    --tron-red: #FF3355;
    --tron-red-glow: rgba(255, 51, 85, 0.3);
    --tron-border: rgba(255, 107, 0, 0.2);
    --tron-grid-line: rgba(255, 107, 0, 0.06);
}

/* ─── Global Reset ──────────────────────────────────────────── */
.stApp {
    background: var(--tron-bg) !important;
    color: var(--tron-white) !important;
    font-family: 'Inter', sans-serif !important;
}

.stApp::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background:
        linear-gradient(var(--tron-grid-line) 1px, transparent 1px),
        linear-gradient(90deg, var(--tron-grid-line) 1px, transparent 1px);
    background-size: 60px 60px;
    pointer-events: none;
    z-index: 0;
    animation: gridPulse 8s ease-in-out infinite;
}

@keyframes gridPulse {
    0%, 100% { opacity: 0.3; }
    50% { opacity: 0.7; }
}

/* ─── Perspective Floor Grid (3D) ───────────────────────────── */
.stApp::after {
    content: '';
    position: fixed;
    bottom: 0; left: -50%; right: -50%;
    height: 45%;
    background:
        linear-gradient(rgba(255,107,0,0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,107,0,0.05) 1px, transparent 1px);
    background-size: 80px 80px;
    transform: perspective(500px) rotateX(55deg);
    transform-origin: center bottom;
    pointer-events: none;
    z-index: 0;
    mask-image: linear-gradient(to top, rgba(0,0,0,0.6) 0%, transparent 100%);
    -webkit-mask-image: linear-gradient(to top, rgba(0,0,0,0.6) 0%, transparent 100%);
    animation: floorScroll 20s linear infinite;
}

@keyframes floorScroll {
    0% { background-position: 0 0; }
    100% { background-position: 0 80px; }
}

/* ─── Hide Streamlit Defaults ───────────────────────────────── */
#MainMenu, footer, header,
.stDeployButton, [data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1400px !important;
    position: relative;
    z-index: 1;
}

/* ─── Scrollbar ─────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--tron-bg); }
::-webkit-scrollbar-thumb {
    background: var(--tron-orange);
    border-radius: 3px;
}

/* ─── Sidebar ───────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: var(--tron-surface) !important;
    border-right: 1px solid var(--tron-border) !important;
}

/* ─── Metrics & Cards ───────────────────────────────────────── */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, var(--tron-card) 0%, rgba(17,17,37,0.7) 100%);
    border: 1px solid var(--tron-border);
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    box-shadow:
        0 0 20px rgba(255, 107, 0, 0.05),
        inset 0 1px 0 rgba(255, 255, 255, 0.03);
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    transform: perspective(800px) rotateY(0deg);
    position: relative;
    overflow: hidden;
}

div[data-testid="stMetric"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--tron-orange), transparent);
    animation: scanLine 3s linear infinite;
}

@keyframes scanLine {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

div[data-testid="stMetric"]:hover {
    border-color: var(--tron-orange);
    box-shadow:
        0 0 30px var(--tron-orange-glow),
        0 0 60px rgba(255, 107, 0, 0.1),
        inset 0 0 20px rgba(255, 107, 0, 0.03);
    transform: perspective(800px) rotateY(-2deg) translateY(-4px) scale(1.02);
}

div[data-testid="stMetric"] label {
    color: var(--tron-white-muted) !important;
    font-family: 'Orbitron', sans-serif !important;
    font-size: 0.65rem !important;
    font-weight: 500 !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--tron-white) !important;
    font-family: 'Orbitron', sans-serif !important;
    font-weight: 700 !important;
    font-size: 2rem !important;
    text-shadow: 0 0 20px var(--tron-orange-glow);
}

/* ─── Columns & Spacing ─────────────────────────────────────── */
div[data-testid="stHorizontalBlock"] > div {
    position: relative;
    z-index: 1;
}

/* ─── Headings ──────────────────────────────────────────────── */
h1, h2, h3, h4 {
    font-family: 'Orbitron', sans-serif !important;
    color: var(--tron-white) !important;
}

/* ─── Divider ───────────────────────────────────────────────── */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, var(--tron-orange), transparent) !important;
    margin: 2rem 0 !important;
    box-shadow: 0 0 10px var(--tron-orange-glow) !important;
}

/* ─── Buttons ───────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, var(--tron-orange) 0%, var(--tron-orange-light) 100%) !important;
    color: var(--tron-bg) !important;
    font-family: 'Orbitron', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.75rem !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.7rem 2rem !important;
    box-shadow: 0 0 20px var(--tron-orange-glow) !important;
    transition: all 0.3s ease !important;
}

.stButton > button:hover {
    box-shadow: 0 0 40px var(--tron-orange-glow), 0 0 80px rgba(255,107,0,0.2) !important;
    transform: translateY(-2px) !important;
}

/* ─── Tabs ──────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: var(--tron-surface);
    border-radius: 12px;
    padding: 4px;
    border: 1px solid var(--tron-border);
}

.stTabs [data-baseweb="tab"] {
    font-family: 'Orbitron', sans-serif !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--tron-white-muted) !important;
    border-radius: 8px !important;
    padding: 0.6rem 1.5rem !important;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--tron-orange) 0%, var(--tron-orange-light) 100%) !important;
    color: var(--tron-bg) !important;
    box-shadow: 0 0 20px var(--tron-orange-glow);
}

.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ─── Expanders ─────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background: var(--tron-card) !important;
    border: 1px solid var(--tron-border) !important;
    border-radius: 12px !important;
    font-family: 'Orbitron', sans-serif !important;
    font-size: 0.75rem !important;
    letter-spacing: 1px !important;
    color: var(--tron-white) !important;
}

details {
    background: var(--tron-card) !important;
    border: 1px solid var(--tron-border) !important;
    border-radius: 12px !important;
}

/* ─── Data Tables ───────────────────────────────────────────── */
.stDataFrame {
    border: 1px solid var(--tron-border) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

.stDataFrame thead th {
    background: var(--tron-surface) !important;
    color: var(--tron-orange) !important;
    font-family: 'Orbitron', sans-serif !important;
    font-size: 0.65rem !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    border-bottom: 1px solid var(--tron-orange) !important;
}

.stDataFrame td {
    background: var(--tron-card) !important;
    color: var(--tron-white-dim) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem !important;
    border-bottom: 1px solid rgba(255,107,0,0.08) !important;
}

/* ─── Info / Warning / Error Boxes ──────────────────────────── */
div[data-testid="stAlert"] {
    background: var(--tron-card) !important;
    border: 1px solid var(--tron-border) !important;
    border-radius: 12px !important;
    color: var(--tron-white-dim) !important;
}

/* ─── Plotly Charts ─────────────────────────────────────────── */
.js-plotly-plot .plotly .main-svg {
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════════════════════
st.markdown("""
<div style="
    text-align: center;
    padding: 2rem 1rem 1rem;
    position: relative;
">
    <!-- Hexagonal glow -->
    <div style="
        position: absolute;
        top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        width: 300px; height: 300px;
        background: radial-gradient(circle, rgba(255,107,0,0.15) 0%, transparent 70%);
        border-radius: 50%;
        filter: blur(40px);
        pointer-events: none;
    "></div>

    <!-- GRID Logo -->
    <div style="
        display: inline-block;
        position: relative;
        margin-bottom: 0.5rem;
    ">
        <div style="
            font-family: 'Orbitron', sans-serif;
            font-size: 4rem;
            font-weight: 900;
            letter-spacing: 18px;
            background: linear-gradient(135deg, #FFFFFF 0%, #FF6B00 50%, #FF8C38 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            filter: drop-shadow(0 0 30px rgba(255,107,0,0.4));
            animation: logoGlow 4s ease-in-out infinite;
        ">GRID</div>
    </div>

    <div style="
        font-family: 'Orbitron', sans-serif;
        font-size: 0.7rem;
        letter-spacing: 6px;
        text-transform: uppercase;
        color: rgba(255, 107, 0, 0.7);
        margin-bottom: 0.4rem;
    ">Governance · Restriction · Intent · Delegation</div>

    <div style="
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
        color: rgba(255, 255, 255, 0.4);
        max-width: 600px;
        margin: 0 auto;
    ">Constitutional Enforcement Layer for Autonomous Financial Agents</div>
</div>

<style>
@keyframes logoGlow {
    0%, 100% { filter: drop-shadow(0 0 30px rgba(255,107,0,0.4)); }
    50% { filter: drop-shadow(0 0 50px rgba(255,107,0,0.7)) drop-shadow(0 0 80px rgba(255,107,0,0.2)); }
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════════
log = AuditLog()
stats = log.get_stats()
recent = log.get_recent(50)
contract = create_demo_contract()

total = stats["total"]
allowed = stats["allowed"]
blocked = stats["blocked"]
block_rate = stats["block_rate"]


# ═══════════════════════════════════════════════════════════════════
#  STATUS BAR
# ═══════════════════════════════════════════════════════════════════
status_color = "#00FF88" if total > 0 else "#FF6B00"
integrity = contract.verify_integrity()
integrity_text = "VERIFIED" if integrity else "UNVERIFIED"
integrity_color = "#00FF88" if integrity else "#FF3355"

st.markdown(f"""
<div style="
    display: flex;
    justify-content: center;
    gap: 3rem;
    padding: 0.8rem 2rem;
    margin: 0.5rem 0 1.5rem;
    background: linear-gradient(135deg, rgba(13,13,26,0.9) 0%, rgba(17,17,37,0.9) 100%);
    border: 1px solid var(--tron-border);
    border-radius: 50px;
    backdrop-filter: blur(10px);
    max-width: 900px;
    margin-left: auto;
    margin-right: auto;
">
    <div style="display: flex; align-items: center; gap: 8px;">
        <div style="width: 8px; height: 8px; border-radius: 50%; background: {status_color};
                    box-shadow: 0 0 10px {status_color}; animation: pulse 2s infinite;"></div>
        <span style="font-family: 'Orbitron', sans-serif; font-size: 0.6rem; letter-spacing: 2px;
                     color: rgba(255,255,255,0.5); text-transform: uppercase;">
            {'ACTIVE' if total > 0 else 'AWAITING DATA'}
        </span>
    </div>
    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: rgba(255,255,255,0.3);">
        SESSION <span style="color: #FF6B00;">grid-demo-001</span>
    </div>
    <div style="display: flex; align-items: center; gap: 8px;">
        <div style="width: 8px; height: 8px; border-radius: 50%; background: {integrity_color};
                    box-shadow: 0 0 10px {integrity_color};"></div>
        <span style="font-family: 'Orbitron', sans-serif; font-size: 0.6rem; letter-spacing: 2px;
                     color: {integrity_color}; text-transform: uppercase;">
            CONTRACT {integrity_text}
        </span>
    </div>
</div>

<style>
@keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.4; }}
}}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
#  METRICS ROW
# ═══════════════════════════════════════════════════════════════════
m1, m2, m3, m4 = st.columns(4)
m1.metric("⚡ Total Evaluated", total)
m2.metric("✅ Authorized", allowed)
m3.metric("🛡️ Blocked", blocked)
m4.metric("📊 Block Rate", block_rate)

st.divider()


# ═══════════════════════════════════════════════════════════════════
#  TABS
# ═══════════════════════════════════════════════════════════════════
tab_feed, tab_analytics, tab_contract, tab_agents = st.tabs([
    "⚡ LIVE ENFORCEMENT FEED",
    "📊 THREAT ANALYTICS",
    "📜 INTENT CONTRACT",
    "🤖 AGENT MESH"
])


# ─── TAB 1: LIVE FEED ──────────────────────────────────────────
with tab_feed:
    if not recent:
        st.markdown("""
        <div style="
            text-align: center;
            padding: 4rem 2rem;
            background: linear-gradient(135deg, rgba(17,17,37,0.5) 0%, rgba(13,13,26,0.5) 100%);
            border: 1px dashed rgba(255,107,0,0.3);
            border-radius: 16px;
            margin: 2rem 0;
        ">
            <div style="font-family: 'Orbitron', sans-serif; font-size: 1.2rem; color: #FF6B00;
                         margin-bottom: 1rem;">NO ENFORCEMENT DATA</div>
            <div style="font-family: 'Inter', sans-serif; color: rgba(255,255,255,0.4); font-size: 0.9rem;">
                Run the demo to populate the enforcement feed:<br><br>
                <code style="background: rgba(255,107,0,0.1); color: #FF8C38; padding: 8px 16px;
                            border-radius: 8px; font-family: 'JetBrains Mono', monospace;">
                    python demo/run_demo.py
                </code>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for i, entry in enumerate(recent):
            is_allow = entry["result"] == "ALLOW"
            icon = "✅" if is_allow else "🔴"
            verdict_color = "#00FF88" if is_allow else "#FF3355"
            verdict_glow = "rgba(0,255,136,0.2)" if is_allow else "rgba(255,51,85,0.2)"
            border_color = "rgba(0,255,136,0.3)" if is_allow else "rgba(255,51,85,0.3)"
            anim_delay = i * 0.05

            ticker_badge = ""
            if entry.get("ticker"):
                ticker_badge = f"""<span style="background: rgba(255,107,0,0.15); color: #FF8C38;
                    padding: 2px 10px; border-radius: 20px; font-family: 'JetBrains Mono', monospace;
                    font-size: 0.7rem; font-weight: 600; border: 1px solid rgba(255,107,0,0.3);">
                    {entry['ticker']}</span>"""

            value_badge = ""
            if entry.get("order_value"):
                value_badge = f"""<span style="color: rgba(255,255,255,0.5); font-family: 'JetBrains Mono', monospace;
                    font-size: 0.75rem;">${entry['order_value']:,.2f}</span>"""

            st.markdown(f"""
            <div style="
                display: grid;
                grid-template-columns: 50px 80px 160px 120px 1fr auto;
                align-items: center;
                gap: 12px;
                padding: 12px 20px;
                margin-bottom: 4px;
                background: linear-gradient(135deg, rgba(17,17,37,0.6) 0%, rgba(13,13,26,0.4) 100%);
                border-left: 3px solid {verdict_color};
                border-radius: 0 10px 10px 0;
                box-shadow: inset 3px 0 15px {verdict_glow};
                animation: slideIn 0.4s ease {anim_delay}s both;
                transition: all 0.2s ease;
            "
            onmouseover="this.style.background='linear-gradient(135deg, rgba(17,17,37,0.8) 0%, rgba(13,13,26,0.6) 100%)'; this.style.borderLeftColor='{verdict_color}'; this.style.boxShadow='inset 3px 0 25px {verdict_glow}, 0 0 20px {verdict_glow}';"
            onmouseout="this.style.background='linear-gradient(135deg, rgba(17,17,37,0.6) 0%, rgba(13,13,26,0.4) 100%)'; this.style.boxShadow='inset 3px 0 15px {verdict_glow}';"
            >
                <span style="font-size: 1.1rem;">{icon}</span>
                <span style="font-family: 'Orbitron', sans-serif; font-size: 0.65rem; font-weight: 700;
                             letter-spacing: 1px; color: {verdict_color};">
                    {entry['result']}
                </span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;
                             color: rgba(255,255,255,0.6);">
                    {entry['agent_id']}
                </span>
                <span style="font-family: 'Orbitron', sans-serif; font-size: 0.6rem;
                             letter-spacing: 1px; color: rgba(255,107,0,0.7);">
                    {entry['action_type'].upper()}
                </span>
                <span style="font-family: 'Inter', sans-serif; font-size: 0.78rem;
                             color: rgba(255,255,255,0.45); line-height: 1.3;">
                    {entry['reason'][:90]}{'...' if len(entry.get('reason', '')) > 90 else ''}
                </span>
                <span>{ticker_badge} {value_badge}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("""
        <style>
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-20px); }
            to { opacity: 1; transform: translateX(0); }
        }
        </style>
        """, unsafe_allow_html=True)


# ─── TAB 2: ANALYTICS ──────────────────────────────────────────
with tab_analytics:
    if total == 0:
        st.info("Run the demo first to see analytics.")
    else:
        a1, a2 = st.columns(2)

        # ── Enforcement Breakdown (3D Donut) ──
        with a1:
            fig_donut = go.Figure(data=[go.Pie(
                labels=["Authorized", "Blocked"],
                values=[allowed, blocked],
                hole=0.65,
                marker=dict(
                    colors=["#00FF88", "#FF3355"],
                    line=dict(color="#080810", width=3),
                ),
                textfont=dict(family="Orbitron", size=13, color="#FFFFFF"),
                hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>",
            )])

            fig_donut.update_layout(
                title=dict(
                    text="ENFORCEMENT VERDICTS",
                    font=dict(family="Orbitron", size=14, color="#FF6B00"),
                    x=0.5
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="rgba(255,255,255,0.7)"),
                showlegend=True,
                legend=dict(
                    font=dict(family="Orbitron", size=10, color="rgba(255,255,255,0.6)"),
                    bgcolor="rgba(0,0,0,0)",
                ),
                height=380,
                margin=dict(t=60, b=20, l=20, r=20),
                annotations=[dict(
                    text=f"<b>{total}</b><br><span style='font-size:10px'>TOTAL</span>",
                    x=0.5, y=0.5, font_size=28,
                    font_family="Orbitron",
                    font_color="#FF6B00",
                    showarrow=False
                )],
            )
            st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})

        # ── Policy Violations Bar Chart ──
        with a2:
            blocked_data = stats.get("blocked_by_policy", [])
            if blocked_data:
                df_blocked = pd.DataFrame(blocked_data)
                fig_bar = go.Figure(data=[go.Bar(
                    x=df_blocked["count"],
                    y=df_blocked["policy_violated"],
                    orientation="h",
                    marker=dict(
                        color=df_blocked["count"],
                        colorscale=[[0, "#FF6B00"], [1, "#FF3355"]],
                        line=dict(width=0),
                        cornerradius=6,
                    ),
                    text=df_blocked["count"],
                    textposition="inside",
                    textfont=dict(family="Orbitron", size=13, color="white"),
                    hovertemplate="<b>%{y}</b><br>Violations: %{x}<extra></extra>",
                )])

                fig_bar.update_layout(
                    title=dict(
                        text="POLICY VIOLATIONS",
                        font=dict(family="Orbitron", size=14, color="#FF6B00"),
                        x=0.5
                    ),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="JetBrains Mono", color="rgba(255,255,255,0.5)", size=11),
                    xaxis=dict(
                        showgrid=True,
                        gridcolor="rgba(255,107,0,0.08)",
                        zeroline=False,
                        title="",
                    ),
                    yaxis=dict(
                        showgrid=False,
                        title="",
                        autorange="reversed",
                    ),
                    height=380,
                    margin=dict(t=60, b=20, l=20, r=20),
                    bargap=0.3,
                )
                st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
            else:
                st.success("No policy violations recorded.")

        st.divider()

        # ── Enforcement Timeline ──
        if recent:
            st.markdown("""
            <div style="font-family: 'Orbitron', sans-serif; font-size: 0.8rem; letter-spacing: 3px;
                        color: #FF6B00; text-transform: uppercase; margin-bottom: 1rem; text-align: center;">
                ⚡ Enforcement Timeline
            </div>
            """, unsafe_allow_html=True)

            df_timeline = pd.DataFrame(recent)
            if "timestamp" in df_timeline.columns:
                df_timeline["ts"] = pd.to_datetime(df_timeline["timestamp"])
                df_timeline["color"] = df_timeline["result"].map({"ALLOW": "#00FF88", "BLOCK": "#FF3355"})
                df_timeline["idx"] = range(len(df_timeline))

                fig_timeline = go.Figure()

                for result_type, color in [("ALLOW", "#00FF88"), ("BLOCK", "#FF3355")]:
                    mask = df_timeline["result"] == result_type
                    subset = df_timeline[mask]
                    if len(subset) > 0:
                        fig_timeline.add_trace(go.Scatter(
                            x=subset["idx"],
                            y=[1 if result_type == "ALLOW" else 0] * len(subset),
                            mode="markers",
                            marker=dict(
                                size=14,
                                color=color,
                                line=dict(width=2, color="#080810"),
                                symbol="diamond" if result_type == "BLOCK" else "circle",
                            ),
                            name=result_type,
                            hovertemplate=(
                                "<b>%{customdata[0]}</b><br>"
                                "Agent: %{customdata[1]}<br>"
                                "Action: %{customdata[2]}<extra></extra>"
                            ),
                            customdata=subset[["result", "agent_id", "action_type"]].values,
                        ))

                fig_timeline.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter", color="rgba(255,255,255,0.5)"),
                    showlegend=True,
                    legend=dict(
                        font=dict(family="Orbitron", size=10, color="rgba(255,255,255,0.6)"),
                        bgcolor="rgba(0,0,0,0)",
                        orientation="h", x=0.5, xanchor="center", y=1.15,
                    ),
                    xaxis=dict(title="Event Sequence", showgrid=True, gridcolor="rgba(255,107,0,0.06)"),
                    yaxis=dict(
                        tickvals=[0, 1], ticktext=["BLOCK", "ALLOW"],
                        showgrid=True, gridcolor="rgba(255,107,0,0.06)",
                        range=[-0.5, 1.5],
                    ),
                    height=200,
                    margin=dict(t=40, b=40, l=20, r=20),
                )
                st.plotly_chart(fig_timeline, use_container_width=True, config={"displayModeBar": False})

        # ── Agent Activity Breakdown ──
        if recent:
            st.divider()
            st.markdown("""
            <div style="font-family: 'Orbitron', sans-serif; font-size: 0.8rem; letter-spacing: 3px;
                        color: #FF6B00; text-transform: uppercase; margin-bottom: 1rem; text-align: center;">
                🤖 Agent Activity Breakdown
            </div>
            """, unsafe_allow_html=True)

            df_agents = pd.DataFrame(recent)
            agent_stats = df_agents.groupby(["agent_id", "result"]).size().reset_index(name="count")

            fig_agent = go.Figure()
            for result_type, color in [("ALLOW", "#00FF88"), ("BLOCK", "#FF3355")]:
                mask = agent_stats["result"] == result_type
                subset = agent_stats[mask]
                fig_agent.add_trace(go.Bar(
                    x=subset["agent_id"],
                    y=subset["count"],
                    name=result_type,
                    marker=dict(color=color, cornerradius=4, line=dict(width=0)),
                    textposition="inside",
                    textfont=dict(family="Orbitron", size=11),
                ))

            fig_agent.update_layout(
                barmode="stack",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="JetBrains Mono", color="rgba(255,255,255,0.5)", size=11),
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,107,0,0.06)", title="Actions"),
                legend=dict(
                    font=dict(family="Orbitron", size=10, color="rgba(255,255,255,0.6)"),
                    bgcolor="rgba(0,0,0,0)",
                    orientation="h", x=0.5, xanchor="center", y=1.15,
                ),
                height=300,
                margin=dict(t=40, b=40, l=20, r=20),
                bargap=0.4,
            )
            st.plotly_chart(fig_agent, use_container_width=True, config={"displayModeBar": False})


# ─── TAB 3: INTENT CONTRACT ────────────────────────────────────
with tab_contract:
    st.markdown("""
    <div style="font-family: 'Orbitron', sans-serif; font-size: 0.8rem; letter-spacing: 3px;
                color: #FF6B00; text-transform: uppercase; margin-bottom: 0.5rem;">
        📜 Sealed Intent Contract
    </div>
    <div style="font-family: 'Inter', sans-serif; font-size: 0.85rem; color: rgba(255,255,255,0.4);
                margin-bottom: 1.5rem;">
        Immutable declaration of session authority. Cannot be modified by any agent at runtime.
    </div>
    """, unsafe_allow_html=True)

    # Contract hash display
    contract_hash = contract.compute_hash()
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(17,17,37,0.8) 0%, rgba(13,13,26,0.8) 100%);
        border: 1px solid rgba(255,107,0,0.3);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    ">
        <div>
            <div style="font-family: 'Orbitron', sans-serif; font-size: 0.6rem; letter-spacing: 2px;
                        color: rgba(255,107,0,0.6); text-transform: uppercase; margin-bottom: 6px;">
                SHA-256 Contract Hash
            </div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;
                        color: #FF8C38; word-break: break-all;">
                {contract_hash}
            </div>
        </div>
        <div style="
            background: {'rgba(0,255,136,0.1)' if integrity else 'rgba(255,51,85,0.1)'};
            border: 1px solid {'rgba(0,255,136,0.3)' if integrity else 'rgba(255,51,85,0.3)'};
            border-radius: 25px;
            padding: 6px 18px;
            font-family: 'Orbitron', sans-serif;
            font-size: 0.6rem;
            letter-spacing: 2px;
            color: {'#00FF88' if integrity else '#FF3355'};
            white-space: nowrap;
        ">{'🔒 SEALED' if integrity else '⚠️ UNSEALED'}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        # Session Info
        st.markdown(f"""
        <div style="background: var(--tron-card); border: 1px solid var(--tron-border); border-radius: 12px;
                    padding: 1.2rem; margin-bottom: 1rem;">
            <div style="font-family: 'Orbitron', sans-serif; font-size: 0.65rem; letter-spacing: 2px;
                        color: #FF6B00; margin-bottom: 1rem;">SESSION DETAILS</div>
            <div style="display: grid; gap: 10px;">
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: rgba(255,255,255,0.4); font-size: 0.8rem;">Session ID</span>
                    <span style="font-family: 'JetBrains Mono', monospace; color: #fff; font-size: 0.8rem;">{contract.session_id}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: rgba(255,255,255,0.4); font-size: 0.8rem;">Paper Trading</span>
                    <span style="color: #00FF88; font-size: 0.8rem;">{'✓ ENABLED' if contract.paper_trading_only else '✗ DISABLED'}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: rgba(255,255,255,0.4); font-size: 0.8rem;">Created</span>
                    <span style="font-family: 'JetBrains Mono', monospace; color: rgba(255,255,255,0.6); font-size: 0.75rem;">{contract.created_at[:19]}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Trade Policy
        tp = contract.trade_policy
        st.markdown(f"""
        <div style="background: var(--tron-card); border: 1px solid var(--tron-border); border-radius: 12px;
                    padding: 1.2rem;">
            <div style="font-family: 'Orbitron', sans-serif; font-size: 0.65rem; letter-spacing: 2px;
                        color: #FF6B00; margin-bottom: 1rem;">TRADE POLICY</div>
            <div style="display: grid; gap: 10px;">
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: rgba(255,255,255,0.4); font-size: 0.8rem;">Per Order Limit</span>
                    <span style="font-family: 'Orbitron', sans-serif; color: #fff; font-size: 0.85rem; font-weight: 600;">${tp.per_order_usd:,.0f}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: rgba(255,255,255,0.4); font-size: 0.8rem;">Daily Limit</span>
                    <span style="font-family: 'Orbitron', sans-serif; color: #fff; font-size: 0.85rem; font-weight: 600;">${tp.daily_usd:,.0f}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: rgba(255,255,255,0.4); font-size: 0.8rem;">Max Shares/Order</span>
                    <span style="font-family: 'Orbitron', sans-serif; color: #fff; font-size: 0.85rem; font-weight: 600;">{tp.max_shares_per_order}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: rgba(255,255,255,0.4); font-size: 0.8rem;">Allowed Tickers</span>
                    <span style="color: #FF8C38; font-size: 0.8rem;">{', '.join(tp.allowed_tickers)}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: rgba(255,255,255,0.4); font-size: 0.8rem;">Allowed Sides</span>
                    <span style="color: rgba(255,255,255,0.6); font-size: 0.8rem;">{', '.join(tp.allowed_sides)}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        # Goal
        st.markdown(f"""
        <div style="background: var(--tron-card); border: 1px solid var(--tron-border); border-radius: 12px;
                    padding: 1.2rem; margin-bottom: 1rem;">
            <div style="font-family: 'Orbitron', sans-serif; font-size: 0.65rem; letter-spacing: 2px;
                        color: #FF6B00; margin-bottom: 1rem;">DECLARED GOAL</div>
            <div style="font-family: 'Inter', sans-serif; font-size: 0.85rem; color: rgba(255,255,255,0.7);
                        line-height: 1.6;">
                {contract.declared_goal}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Forbidden Tools
        st.markdown(f"""
        <div style="background: var(--tron-card); border: 1px solid rgba(255,51,85,0.2); border-radius: 12px;
                    padding: 1.2rem;">
            <div style="font-family: 'Orbitron', sans-serif; font-size: 0.65rem; letter-spacing: 2px;
                        color: #FF3355; margin-bottom: 1rem;">🚫 FORBIDDEN TOOLS</div>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                {''.join(f'<span style="background: rgba(255,51,85,0.1); border: 1px solid rgba(255,51,85,0.3); color: #FF3355; padding: 4px 12px; border-radius: 20px; font-family: JetBrains Mono, monospace; font-size: 0.7rem;">{t}</span>' for t in contract.forbidden_tools)}
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─── TAB 4: AGENT MESH ─────────────────────────────────────────
with tab_agents:
    st.markdown("""
    <div style="font-family: 'Orbitron', sans-serif; font-size: 0.8rem; letter-spacing: 3px;
                color: #FF6B00; text-transform: uppercase; margin-bottom: 0.5rem;">
        🤖 Agent Authority Mesh
    </div>
    <div style="font-family: 'Inter', sans-serif; font-size: 0.85rem; color: rgba(255,255,255,0.4);
                margin-bottom: 1.5rem;">
        Each agent operates with bounded authority. No agent can access tools outside its defined scope.
    </div>
    """, unsafe_allow_html=True)

    agent_colors = {
        "analyst-agent": ("#3B82F6", "rgba(59,130,246,0.15)"),
        "risk-agent": ("#8B5CF6", "rgba(139,92,246,0.15)"),
        "trader-agent": ("#FF6B00", "rgba(255,107,0,0.15)"),
    }

    agent_icons = {
        "analyst-agent": "📊",
        "risk-agent": "🛡️",
        "trader-agent": "💹",
    }

    agent_descriptions = {
        "analyst-agent": "Research & signal generation. Read-only market data access.",
        "risk-agent": "Portfolio exposure validation. Evaluates risk before execution.",
        "trader-agent": "Trade submission through enforcement gate. Terminal node — cannot delegate.",
    }

    dp = contract.delegation_policy

    cols = st.columns(3)
    for i, (agent_id, tools) in enumerate(contract.agent_scopes.items()):
        color, bg = agent_colors.get(agent_id, ("#FF6B00", "rgba(255,107,0,0.15)"))
        icon = agent_icons.get(agent_id, "🤖")
        desc = agent_descriptions.get(agent_id, "")

        can_delegate = True
        if agent_id == "trader-agent":
            can_delegate = dp.trader_can_delegate
        elif agent_id == "analyst-agent":
            can_delegate = dp.analyst_can_delegate
        elif agent_id == "risk-agent":
            can_delegate = dp.risk_can_delegate

        with cols[i]:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, {bg} 0%, rgba(13,13,26,0.8) 100%);
                border: 1px solid {color}33;
                border-radius: 16px;
                padding: 1.5rem;
                position: relative;
                overflow: hidden;
                transition: all 0.3s ease;
                min-height: 320px;
            "
            onmouseover="this.style.borderColor='{color}'; this.style.boxShadow='0 0 30px {color}33';"
            onmouseout="this.style.borderColor='{color}33'; this.style.boxShadow='none';"
            >
                <!-- Top accent line -->
                <div style="position: absolute; top: 0; left: 0; right: 0; height: 2px;
                            background: linear-gradient(90deg, transparent, {color}, transparent);"></div>

                <div style="text-align: center; margin-bottom: 1rem;">
                    <span style="font-size: 2rem;">{icon}</span>
                </div>

                <div style="font-family: 'Orbitron', sans-serif; font-size: 0.75rem; letter-spacing: 2px;
                            color: {color}; text-align: center; margin-bottom: 0.3rem; text-transform: uppercase;">
                    {agent_id}
                </div>

                <div style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: rgba(255,255,255,0.4);
                            text-align: center; margin-bottom: 1.2rem; line-height: 1.4;">
                    {desc}
                </div>

                <div style="font-family: 'Orbitron', sans-serif; font-size: 0.55rem; letter-spacing: 2px;
                            color: rgba(255,255,255,0.3); margin-bottom: 0.5rem;">AUTHORIZED TOOLS</div>

                <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 1rem;">
                    {''.join(f'<span style="background: {color}15; border: 1px solid {color}33; color: {color}; padding: 3px 10px; border-radius: 15px; font-family: JetBrains Mono, monospace; font-size: 0.65rem;">{t}</span>' for t in tools)}
                </div>

                <div style="display: flex; align-items: center; gap: 6px; margin-top: auto;">
                    <div style="width: 6px; height: 6px; border-radius: 50%;
                                background: {'#00FF88' if can_delegate else '#FF3355'};
                                box-shadow: 0 0 8px {'rgba(0,255,136,0.5)' if can_delegate else 'rgba(255,51,85,0.5)'};
                    "></div>
                    <span style="font-family: 'Orbitron', sans-serif; font-size: 0.55rem; letter-spacing: 1px;
                                 color: {'#00FF88' if can_delegate else '#FF3355'};">
                        {'CAN DELEGATE' if can_delegate else 'TERMINAL NODE'}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Agent flow diagram
    st.markdown("""
    <div style="
        margin-top: 2rem;
        padding: 1.5rem;
        background: linear-gradient(135deg, rgba(17,17,37,0.5) 0%, rgba(13,13,26,0.5) 100%);
        border: 1px solid var(--tron-border);
        border-radius: 16px;
        text-align: center;
    ">
        <div style="font-family: 'Orbitron', sans-serif; font-size: 0.65rem; letter-spacing: 3px;
                    color: rgba(255,107,0,0.5); margin-bottom: 1rem;">ENFORCEMENT FLOW</div>
        <div style="
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            flex-wrap: wrap;
        ">
            <span style="background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3);
                         color: #3B82F6; padding: 8px 16px; border-radius: 10px;
                         font-family: 'Orbitron', sans-serif; font-size: 0.65rem; letter-spacing: 1px;">
                📊 ANALYST
            </span>
            <span style="color: #FF6B00; font-family: 'Orbitron', sans-serif; font-size: 1.2rem;">→</span>
            <span style="background: rgba(139,92,246,0.15); border: 1px solid rgba(139,92,246,0.3);
                         color: #8B5CF6; padding: 8px 16px; border-radius: 10px;
                         font-family: 'Orbitron', sans-serif; font-size: 0.65rem; letter-spacing: 1px;">
                🛡️ RISK
            </span>
            <span style="color: #FF6B00; font-family: 'Orbitron', sans-serif; font-size: 1.2rem;">→</span>
            <span style="background: rgba(255,107,0,0.15); border: 1px solid rgba(255,107,0,0.3);
                         color: #FF6B00; padding: 8px 16px; border-radius: 10px;
                         font-family: 'Orbitron', sans-serif; font-size: 0.65rem; letter-spacing: 1px;">
                💹 TRADER
            </span>
            <span style="color: #FF6B00; font-family: 'Orbitron', sans-serif; font-size: 1.2rem;">→</span>
            <span style="background: linear-gradient(135deg, rgba(255,107,0,0.2) 0%, rgba(255,51,85,0.2) 100%);
                         border: 1px solid rgba(255,107,0,0.4); color: #FFFFFF; padding: 8px 20px;
                         border-radius: 10px; font-family: 'Orbitron', sans-serif; font-size: 0.65rem;
                         letter-spacing: 1px; box-shadow: 0 0 15px rgba(255,107,0,0.2);">
                ⚡ GRID GATE
            </span>
            <span style="color: #FF6B00; font-family: 'Orbitron', sans-serif; font-size: 1.2rem;">→</span>
            <span style="background: rgba(0,255,136,0.1); border: 1px solid rgba(0,255,136,0.3);
                         color: #00FF88; padding: 8px 16px; border-radius: 10px;
                         font-family: 'Orbitron', sans-serif; font-size: 0.65rem; letter-spacing: 1px;">
                🏦 ALPACA
            </span>
        </div>
        <div style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: rgba(255,255,255,0.3);
                    margin-top: 1rem;">
            Every action passes through the GRID enforcement gate. No agent has direct market access.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
#  FOOTER
# ═══════════════════════════════════════════════════════════════════
st.markdown(f"""
<div style="
    text-align: center;
    padding: 2rem 1rem;
    margin-top: 3rem;
    border-top: 1px solid rgba(255,107,0,0.1);
">
    <div style="font-family: 'Orbitron', sans-serif; font-size: 0.6rem; letter-spacing: 4px;
                color: rgba(255,107,0,0.3); margin-bottom: 0.3rem;">
        GRID v0.2.0 — CONSTITUTIONAL ENFORCEMENT LAYER
    </div>
    <div style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: rgba(255,255,255,0.2);">
        ArmorIQ × OpenClaw Hackathon · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
#  AUTO-REFRESH
# ═══════════════════════════════════════════════════════════════════
time.sleep(5)
st.rerun()
