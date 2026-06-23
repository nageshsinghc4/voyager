"""
transport.py
------------
transport_agent: runs in parallel with other sub-agents.

Uses Tavily web search to gather local transportation information at the
destination — airport transfers, public transit passes, taxi/rideshare
costs — and uses the LLM to normalise into a structured dict.
"""

from __future__ import annotations

import json
import logging

from trip_planner.llm import get_llm, clean_json
from trip_planner.state import TripState
from trip_planner.tools import fetch_transport_info

logger = logging.getLogger(__name__)


def transport_agent(state: TripState) -> dict:
    llm          = get_llm()
    destination  = state["destination"]
    travel_style = state.get("travel_style") or "Mid-range"
    num_travelers = state.get("num_travelers") or 1

    # ── Step 1: Fetch live transport data ─────────────────────────────────
    try:
        raw = fetch_transport_info(destination)
        tool_ok = raw and not raw.startswith("Error")
    except Exception as exc:
        logger.warning("transport_agent: fetch failed (%s)", exc)
        raw     = ""
        tool_ok = False

    data_section = (
        f"\nLIVE TRANSPORT RESEARCH DATA:\n{raw[:4000]}"
        if tool_ok and raw else ""
    )

    # ── Step 2: LLM normalises to schema ──────────────────────────────────
    prompt = f"""You are a local transport expert helping travellers get around efficiently.

Destination  : {destination}
Travel style : {travel_style}
Travelers    : {num_travelers}
{data_section}

Return a single JSON object with exactly these keys:

{{
  "airport_transfer": [
    {{
      "mode":        "Train / Subway",
      "description": "e.g. Heathrow Express to Paddington (15 min)",
      "cost_usd":    22.0,
      "duration":    "15 min",
      "frequency":   "Every 15 min",
      "tips":        "Buy a return for savings"
    }},
    {{
      "mode":        "Taxi / Private Transfer",
      "description": "Metered taxi or pre-booked minicab",
      "cost_usd":    65.0,
      "duration":    "45-60 min",
      "frequency":   "On demand",
      "tips":        "Pre-book online to avoid surge pricing"
    }},
    {{
      "mode":        "Bus",
      "description": "e.g. National Express coach to Victoria",
      "cost_usd":    10.0,
      "duration":    "60-90 min",
      "frequency":   "Every 30 min",
      "tips":        "Cheapest option but slower"
    }}
  ],
  "local_transport": [
    {{
      "mode":             "Metro / Subway / Tube",
      "pass_name":        "e.g. Oyster Card / IC Card / Suica",
      "daily_cost_usd":   12.0,
      "coverage":         "Covers all metro lines and buses",
      "tips":             "Load at least $20, tap in and out every journey"
    }},
    {{
      "mode":             "Bus",
      "pass_name":        "Day Pass",
      "daily_cost_usd":   5.0,
      "coverage":         "City bus network",
      "tips":             "Download the local transit app for real-time arrivals"
    }},
    {{
      "mode":             "Uber / Rideshare",
      "pass_name":        "",
      "daily_cost_usd":   0.0,
      "coverage":         "City-wide",
      "tips":             "Average ride $10-20; surge pricing during peak hours"
    }},
    {{
      "mode":             "Taxi",
      "pass_name":        "",
      "daily_cost_usd":   0.0,
      "coverage":         "City-wide",
      "tips":             "Always use metered taxis or hail from official stands"
    }}
  ],
  "between_activities_estimate": {{
    "avg_ride_usd": 12.0,
    "note": "Typical Uber/taxi fare between popular tourist areas"
  }},
  "tips": [
    "Practical tip 1",
    "Practical tip 2",
    "Practical tip 3"
  ]
}}

Guidelines:
- Provide realistic USD costs based on the destination.
- Include at least 3 airport transfer options (train, taxi, bus where available).
- Include all relevant local transport modes.
- If a city has no metro, omit that entry and add alternatives.
- Return ONLY the JSON object — no markdown fences, no explanation.
"""

    try:
        raw_llm   = llm.invoke(prompt)
        transport = json.loads(clean_json(raw_llm))
        logger.info("transport_agent: data generated for %s", destination)
        return {"transport_info": transport}
    except Exception as exc:
        logger.error("transport_agent failed: %s", exc)
        return {
            "transport_info": None,
            "errors": [f"transport_agent: {exc}"],
        }
