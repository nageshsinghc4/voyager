"""
activities.py
-------------
activities_agent: searches for real activities via Tavily, normalises
results with the LLM, and falls back to pure LLM if Tavily is unavailable.
"""

from __future__ import annotations

import json
import logging

from trip_planner.llm import get_llm, clean_json
from trip_planner.state import TripState
from trip_planner.tools import fetch_activities
from trip_planner.config import BUDGET_ACTIVITIES_PCT

logger = logging.getLogger(__name__)


def activities_agent(state: TripState) -> dict:
    llm               = get_llm()
    activities_budget = state["budget_usd"] * BUDGET_ACTIVITIES_PCT
    prefs             = state.get("preferred_activities") or []
    purpose           = state.get("trip_purpose") or "Leisure"
    style             = state.get("travel_style") or "Mid-range"
    travelers         = state.get("num_travelers") or 1

    pref_context = ""
    if prefs:
        pref_context = f"\n  Preferred interests : {', '.join(prefs)}"
    purpose_context = f"\n  Trip purpose        : {purpose}"
    style_context   = f"\n  Travel style        : {style}"

    try:
        raw_data = fetch_activities(
            destination=state["destination"],
            start_date=state["start_date"],
            end_date=state["end_date"],
            budget_usd=state["budget_usd"],
        )
        tool_ok = not raw_data.startswith("Error fetching")
    except Exception as exc:
        logger.warning("activities_agent: Tavily unavailable (%s), using LLM fallback", exc)
        raw_data = None
        tool_ok  = False

    if tool_ok:
        prompt = f"""You are an expert travel activities planner.
Below is LIVE data from web searches about activities in {state["destination"]}:

  Travel dates       : {state["start_date"]} to {state["end_date"]}
  Activities budget  : ${activities_budget:.0f} total
  Travelers          : {travelers}{pref_context}{purpose_context}{style_context}

LIVE SEARCH DATA:
{raw_data[:6000]}

Based ONLY on the real activities, tours, and experiences mentioned in the
data above, extract and return 5-6 of the best options as a JSON array.
Prioritise activities that match the preferred interests and trip purpose above.
Only include activities that are explicitly mentioned in the data.

Each object must have exactly these keys:
  name         (string)
  category     (string: "Culture" | "Food" | "Adventure" | "Leisure" | "Nature")
  price_usd    (number, per person — use 0 if free, estimate if not mentioned)
  duration     (string, e.g. "3h" — estimate if not mentioned)
  rating       (number out of 5.0 — use 4.5 as default if not mentioned)
  description  (string, one sentence from the search data)

Return ONLY the JSON array — no markdown fences, no explanation.
Ensure a diverse mix of categories. Sort by rating descending.
Total price_usd should not exceed ${activities_budget:.0f}.
"""
    else:
        logger.info("activities_agent: using LLM-only fallback prompt")
        prompt = f"""You are an expert travel activities planner.
Suggest the best activities and experiences for:

  Destination        : {state["destination"]}
  Travel dates       : {state["start_date"]} to {state["end_date"]}
  Activities budget  : ${activities_budget:.0f} total
  Travelers          : {travelers}{pref_context}{purpose_context}{style_context}

Prioritise activities matching the preferred interests and trip purpose above.
Return ONLY a JSON array — no markdown fences, no explanation.
Each object must have: name, category, price_usd, duration, rating, description.
Include a diverse mix. Sort by rating descending. Return 5-6 activities.
"""

    try:
        raw_llm = llm.invoke(prompt)
        results = json.loads(clean_json(raw_llm))
        source  = "Tavily+LLM" if tool_ok else "LLM-only"
        logger.info("activities_agent [%s]: %d options returned", source, len(results))
        return {"activity_results": results}
    except Exception as exc:
        logger.error("activities_agent failed: %s", exc)
        return {"activity_results": [], "errors": [f"activities_agent: {exc}"]}
