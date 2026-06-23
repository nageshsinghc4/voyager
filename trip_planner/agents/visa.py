"""
visa.py
-------
visa_agent: runs in parallel with other sub-agents.

Uses Tavily web search to surface visa requirements, processing times,
costs, and application links for the traveller's source country →
destination country route.
"""

from __future__ import annotations

import json
import logging

from trip_planner.llm import get_llm, clean_json
from trip_planner.state import TripState
from trip_planner.tools import fetch_visa_info

logger = logging.getLogger(__name__)


def visa_agent(state: TripState) -> dict:
    llm         = get_llm()
    destination = state["destination"]
    source_city = state.get("source_city") or "New Delhi, India"

    # ── Step 1: Fetch live visa information ───────────────────────────────
    try:
        raw = fetch_visa_info(source_city, destination)
        tool_ok = raw and not raw.startswith("Error")
    except Exception as exc:
        logger.warning("visa_agent: fetch failed (%s)", exc)
        raw     = ""
        tool_ok = False

    data_section = (
        f"\nLIVE VISA RESEARCH DATA:\n{raw[:4000]}"
        if tool_ok and raw else ""
    )

    dest_country = (
        destination.split(",")[-1].strip()
        if "," in destination else destination
    )
    src_country = (
        source_city.split(",")[-1].strip()
        if "," in source_city else source_city
    )

    # ── Step 2: LLM normalises to schema ──────────────────────────────────
    prompt = f"""You are an immigration and travel visa expert.

Source      : {source_city} ({src_country})
Destination : {destination} ({dest_country})
{data_section}

Return a single JSON object with exactly these keys:

{{
  "source_country":      "{src_country}",
  "destination_country": "{dest_country}",
  "requirement":         "Visa Required" | "Visa on Arrival" | "Visa Free" | "eTA Required",
  "visa_type":           "e.g. Standard Visitor Visa / Tourist Visa / e-Visa",
  "processing_time":     "e.g. 3-6 weeks / 2-3 business days / On arrival",
  "validity":            "e.g. 6 months / 30 days / 90 days",
  "cost_usd":            115.0,
  "application_url":     "Official government or embassy application URL",
  "requirements_list":   [
    "Valid passport with at least 6 months validity",
    "Proof of accommodation",
    "Return flight tickets",
    "Bank statements (last 3-6 months)",
    "Travel insurance"
  ],
  "notes": "Any important caveats, recent policy changes, or tips"
}}

Important:
- Base your answer on the live research data when available.
- If the source and destination are the same country, set requirement to "Visa Free" and note it.
- Use the most recent and accurate information you have.
- Return ONLY the JSON object — no markdown fences, no explanation.
"""

    try:
        raw_llm = llm.invoke(prompt)
        visa    = json.loads(clean_json(raw_llm))
        logger.info(
            "visa_agent: %s → %s: %s",
            src_country, dest_country, visa.get("requirement", "unknown"),
        )
        return {"visa_info": visa}
    except Exception as exc:
        logger.error("visa_agent failed: %s", exc)
        return {
            "visa_info": None,
            "errors": [f"visa_agent: {exc}"],
        }
