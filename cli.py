#!/usr/bin/env python3
"""
cli.py
------
Command-line interface for the Trip Planner.

Usage (interactive):
    python cli.py

Usage (one-shot):
    python cli.py --destination "Tokyo, Japan" \\
                  --start 2025-10-01 \\
                  --end   2025-10-08 \\
                  --budget 3500

Usage (mock LLM, no API key):
    LLM_PROVIDER=mock python cli.py

After the plan is generated you enter a chat session where you can ask
follow-up questions (type 'pdf' to export a PDF, 'quit' to exit).
"""

from __future__ import annotations

import argparse
import sys
import logging

from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt, FloatPrompt

load_dotenv()

console = Console()
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s  %(name)s  %(message)s",
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="AI Trip Planner — powered by LangGraph multi-agent system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--destination", "-d", type=str,   default=None)
    p.add_argument("--start",       "-s", type=str,   default=None, metavar="YYYY-MM-DD")
    p.add_argument("--end",         "-e", type=str,   default=None, metavar="YYYY-MM-DD")
    p.add_argument("--budget",      "-b", type=float, default=None, metavar="USD")
    p.add_argument("--no-chat",           action="store_true",
                   help="Skip the interactive chat session after planning")
    p.add_argument("--pdf",               type=str,   default=None, metavar="PATH",
                   help="Auto-export PDF to this path after planning")
    p.add_argument("--verbose",     "-v", action="store_true",
                   help="Enable debug logging")
    return p.parse_args()


def _prompt_inputs() -> tuple[str, str, str, float]:
    """Interactively prompt the user for trip details."""
    console.rule("[bold magenta]AI Trip Planner[/]")
    console.print("[dim]Powered by LangGraph · Multi-Agent System[/]\n")
    destination = Prompt.ask("[cyan]Destination[/]",  default="Bali, Indonesia")
    start_date  = Prompt.ask("[cyan]Start date[/]",   default="2025-09-05")
    end_date    = Prompt.ask("[cyan]End date[/]",     default="2025-09-12")
    budget      = FloatPrompt.ask("[cyan]Budget (USD)[/]", default=2500)
    return destination, start_date, end_date, budget


def _run_chat(result: dict) -> None:
    """Interactive Q&A loop using the generated trip plan as context."""
    from trip_planner.chat import ChatSession

    session = ChatSession(result)

    console.print("\n[bold cyan]Chat Mode[/] — Ask anything about your trip.")
    console.print("[dim]Commands:  'pdf [filename]' to export PDF  |  'quit' to exit[/]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/]").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        lower = user_input.lower()

        if lower in ("quit", "exit", "q", "bye"):
            console.print("[dim]Goodbye! Have a great trip.[/]")
            break

        if lower.startswith("pdf"):
            parts    = user_input.split(maxsplit=1)
            pdf_path = parts[1] if len(parts) > 1 else "trip_plan.pdf"
            _export_pdf(result, pdf_path)
            continue

        answer = session.ask(user_input)
        console.print(f"\n[bold cyan]Assistant:[/] {answer}\n")


def _export_pdf(result: dict, pdf_path: str) -> None:
    """Export the trip plan to a PDF and print confirmation."""
    from trip_planner.pdf_export import export_pdf

    try:
        abs_path = export_pdf(result, pdf_path)
        console.print(f"[bold green]PDF exported:[/] {abs_path}")
    except Exception as exc:
        console.print(f"[bold red]PDF export failed:[/] {exc}")


def main() -> int:
    args = _parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Collect inputs
    if all([args.destination, args.start, args.end, args.budget]):
        destination = args.destination
        start_date  = args.start
        end_date    = args.end
        budget      = args.budget
    else:
        destination, start_date, end_date, budget = _prompt_inputs()

    # Import here so env vars (e.g. LLM_PROVIDER) are set before the module loads
    from trip_planner import plan_trip

    try:
        result = plan_trip(
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            budget_usd=budget,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/]")
        return 1
    except Exception as exc:
        console.print(f"\n[bold red]Error:[/] {exc}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    # Auto-export PDF if --pdf flag was passed
    if args.pdf:
        _export_pdf(result, args.pdf)

    # Enter chat session unless suppressed
    if not args.no_chat:
        _run_chat(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
