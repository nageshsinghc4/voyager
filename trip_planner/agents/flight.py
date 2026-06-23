"""
flight.py
---------
flight_agent: fetches live flight options via SerpAPI Google Flights,
normalises them with the LLM, and falls back to pure LLM if SerpAPI
is unavailable.
"""

from __future__ import annotations

import json
import logging

from trip_planner.llm import get_llm, clean_json
from trip_planner.state import TripState
from trip_planner.tools import fetch_flights
from trip_planner.config import BUDGET_FLIGHT_PCT
from trip_planner.agents._base import is_tool_error

logger = logging.getLogger(__name__)


def flight_agent(state: TripState) -> dict:
    llm           = get_llm()
    flight_budget = state["budget_usd"] * BUDGET_FLIGHT_PCT

    try:
        raw_data = fetch_flights(
            destination=state["destination"],
            start_date=state["start_date"],
            end_date=state["end_date"],
            budget_usd=state["budget_usd"],
        )
        tool_ok = not is_tool_error(raw_data)
    except Exception as exc:
        logger.warning("flight_agent: SerpAPI unavailable (%s), using LLM fallback", exc)
        raw_data = None
        tool_ok  = False

    if tool_ok:
        prompt = f"""You are an expert flight search assistant.
Below is LIVE flight data fetched from Google Flights for this trip:

  Destination : {state["destination"]}
  Outbound    : {state["start_date"]}
  Return      : {state["end_date"]}
  Budget cap  : ${flight_budget:.0f} per person (one-way)

LIVE FLIGHT DATA:
{raw_data}

Using ONLY the data above, select the best 8-10 options and return them as a
JSON array. Do NOT invent flights that are not in the data above.

Each object must have exactly these keys:
  airline        (string)
  departure      (string, "HH:MM")
  arrival        (string, "HH:MM" or "HH:MM+1" for next-day)
  price_usd      (number)
  cabin_class    (string: "Economy" | "Business" | "First")
  stops          (integer)
  duration       (string, e.g. "7h 25m")

Return ONLY the JSON array — no markdown fences, no explanation.
Sort by price_usd ascending.
"""
    else:
        logger.info("flight_agent: using LLM-only fallback prompt")
        prompt = f"""You are an expert flight search assistant.
Find the best flight options for this trip:

  Destination : {state["destination"]}
  Outbound    : {state["start_date"]}
  Return      : {state["end_date"]}
  Max budget  : ${flight_budget:.0f} per person (one-way)

Return ONLY a JSON array — no markdown fences, no explanation.
Each object must have exactly these keys:
  airline, departure, arrival, price_usd, cabin_class, stops, duration

Sort by price_usd ascending. Return 8-10 options across different airlines and fare types.
"""

    try:
        raw_llm = llm.invoke(prompt)
        results = json.loads(clean_json(raw_llm))
        source  = "SerpAPI+LLM" if tool_ok else "LLM-only"
        logger.info("flight_agent [%s]: %d options returned", source, len(results))
        return {"flight_results": results}
    except Exception as exc:
        logger.error("flight_agent failed: %s", exc)
        return {"flight_results": [], "errors": [f"flight_agent: {exc}"]}
