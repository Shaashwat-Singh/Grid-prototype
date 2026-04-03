#!/usr/bin/env python3
"""
GRID Demo Runner — Interactive demonstration of constitutional enforcement.

Runs through pre-built scenarios that demonstrate GRID's enforcement
capabilities: authorized trades, ticker restrictions, size limits,
daily caps, tool scoping, prompt injection detection, and delegation
depth enforcement.

Usage:
    python -m demo.run_demo
    python -m demo.run_demo --scenario 3
    python -m demo.run_demo --agent-flow
"""

import argparse
import sys
import os
from typing import Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from grid.intent_contract import (
    IntentContract,
    TradeConstraints,
    DataConstraints,
    AgentPermissions,
)
from grid.policy_engine import PolicyEngine, ActionRequest
from grid.audit_log import AuditLog
from grid.enforcement_gate import EnforcementGate
from agents.analyst_agent import AnalystAgent
from agents.risk_agent import RiskAgent
from agents.trader_agent import TraderAgent
from demo.scenarios import get_all_scenarios, get_scenario_by_number

console = Console()


def create_demo_contract() -> IntentContract:
    """Create the standard demo IntentContract."""
    contract = IntentContract(
        user_id="demo_user",
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
            AgentPermissions(
                role="analyst",
                allowed_tools=["market_data", "get_position"],
                can_delegate=False,
            ),
            AgentPermissions(
                role="risk",
                allowed_tools=["market_data", "get_position", "get_portfolio"],
                can_delegate=False,
            ),
            AgentPermissions(
                role="trader",
                allowed_tools=["market_data", "place_order", "get_position"],
                can_delegate=False,
            ),
        ],
        max_delegation_depth=2,
    )
    
    # Sign the contract (makes it immutable)
    contract.sign()
    return contract


def print_header():
    """Print the GRID demo header."""
    header = Text()
    header.append("╔══════════════════════════════════════════════════════════╗\n", style="bold cyan")
    header.append("║                                                          ║\n", style="bold cyan")
    header.append("║   ", style="bold cyan")
    header.append("GRID", style="bold white on blue")
    header.append(" — Constitutional Enforcement Demo            ║\n", style="bold cyan")
    header.append("║   Governance • Restriction • Intent • Delegation        ║\n", style="bold cyan")
    header.append("║                                                          ║\n", style="bold cyan")
    header.append("╚══════════════════════════════════════════════════════════╝", style="bold cyan")
    console.print(header)
    console.print()


def print_contract_summary(contract: IntentContract):
    """Display the IntentContract details in a formatted panel."""
    table = Table(box=box.ROUNDED, title="IntentContract", title_style="bold yellow")
    table.add_column("Property", style="cyan", width=25)
    table.add_column("Value", style="white")
    
    table.add_row("Contract ID", contract.contract_id[:16] + "...")
    table.add_row("User", contract.user_id)
    table.add_row("Goal", contract.goal)
    table.add_row("Allowed Tickers", ", ".join(contract.trade_constraints.allowed_tickers))
    table.add_row("Max Per Order", f"${contract.trade_constraints.max_order_value:,.2f}")
    table.add_row("Max Daily", f"${contract.trade_constraints.max_daily_value:,.2f}")
    table.add_row("Order Types", ", ".join(contract.trade_constraints.allowed_order_types))
    table.add_row("Trade Sides", ", ".join(contract.trade_constraints.allowed_sides))
    table.add_row("Market Hours Only", str(contract.trade_constraints.market_hours_only))
    table.add_row("Max Delegation Depth", str(contract.max_delegation_depth))
    table.add_row("Signed", "✓ YES" if contract.is_signed else "✗ NO")
    table.add_row("Integrity", "✓ VALID" if contract.verify_integrity() else "✗ INVALID")
    table.add_row("Hash", contract.contract_hash[:32] + "..." if contract.contract_hash else "N/A")
    
    console.print(table)
    console.print()
    
    # Agent permissions table
    perm_table = Table(box=box.ROUNDED, title="Agent Permissions", title_style="bold yellow")
    perm_table.add_column("Role", style="cyan")
    perm_table.add_column("Allowed Tools", style="white")
    perm_table.add_column("Can Delegate", style="white")
    
    for perm in contract.agent_permissions:
        perm_table.add_row(
            perm.role,
            ", ".join(perm.allowed_tools),
            "Yes" if perm.can_delegate else "No",
        )
    
    console.print(perm_table)
    console.print()


