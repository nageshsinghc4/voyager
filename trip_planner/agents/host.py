"""
host.py
-------
Two nodes that bookend the parallel fan-out:

  host_agent    — entry node: validates input, initialises state, logs dispatch.
  merge_results — barrier node: runs after ALL parallel sub-agents complete;
                  assembles the human-readable trip plan.
"""

from __future__ import annotations

import logging
from datetime import date

from rich.panel import Panel

from trip_planner.state import TripState
from trip_planner.agents._base import console

logger = logging.getLogger(__name__)


# ── Entry node ────────────────────────────────────────────────────────────────

def host_agent(state: TripState) -> dict:
    errors: list[str] = []

    for field in ("destination", "start_date", "end_date", "budget_usd"):
        if not state.get(field):
            errors.append(f"Missing required field: '{field}'")

    budget = state.get("budget_usd", 0)
    if budget <= 0:
        errors.append("budget_usd must be a positive number.")

    try:
        start = date.fromisoformat(state.get("start_date", ""))
        end   = date.fromisoformat(state.get("end_date", ""))
        if end <= start:
            errors.append("end_date must be after start_date.")
    except ValueError:
        errors.append("Dates must be in YYYY-MM-DD format.")

    destination = state.get("destination", "").strip().title()

    console.print(Panel(
        f"[bold cyan]Destination:[/] {destination}\n"
        f"[bold cyan]Dates:[/]       {state.get('start_date')} → {state.get('end_date')}\n"
        f"[bold cyan]Budget:[/]      ${budget:,.0f}\n\n"
        f"[dim]Dispatching → flight_agent | stay_agent | "
        f"activities_agent | info_agent[/]",
        title="[bold magenta]AI Trip Planner  —  Orchestrating[/]",
        border_style="magenta",
    ))

    return {
        "destination":       destination,
        "flight_results":    None,
        "stay_results":      None,
        "activity_results":  None,
        "event_results":     None,
        "weather_info":      None,
        "packing_list":      None,
        "food_culture_tips": None,
        "travel_guides":     None,
        "travel_tips":       None,
        "daily_itinerary":   None,
        "final_plan":        None,
        "errors":            errors,
    }


# ── Barrier node ──────────────────────────────────────────────────────────────

