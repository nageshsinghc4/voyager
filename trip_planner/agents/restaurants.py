"""
restaurants.py
--------------
restaurant_agent: runs in parallel with other sub-agents.

Uses SerpAPI Google Local (with Tavily fallback) to discover restaurants
at the destination, then uses the LLM to normalise results into a typed
RestaurantOption list with cuisine, price level, rating, and must-try dish.
"""

from __future__ import annotations

import json
import logging

from trip_planner.llm import get_llm, clean_json
from trip_planner.state import TripState
from trip_planner.tools import fetch_restaurants, attach_google_photos
from trip_planner.agents._base import is_tool_error

logger = logging.getLogger(__name__)


def restaurant_agent(state: TripState) -> dict:
    llm         = get_llm()
    destination = state["destination"]
    travel_style = state.get("travel_style") or "Mid-range"

    # Get hotel location hint to bias results near accommodation
    hotel_location = ""
    stay = state.get("stay_results") or []
    if stay:
        hotel_location = stay[0].get("location", "")

    # ── Step 1: Fetch raw restaurant data ─────────────────────────────────
    try:
        raw = fetch_restaurants(destination, hotel_location)
        tool_ok = not is_tool_error(raw)
    except Exception as exc:
        logger.warning("restaurant_agent: fetch failed (%s)", exc)
        raw     = ""
        tool_ok = False

    # ── Step 2: LLM normalises to schema ──────────────────────────────────
    data_section = (
        f"\nLIVE RESTAURANT DATA (use this as the basis for your output):\n{raw[:4000]}"
        if tool_ok and raw else ""
    )

    prompt = f"""You are a dining expert curating restaurant recommendations for travellers.

Destination  : {destination}
Travel style : {travel_style}
{data_section}

Return a JSON array of exactly 10 restaurant objects. Each object must have
exactly these keys:

{{
  "name":        "Restaurant name",
  "cuisine":     "Primary cuisine type (e.g. Italian, Local/Traditional, Japanese, Seafood)",
  "price_level": "$" | "$$" | "$$$" | "$$$$",
  "rating":      4.3,
  "address":     "Street address or neighbourhood",
  "description": "1-2 sentence description including atmosphere and speciality",
  "must_try":    "One signature dish or item to order"
}}

Guidelines:
- Cover a variety of cuisine types and price levels.
- Include 2-3 places under $$ for budget-conscious travellers.
- Include at least 2 places serving authentic local cuisine.
- Ratings should be realistic (3.5–4.9 range).
- If live data is provided, prefer real venue names from it.
- Return ONLY the JSON array — no markdown fences, no explanation.
"""

    # Build name → photo_url map from raw SerpAPI data before LLM normalizes
    photo_map: dict[str, str] = {}
    if tool_ok and raw:
        try:
            raw_list = json.loads(raw)
            if isinstance(raw_list, list):
                for r in raw_list:
                    name  = (r.get("name") or "").strip().lower()
                    photo = (r.get("photo_url") or "").strip()
                    if name and photo:
                        photo_map[name] = photo
        except Exception:
            pass

    try:
        raw_llm = llm.invoke(prompt)
        results = json.loads(clean_json(raw_llm))
        if not isinstance(results, list):
            results = []
        for rr in results:
            norm  = (rr.get("name") or "").strip().lower()
            photo = photo_map.get(norm, "")
            if not photo:
                for key, url in photo_map.items():
                    if key in norm or norm in key:
                        photo = url
                        break
            rr["photo_url"] = photo

        # Fill remaining blanks with Google Places Photos API
        attach_google_photos(results, destination)

        logger.info("restaurant_agent: %d restaurants generated for %s",
                    len(results), destination)
        return {"restaurant_results": results[:10]}
    except Exception as exc:
        logger.error("restaurant_agent failed: %s", exc)
        return {
            "restaurant_results": [],
            "errors": [f"restaurant_agent: {exc}"],
        }