def run_scenario(gate: EnforcementGate, scenario: Dict, index: int):
    """Run a single enforcement scenario."""
    expected = scenario["expected_verdict"]
    expected_color = "green" if expected == "ALLOW" else "red"
    
    console.print(Panel(
        f"[bold]{scenario['description']}[/bold]\n\n"
        f"[dim]Tests: {scenario['tests']}[/dim]\n"
        f"Expected: [{expected_color}]{expected}[/{expected_color}]",
        title=f"[bold yellow]Scenario {index}: {scenario['name']}[/bold yellow]",
        border_style="cyan",
    ))
    
    # Process through the gate
    result = gate.process(scenario["request"])
    
    # Display result
    actual_color = "green" if result.allowed else "red"
    verdict_text = "ALLOW ✓" if result.allowed else "BLOCK ✗"
    match = result.verdict == expected
    match_text = "[bold green]PASS[/bold green]" if match else "[bold red]FAIL[/bold red]"
    
    console.print(f"  Verdict: [{actual_color}]{verdict_text}[/{actual_color}]  |  Test: {match_text}")
    
    # Show policy details
    for rule_result in result.policy_result.rule_results:
        icon = "✓" if rule_result.passed else "✗"
        color = "green" if rule_result.passed else "red"
        console.print(f"    [{color}]{icon}[/{color}] {rule_result.rule_name}: {rule_result.reason}")
    
    if result.execution_data:
        console.print(f"  [dim]Execution: {result.execution_data.get('message', result.execution_data.get('status', 'N/A'))}[/dim]")
    
    console.print()
    return match


def run_all_scenarios(gate: EnforcementGate):
    """Run all pre-built scenarios."""
    console.print(Panel(
        "[bold]Running all 7 enforcement scenarios[/bold]\n"
        "Each scenario tests a different GRID enforcement capability.",
        title="[bold cyan]Enforcement Test Suite[/bold cyan]",
        border_style="cyan",
    ))
    console.print()
    
    scenarios = get_all_scenarios()
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        passed = run_scenario(gate, scenario, i)
        results.append((scenario["name"], passed))
    
    # Summary table
    console.print()
    summary = Table(box=box.ROUNDED, title="Test Results", title_style="bold yellow")
    summary.add_column("#", style="cyan", width=3)
    summary.add_column("Scenario", style="white")
    summary.add_column("Result", style="white", justify="center")
    
    for i, (name, passed) in enumerate(results, 1):
        result_text = "[green]PASS ✓[/green]" if passed else "[red]FAIL ✗[/red]"
        summary.add_row(str(i), name, result_text)
    
    total_passed = sum(1 for _, p in results if p)
    summary.add_row("", "[bold]Total[/bold]", f"[bold]{total_passed}/{len(results)}[/bold]")
    
    console.print(summary)
    return results


