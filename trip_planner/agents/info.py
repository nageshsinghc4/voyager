"""
info.py
-------
info_agent: runs in parallel with flight/stay/activities agents.

1. Fetches live weather via OpenWeatherMap (current + full 3-hourly forecast).
2. Fetches top-5 travel guide links via Tavily.
3. Uses the LLM to generate packing list, food/culture tips, travel tips,
   and an extended hourly weather breakdown with outdoor-caution flags.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from trip_planner.llm import get_llm, clean_json
from trip_planner.state import TripState
from trip_planner.tools import fetch_weather, fetch_travel_guides
from trip_planner.agents._base import nights

logger = logging.getLogger(__name__)


def _extract_hourly_slots(weather_raw: str) -> list[dict]:
    """Parse the HOURLY_SLOTS_JSON block appended by fetch_weather."""
    marker = "=== HOURLY_SLOTS_JSON ==="
    idx = weather_raw.find(marker)
    if idx == -1:
        return []
    try:
        return json.loads(weather_raw[idx + len(marker):].strip())
    except Exception:
        return []


def info_agent(state: TripState) -> dict:
    llm         = get_llm()
    destination = state["destination"]
    start_date  = state["start_date"]
    end_date    = state["end_date"]
    n           = nights(state)
    month_name  = date.fromisoformat(start_date).strftime("%B")

    # ── Step 1: fetch weather ─────────────────────────────────────────────
    try:
        weather_raw = fetch_weather(destination)
        weather_ok  = not weather_raw.startswith("Error")
    except Exception as exc:
        logger.warning("info_agent: weather fetch failed (%s)", exc)
        weather_raw = ""
        weather_ok  = False

    # Extract structured hourly slots (appended as JSON by fetch_weather)
    hourly_slots = _extract_hourly_slots(weather_raw) if weather_ok else []

    # Strip the JSON block from the text sent to the LLM (keeps prompt smaller)
    weather_text = weather_raw
    marker_idx = weather_raw.find("=== HOURLY_SLOTS_JSON ===")
    if marker_idx != -1:
        weather_text = weather_raw[:marker_idx].strip()

    # ── Step 2: fetch travel guides ───────────────────────────────────────
    try:
        travel_guides = fetch_travel_guides(destination, start_date)
    except Exception as exc:
        logger.warning("info_agent: guides fetch failed (%s)", exc)
        travel_guides = []

    # ── Step 3: LLM generates packing, food/culture, travel tips, weather ─
    weather_section = (
        f"\nWEATHER DATA (use to tailor packing, tips, and forecasts):\n{weather_text[:2500]}"
        if weather_ok else ""
    )

    # Build hourly context — group by date for LLM
    hourly_by_date: dict[str, list] = {}
    for slot in hourly_slots:
        hourly_by_date.setdefault(slot["date"], []).append(slot)

    hourly_section = ""
    if hourly_by_date:
        lines = ["\nHOURLY SLOT DATA (3-hour intervals, use for hourly_forecast):"]
        for day_str, slots in hourly_by_date.items():
            lines.append(f"  {day_str}:")
            for s in slots:
                lines.append(
                    f"    {s['time']} [{s['period']}] "
                    f"{s['description']}, {s['temp_c']}C, "
                    f"rain {s['rain_mm']}mm, wind {s['wind_ms']}m/s"
                )
        hourly_section = "\n".join(lines)

    prompt = f"""You are a travel expert preparing comprehensive trip information.

Destination : {destination}
Trip dates  : {start_date} to {end_date} ({n} nights, {month_name})
{weather_section}
{hourly_section}

Return a single JSON object with exactly these five keys:

"weather_summary": {{
  "conditions":  "one-line description of typical weather during the trip",
  "temp_range":  "e.g. 18-26 C / 64-79 F",
  "rain_chance": "Low | Moderate | High",
  "forecast":    [
    "Day 1 (YYYY-MM-DD): <condition>, <temp range>",
    ... one entry per day of the trip (all {n} days if data available, else 3-5 days)
  ],
  "hourly_forecast": [
    {{
      "date": "YYYY-MM-DD",
      "label": "e.g. Monday, Oct 1",
      "slots": [
        {{
          "time":        "09:00",
          "period":      "Morning",
          "temp_c":      22.5,
          "description": "Partly Cloudy",
          "rain_mm":     0.0,
          "wind_ms":     3.2,
          "icon":        "sunny | cloudy | partly-cloudy | rainy | stormy | snowy | windy"
        }}
      ]
    }}
  ],
  "outdoor_caution": [
    "Flag only genuinely risky windows, e.g. 'Day 2 afternoon: Heavy rain (12mm), avoid outdoor activities 14:00-17:00'"
  ]
}}

"packing_list": [
  "category: item description",
  ...
]
Include 18-22 items grouped by: Clothing, Toiletries, Documents, Tech, Health, Misc.
Tailor to the weather and destination type.

"food_culture": {{
  "must_try_foods":  ["dish 1", "dish 2", "dish 3", "dish 4", "dish 5"],
  "dining_customs":  "brief description of local dining culture",
  "tipping":         "local tipping norms",
  "cultural_tips":   ["tip 1", "tip 2", "tip 3", "tip 4"]
}}

"travel_tips": [
  "practical tip 1",
  "practical tip 2",
  "practical tip 3",
  "practical tip 4",
  "practical tip 5"
]

Return ONLY the JSON object — no markdown fences, no explanation.
"""

    try:
        raw_llm = llm.invoke(prompt)
        info    = json.loads(clean_json(raw_llm))
        logger.info("info_agent: packing (%d items), %d guides, %d hourly days",
                    len(info.get("packing_list", [])),
                    len(travel_guides),
                    len(info.get("weather_summary", {}).get("hourly_forecast", [])))
        return {
            "weather_info":      info.get("weather_summary"),
            "packing_list":      info.get("packing_list", []),
            "food_culture_tips": info.get("food_culture"),
            "travel_tips":       info.get("travel_tips", []),
            "travel_guides":     travel_guides,
        }
    except Exception as exc:
        logger.error("info_agent failed: %s", exc)
        return {
            "weather_info":      None,
            "packing_list":      [],
            "food_culture_tips": None,
            "travel_tips":       [],
            "travel_guides":     travel_guides,
            "errors":            [f"info_agent: {exc}"],
        }