def merge_results(state: TripState) -> dict:
    destination = state.get("destination", "Your Destination")
    budget      = state.get("budget_usd", 0)
    flights     = state.get("flight_results")    or []
    stays       = state.get("stay_results")      or []
    acts        = state.get("activity_results")  or []
    weather     = state.get("weather_info")      or {}
    packing     = state.get("packing_list")      or []
    food        = state.get("food_culture_tips") or {}
    guides      = state.get("travel_guides")     or []
    tips        = state.get("travel_tips")       or []
    errors      = state.get("errors")            or []
    nights      = (stays[0].get("nights", 0) if stays else 0) or _calc_nights(state)

    lines: list[str] = []

    lines += [
        "=" * 66,
        f"  TRIP PLAN  —  {destination}",
        f"  {state.get('start_date')} to {state.get('end_date')}  ({nights} nights)",
        f"  Total Budget: ${budget:,.0f}",
        "=" * 66,
    ]

    if weather:
        lines.append("\nWEATHER FORECAST")
        lines.append(f"  Conditions  : {weather.get('conditions', 'N/A')}")
        lines.append(f"  Temperature : {weather.get('temp_range', 'N/A')}")
        lines.append(f"  Rain chance : {weather.get('rain_chance', 'N/A')}")
        forecast = weather.get("forecast", [])
        if forecast:
            lines.append("  Forecast    :")
            for f in forecast[:5]:
                lines.append(f"    • {f}")

    lines.append("\nFLIGHT OPTIONS  (budget: 30%)")
    if flights:
        for i, f in enumerate(flights, 1):
            lines.append(
                f"  {i}. {f.get('airline','?'):<22}"
                f"  {f.get('departure','?')} → {f.get('arrival','?')}"
                f"  |  ${f.get('price_usd', 0):>6,.0f}"
                f"  |  {f.get('stops', 0)} stop(s)"
                f"  |  {f.get('duration','?')}"
                f"  |  {f.get('cabin_class','')}"
            )
        best = min(flights, key=lambda x: x.get("price_usd", 9999))
        lines.append(f"\n  Recommended: {best['airline']}  —  ${best['price_usd']:,.0f}")
    else:
        lines.append("  No flight data available.")

    lines.append("\nHOTEL OPTIONS  (budget: 40%)")
    if stays:
        for i, h in enumerate(stays, 1):
            amenities = ", ".join(h.get("amenities", []))
            lines.append(
                f"  {i}. {'*' * h.get('stars', 3)}  {h.get('name','?'):<28}"
                f"  ${h.get('price_per_night_usd', 0):>5,.0f}/night"
                f"  (${h.get('total_cost_usd', 0):>6,.0f} total)"
                f"  Rating: {h.get('rating','?')}"
            )
            lines.append(f"     {h.get('location','?')}  |  {amenities}")
        best = min(stays, key=lambda x: x.get("price_per_night_usd", 9999))
        lines.append(f"\n  Best value: {best['name']}  —  ${best['price_per_night_usd']:,.0f}/night")
    else:
        lines.append("  No hotel data available.")

    lines.append("\nACTIVITIES  (budget: 30%)")
    total_acts_cost = 0.0
    if acts:
        for i, a in enumerate(acts, 1):
            lines.append(
                f"  {i}. {a.get('name','?'):<32}"
                f"  [{a.get('category','?')}]"
                f"  ${a.get('price_usd', 0):>5,.0f}"
                f"  |  {a.get('duration','?')}"
                f"  |  Rating: {a.get('rating','?')}"
            )
            lines.append(f"     {a.get('description','')}")
            total_acts_cost += a.get("price_usd", 0)
        lines.append(f"\n  Total activities cost: ${total_acts_cost:,.0f}")
    else:
        lines.append("  No activity data available.")

    if food:
        lines.append("\nFOOD & CULTURE")
        must_try = food.get("must_try_foods", [])
        if must_try:
            lines.append(f"  Must-try foods  : {', '.join(must_try)}")
        if food.get("dining_customs"):
            lines.append(f"  Dining customs  : {food['dining_customs']}")
        if food.get("tipping"):
            lines.append(f"  Tipping         : {food['tipping']}")
        for tip in food.get("cultural_tips", []):
            lines.append(f"    • {tip}")

    if packing:
        lines.append("\nPACKING LIST")
        for item in packing:
            lines.append(f"  [ ] {item}")

    if tips:
        lines.append("\nPRACTICAL TRAVEL TIPS")
        for tip in tips:
            lines.append(f"  • {tip}")

    if guides:
        lines.append("\nTOP TRAVEL GUIDES")
        for i, g in enumerate(guides, 1):
            lines.append(f"  {i}. {g.get('title', 'Guide')}")
            lines.append(f"     {g.get('url', '')}")
            snippet = g.get("snippet", "")
            if snippet:
                lines.append(f"     {snippet[:120]}...")

    cheapest_flight  = min(flights, key=lambda x: x.get("price_usd", 0),
                           default={}).get("price_usd", 0)
    cheapest_hotel   = min(stays, key=lambda x: x.get("total_cost_usd", 0),
                           default={}).get("total_cost_usd", 0)
    estimated_total  = cheapest_flight + cheapest_hotel + total_acts_cost
    remaining        = budget - estimated_total
    status           = "ON BUDGET" if remaining >= 0 else "OVER BUDGET"

    lines += [
        "\nBUDGET SUMMARY",
        f"  Flights        : ${cheapest_flight:>8,.0f}",
        f"  Accommodation  : ${cheapest_hotel:>8,.0f}",
        f"  Activities     : ${total_acts_cost:>8,.0f}",
        f"  {'─' * 30}",
        f"  Estimated Total: ${estimated_total:>8,.0f}   (of ${budget:,.0f})",
        f"  Remaining      : ${remaining:>8,.0f}  [{status}]",
    ]

    if errors:
        lines.append("\nWARNINGS")
        for e in errors:
            lines.append(f"  • {e}")

    lines += [
        "\n" + "=" * 66,
        "  (Generating day-by-day itinerary...)",
        "=" * 66,
    ]

    partial_plan = "\n".join(lines)
    console.print(Panel(
        partial_plan,
        title="[bold green]Trip Overview[/]",
        border_style="green",
    ))

    return {
        "nights":           nights,
        "budget_breakdown": {
            "flights":       cheapest_flight,
            "accommodation": cheapest_hotel,
            "activities":    total_acts_cost,
            "total":         estimated_total,
            "remaining":     remaining,
        },
        "final_plan": partial_plan,
    }


def _calc_nights(state: TripState) -> int:
    try:
        return (
            date.fromisoformat(state["end_date"]) -
            date.fromisoformat(state["start_date"])
        ).days
    except Exception:
        return 0
