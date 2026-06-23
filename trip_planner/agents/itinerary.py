"""
itinerary.py
------------
itinerary_agent: sequential node that runs after merge_results.

Generates a detailed day-by-day itinerary that weaves together:
  • top-rated activities from activities_agent
  • recommended hotel location from stay_agent
  • local dining suggestions from food_culture_tips
  • downtime / relaxation blocks
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from rich.panel import Panel

from trip_planner.llm import get_llm, clean_json
from trip_planner.state import TripState
from trip_planner.agents._base import console, nights

logger = logging.getLogger(__name__)


def itinerary_agent(state: TripState) -> dict:
    llm         = get_llm()
    destination = state["destination"]
    start_date  = state["start_date"]
    n           = nights(state)

    hotels     = state.get("stay_results")      or []
    activities = state.get("activity_results")  or []
    weather    = state.get("weather_info")      or {}
    food       = state.get("food_culture_tips") or {}

    best_hotel = hotels[0].get("name", "your hotel") if hotels else "your hotel"
    hotel_loc  = hotels[0].get("location", destination) if hotels else destination

    act_lines = "\n".join(
        f"  - {a.get('name')} [{a.get('category')}] "
        f"${a.get('price_usd', 0)} | {a.get('duration')} | "
        f"★{a.get('rating', 4.5)} — {a.get('description', '')}"
        for a in activities
    ) or "  - Explore local highlights"

    must_try = ", ".join(food.get("must_try_foods", [])) if food else ""
    customs  = food.get("dining_customs", "") if food else ""

    start = date.fromisoformat(start_date)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(n)]

    prompt = f"""You are an expert travel itinerary planner creating a detailed daily schedule.

TRIP DETAILS
  Destination  : {destination}
  Dates        : {start_date}  ({n} nights)
  Staying at   : {best_hotel} ({hotel_loc})
  Weather      : {weather.get("conditions", "pleasant")} | {weather.get("temp_range", "")}

AVAILABLE ACTIVITIES (use these across the days):
{act_lines}

LOCAL FOOD
  Must-try dishes : {must_try}
  Dining culture  : {customs}

Trip dates: {json.dumps(dates)}

Generate a JSON array of exactly {n} objects — one per day.
Distribute the listed activities across different days (not all on day 1).
Include at least one "downtime / relaxation" block somewhere in the trip.
Each dining entry should reference real local dishes or restaurant types.

Each object must have EXACTLY these keys:
{{
  "day":       1,
  "date":      "YYYY-MM-DD",
  "morning":   "Activity name + brief description + suggested time (e.g. 9:00 AM)",
  "afternoon": "Activity name + brief description + suggested time (e.g. 2:00 PM)",
  "evening":   "Dinner plan / evening activity + suggested time (e.g. 7:00 PM)",
  "dining": [
    "Breakfast: specific suggestion",
    "Lunch: specific suggestion",
    "Dinner: specific restaurant type or dish"
  ],
  "notes":     "1-2 practical tips: transport, booking advice, downtime suggestion"
}}

Return ONLY the JSON array — no markdown fences, no explanation.
"""

    try:
        raw_llm = llm.invoke(prompt)
        daily   = json.loads(clean_json(raw_llm))
        logger.info("itinerary_agent: %d-day itinerary generated", len(daily))
        _print_itinerary(destination, daily)
        return {"daily_itinerary": daily}
    except Exception as exc:
        logger.error("itinerary_agent failed: %s", exc)
        return {"daily_itinerary": [], "errors": [f"itinerary_agent: {exc}"]}


def _print_itinerary(destination: str, daily: list) -> None:
    """Render the day-by-day itinerary as a Rich panel."""
    if not daily:
        return
    lines = ["=" * 66, f"  DAY-BY-DAY ITINERARY  —  {destination}", "=" * 66]
    for day in daily:
        lines.append(f"\nDay {day.get('day','?')}  ({day.get('date','')})")
        lines.append(f"  Morning   : {day.get('morning','')}")
        lines.append(f"  Afternoon : {day.get('afternoon','')}")
        lines.append(f"  Evening   : {day.get('evening','')}")
        for meal in (day.get("dining") or []):
            lines.append(f"    • {meal}")
        if day.get("notes"):
            lines.append(f"  Notes     : {day.get('notes')}")
    lines += ["\n" + "=" * 66, "  Have a great trip!", "=" * 66]
    console.print(Panel(
        "\n".join(lines),
        title="[bold cyan]Day-by-Day Itinerary[/]",
        border_style="cyan",
    ))
