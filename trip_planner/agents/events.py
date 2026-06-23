"""
events.py
---------
events_agent: fetches live events from Ticketmaster Discovery API during
the trip window, then uses the LLM to normalise results and match each
event to nearby hotels from stay_results.

Falls back to LLM-generated events if Ticketmaster is unavailable or
TICKETMASTER_API_KEY is not set.
"""

from __future__ import annotations

import json
import logging

from trip_planner.state import TripState
from trip_planner.llm import get_llm, clean_json
from trip_planner.tools import fetch_events

logger = logging.getLogger(__name__)


def events_agent(state: TripState) -> dict:
    llm   = get_llm()
    dest  = state["destination"]
    s0    = state["start_date"]
    s1    = state["end_date"]
    prefs = state.get("event_preferences") or []
    stays = state.get("stay_results") or []

    hotel_names = [h.get("name", "") for h in stays[:5] if h.get("name")]
    hotel_list  = ", ".join(hotel_names) if hotel_names else f"hotels near {dest}"

    raw_events: list[dict] = []
    tool_ok = False

    try:
        raw_json   = fetch_events(dest, s0, s1, prefs or None)
        raw_events = json.loads(raw_json)
        if isinstance(raw_events, list) and len(raw_events) > 0:
            tool_ok = True
            logger.info("events_agent: %d events fetched from Ticketmaster", len(raw_events))
    except Exception as exc:
        logger.warning("events_agent: Ticketmaster unavailable (%s) — using LLM fallback", exc)

    pref_hint = f"\nFocus on these event types: {', '.join(prefs)}." if prefs else ""

    if tool_ok:
        prompt = f"""You are a travel event curator for {dest}.

LIVE EVENTS (from Ticketmaster) between {s0} and {s1}:
{json.dumps(raw_events, indent=2)[:4000]}

Trip hotels available: {hotel_list}

For each event add a "nearby_hotels" field listing 1-2 hotels from the list
above that are most convenient for attending that event.

Return a JSON array of up to 10 events. Each object must have EXACTLY these keys:
{{
  "name":          "Event name",
  "venue":         "Venue name",
  "venue_address": "City, State",
  "date":          "YYYY-MM-DD",
  "time":          "HH:MM",
  "category":      "Music|Sports|Arts|Comedy|Family|Film|Other",
  "price_min":     0.0,
  "price_max":     0.0,
  "url":           "ticket URL or empty string",
  "description":   "One sentence, max 120 chars",
  "nearby_hotels": ["Hotel A"]
}}

Return ONLY valid JSON — no markdown, no explanation.{pref_hint}"""
    else:
        logger.info("events_agent: generating LLM-only events for %s", dest)
        prompt = f"""You are a travel event curator. Generate 6 realistic events
that could realistically take place in {dest} between {s0} and {s1}.{pref_hint}

Trip hotels: {hotel_list}

Return a JSON array. Each object must have EXACTLY:
{{
  "name":          "Realistic event name",
  "venue":         "Real or plausible venue in {dest}",
  "venue_address": "Neighbourhood, {dest}",
  "date":          "YYYY-MM-DD (within {s0} – {s1})",
  "time":          "HH:MM",
  "category":      "Music|Sports|Arts|Comedy|Family|Other",
  "price_min":     20.0,
  "price_max":     100.0,
  "url":           "",
  "description":   "One sentence",
  "nearby_hotels": ["{hotel_names[0] if hotel_names else 'A nearby hotel'}"]
}}

Return ONLY valid JSON — no markdown, no explanation."""

    try:
        raw_llm = llm.invoke(prompt)
        events  = json.loads(clean_json(raw_llm))
        if not isinstance(events, list):
            events = []
        logger.info("events_agent: %d events processed", len(events))
        return {"event_results": events}
    except Exception as exc:
        logger.error("events_agent failed: %s", exc)
        return {"event_results": [], "errors": [f"events_agent: {exc}"]}
