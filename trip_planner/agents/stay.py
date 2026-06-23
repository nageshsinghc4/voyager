"""
stay.py
-------
stay_agent: fetches live hotel options via SerpAPI Google Hotels,
normalises them with the LLM, and falls back to pure LLM if SerpAPI
is unavailable.
"""

from __future__ import annotations

import json
import logging

from trip_planner.llm import get_llm, clean_json
from trip_planner.state import TripState
from trip_planner.tools import fetch_hotels, attach_google_photos
from trip_planner.config import BUDGET_HOTEL_PCT
from trip_planner.agents._base import nights, is_tool_error

logger = logging.getLogger(__name__)


def stay_agent(state: TripState) -> dict:
    llm               = get_llm()
    n                 = nights(state)
    total_stay_budget = state["budget_usd"] * BUDGET_HOTEL_PCT
    nightly_cap       = total_stay_budget / max(n, 1)
    style             = state.get("travel_style") or "Mid-range"
    travelers         = state.get("num_travelers") or 1
    purpose           = state.get("trip_purpose") or "Leisure"

    style_guide = {
        "Budget":    "Prefer 2-3 star, affordable options. Value-for-money is key.",
        "Mid-range": "Mix of 3-4 star options. Balance quality and price.",
        "Luxury":    "Prefer 4-5 star, premium hotels with top amenities.",
    }.get(style, "Mix of budget, mid-range, and premium options.")

    try:
        raw_data = fetch_hotels(
            destination=state["destination"],
            start_date=state["start_date"],
            end_date=state["end_date"],
            nightly_cap_usd=nightly_cap,
        )
        tool_ok = not is_tool_error(raw_data)
    except Exception as exc:
        logger.warning("stay_agent: SerpAPI unavailable (%s), using LLM fallback", exc)
        raw_data = None
        tool_ok  = False

    if tool_ok:
        prompt = f"""You are an expert hotel search assistant.
Below is LIVE hotel data fetched from Google Hotels for this trip:

  Destination   : {state["destination"]}
  Check-in      : {state["start_date"]}
  Check-out     : {state["end_date"]}
  Nights        : {n}
  Travelers     : {travelers}
  Max per night : ${nightly_cap:.0f}
  Travel style  : {style} — {style_guide}
  Trip purpose  : {purpose}

LIVE HOTEL DATA:
{raw_data}

Using ONLY the data above, select the best 8-10 options that match the travel
style above and return them as a JSON array.
Do NOT invent hotels that are not in the data above.

Each object must have exactly these keys:
  name                 (string)
  stars                (integer 2-5)
  price_per_night_usd  (number)
  amenities            (array of strings, up to 5)
  location             (string, neighbourhood / area)
  rating               (number, out of 5.0)

Return ONLY the JSON array — no markdown fences, no explanation.
Sort by value-for-money (rating / price_per_night_usd) descending.
"""
    else:
        logger.info("stay_agent: using LLM-only fallback prompt")
        prompt = f"""You are an expert hotel search assistant.
Find the best hotel options for:

  Destination   : {state["destination"]}
  Check-in      : {state["start_date"]}
  Check-out     : {state["end_date"]}
  Nights        : {n}
  Travelers     : {travelers}
  Max per night : ${nightly_cap:.0f}
  Travel style  : {style} — {style_guide}
  Trip purpose  : {purpose}

Return ONLY a JSON array — no markdown fences, no explanation.
Each object must have: name, stars, price_per_night_usd, amenities, location, rating.
Align hotel tier with the travel style. Return 8-10 options across different price points.
"""

    # Build name → photo_url map from raw SerpAPI data before LLM normalizes
    photo_map: dict[str, str] = {}
    if tool_ok and raw_data:
        try:
            raw_list = json.loads(raw_data)
            if isinstance(raw_list, list):
                for h in raw_list:
                    name  = (h.get("name") or "").strip().lower()
                    photo = (h.get("photo_url") or "").strip()
                    if name and photo:
                        photo_map[name] = photo
        except Exception:
            pass

    try:
        raw_llm = llm.invoke(prompt)
        results = json.loads(clean_json(raw_llm))
        for h in results:
            h["nights"]         = n
            h["total_cost_usd"] = round(h.get("price_per_night_usd", 0) * n, 2)
            # Step 1: attach from SerpAPI thumbnail map (exact → substring match)
            norm  = (h.get("name") or "").strip().lower()
            photo = photo_map.get(norm, "")
            if not photo:
                for key, url in photo_map.items():
                    if key in norm or norm in key:
                        photo = url
                        break
            h["photo_url"] = photo

        # Step 2: fill remaining blanks with Google Places Photos API
        attach_google_photos(results, state["destination"])

        source = "SerpAPI+LLM" if tool_ok else "LLM-only"
        logger.info("stay_agent [%s]: %d options returned", source, len(results))
        return {"stay_results": results}
    except Exception as exc:
        logger.error("stay_agent failed: %s", exc)
        return {"stay_results": [], "errors": [f"stay_agent: {exc}"]}