def run_agent_flow(gate: EnforcementGate):
    """
    Run the full agent pipeline: Analyst → Risk → Trader.
    
    Demonstrates the complete OpenClaw-compatible agent mesh
    with GRID enforcement at every step.
    """
    console.print(Panel(
        "[bold]Full Agent Pipeline Demo[/bold]\n"
        "AnalystAgent → RiskAgent → TraderAgent → EnforcementGate\n\n"
        "Each agent operates within bounded authority.\n"
        "All actions pass through the GRID enforcement gate.",
        title="[bold cyan]Agent Flow Demo[/bold cyan]",
        border_style="cyan",
    ))
    console.print()
    
    # Initialize agents
    analyst = AnalystAgent(gate, agent_id="analyst_001")
    risk = RiskAgent(gate, agent_id="risk_001", portfolio_value=100000.0)
    trader = TraderAgent(gate, agent_id="trader_001")
    
    console.print("[bold yellow]Step 1: AnalystAgent — Research & Signal Generation[/bold yellow]")
    console.print("─" * 60)
    signals = analyst.analyze("AAPL")
    
    if not signals:
        console.print("[red]No signals generated. Aborting flow.[/red]")
        return
    
    signal = signals[0]
    console.print(f"  Signal: {signal.ticker} {signal.signal_type} (strength: {signal.strength:.0%})")
    console.print(f"  Price: ${signal.price:.2f}")
    console.print(f"  Reasoning: {signal.reasoning[:100]}...")
    console.print()
    
    console.print("[bold yellow]Step 2: RiskAgent — Exposure Validation[/bold yellow]")
    console.print("─" * 60)
    assessment = risk.evaluate_signal(signal)
    
    console.print(f"  Risk Score: {assessment.risk_score:.2f}")
    console.print(f"  Max Position: {assessment.max_position_size} shares (${assessment.max_position_value:,.2f})")
    console.print(f"  Approved: {'Yes ✓' if assessment.approved else 'No ✗'}")
    console.print()
    
    console.print("[bold yellow]Step 3: TraderAgent — Trade Submission (via EnforcementGate)[/bold yellow]")
    console.print("─" * 60)
    
    if assessment.approved:
        result = trader.submit_from_assessment(signal, assessment)
        console.print()
        console.print(f"  Gate Verdict: {'[green]ALLOW ✓[/green]' if result.allowed else '[red]BLOCK ✗[/red]'}")
    else:
        console.print("  [yellow]Risk assessment not approved — no trade submitted[/yellow]")
    
    console.print()
    
    # Show system integrity
    console.print("[bold yellow]System Integrity Check[/bold yellow]")
    console.print("─" * 60)
    integrity = gate.verify_system_integrity()
    for key, value in integrity.items():
        console.print(f"  {key}: {value}")
    console.print()
    
    # Show audit stats
    console.print("[bold yellow]Audit Log Statistics[/bold yellow]")
    console.print("─" * 60)
    stats = gate.get_audit_stats()
    for key, value in stats.items():
        console.print(f"  {key}: {value}")


def main():
    """Main demo entry point."""
    parser = argparse.ArgumentParser(
        description="GRID Constitutional Enforcement Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m demo.run_demo               # Run all scenarios\n"
            "  python -m demo.run_demo --scenario 3   # Run specific scenario\n"
            "  python -m demo.run_demo --agent-flow   # Run full agent pipeline\n"
        ),
    )
    parser.add_argument(
        "--scenario", "-s", type=int, default=None,
        help="Run a specific scenario (1-7)",
    )
    parser.add_argument(
        "--agent-flow", "-a", action="store_true",
        help="Run the full agent pipeline demo",
    )
    
    args = parser.parse_args()
    
    # Header
    print_header()
    
    # Create and sign the intent contract
    console.print("[bold cyan]Phase 1: Creating IntentContract[/bold cyan]")
    console.print("═" * 60)
    contract = create_demo_contract()
    print_contract_summary(contract)
    
    # Initialize the enforcement gate
    console.print("[bold cyan]Phase 2: Initializing EnforcementGate[/bold cyan]")
    console.print("═" * 60)
    
    audit_log = AuditLog(log_dir="./audit_logs")
    audit_log.clear()  # Clean start for demo
    
    gate = EnforcementGate(
        contract=contract,
        audit_log=audit_log,
        dry_run=True,  # Paper trading simulation
    )
    
    integrity = gate.verify_system_integrity()
    for key, value in integrity.items():
        console.print(f"  {key}: {value}")
    console.print()
    
    # Run scenarios or agent flow
    console.print("[bold cyan]Phase 3: Enforcement Demonstration[/bold cyan]")
    console.print("═" * 60)
    console.print()
    
    if args.agent_flow:
        run_agent_flow(gate)
    elif args.scenario:
        try:
            scenario = get_scenario_by_number(args.scenario)
            run_scenario(gate, scenario, args.scenario)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    else:
        run_all_scenarios(gate)
        console.print()
        console.print("[dim]Run with --agent-flow to see the full agent pipeline demo[/dim]")
    
    # Final stats
    console.print()
    console.print("[bold cyan]Gate Statistics[/bold cyan]")
    console.print("═" * 60)
    stats = gate.get_stats()
    for key, value in stats.items():
        console.print(f"  {key}: {value}")
    
    console.print()
    console.print("[bold green]Demo complete.[/bold green] Audit log saved to ./audit_logs/grid_audit.jsonl")


if __name__ == "__main__":
    main()
