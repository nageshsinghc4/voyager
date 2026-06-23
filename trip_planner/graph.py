"""
graph.py
--------
Wires all nodes into a compiled LangGraph StateGraph.

Graph topology
--------------
    START
      |
      v
  host_agent                       <- entry: validate, normalise, init state
      |
      | (conditional edge: dispatch_agents returns Send objects)
      |
   ---+--------+----------+--------+----------+----------+----------+----------+
      v        v          v        v          v          v          v          v
  flight  stay  activities  info  events  transport  visa  restaurant
      |  (parallel)  |      |      |      |          |      |          |
      +--------+-----+------+------+------+----------+------+----------+
               |
               v
         merge_results        <- barrier: aggregate + format basic plan
               |
               v
       itinerary_agent        <- sequential: generate day-by-day plan
               |
              END

Public API
----------
    from trip_planner.graph import plan_trip

    result = plan_trip(
        destination          = "Kyoto, Japan",
        start_date           = "2025-10-01",
        end_date             = "2025-10-08",
        budget_usd           = 3500,
        num_travelers        = 2,
        travel_style         = "Mid-range",
        trip_purpose         = "Leisure",
        preferred_activities = ["Sightseeing", "Food & Dining"],
        event_preferences    = ["Music", "Arts"],
        source_city          = "New Delhi, India",
    )
    print(result["final_plan"])
"""

from __future__ import annotations

import logging
from typing import Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from trip_planner.state import TripState
from trip_planner.agents import (
    host_agent, merge_results,
    flight_agent, stay_agent, activities_agent,
    info_agent, itinerary_agent, events_agent,
    restaurant_agent, visa_agent, transport_agent,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Parallel dispatch edge
# ─────────────────────────────────────────────────────────────────────────────

def dispatch_agents(state: TripState) -> list[Send]:
    """
    Conditional edge called after host_agent completes.

    Returns eight Send objects — one per sub-agent — each carrying the full
    current state. LangGraph executes all eight in parallel and merges their
    partial state updates before advancing to merge_results.
    """
    return [
        Send("flight_agent",      state),
        Send("stay_agent",        state),
        Send("activities_agent",  state),
        Send("info_agent",        state),
        Send("events_agent",      state),
        Send("transport_agent",   state),
        Send("visa_agent",        state),
        Send("restaurant_agent",  state),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Graph builder
# ─────────────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Construct and compile the trip-planner StateGraph."""
    g = StateGraph(TripState)

    # Register nodes
    g.add_node("host_agent",        host_agent)
    g.add_node("flight_agent",      flight_agent)
    g.add_node("stay_agent",        stay_agent)
    g.add_node("activities_agent",  activities_agent)
    g.add_node("info_agent",        info_agent)
    g.add_node("events_agent",      events_agent)
    g.add_node("transport_agent",   transport_agent)
    g.add_node("visa_agent",        visa_agent)
    g.add_node("restaurant_agent",  restaurant_agent)
    g.add_node("merge_results",     merge_results)
    g.add_node("itinerary_agent",   itinerary_agent)

    # Entry edge
    g.add_edge(START, "host_agent")

    # Parallel fan-out via Send
    g.add_conditional_edges(
        "host_agent",
        dispatch_agents,
        [
            "flight_agent", "stay_agent", "activities_agent",
            "info_agent", "events_agent",
            "transport_agent", "visa_agent", "restaurant_agent",
        ],
    )

    # Fan-in: all sub-agents converge on merge_results
    for node in [
        "flight_agent", "stay_agent", "activities_agent",
        "info_agent", "events_agent",
        "transport_agent", "visa_agent", "restaurant_agent",
    ]:
        g.add_edge(node, "merge_results")

    # Sequential: itinerary generation after the barrier
    g.add_edge("merge_results",   "itinerary_agent")

    # Exit
    g.add_edge("itinerary_agent", END)

    return g.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

# Module-level singleton — built once, reused on every call
_app = build_graph()


def plan_trip(
    destination: str,
    start_date: str,
    end_date: str,
    budget_usd: float,
    num_travelers: int = 1,
    travel_style: str = "Mid-range",
    trip_purpose: str = "Leisure",
    preferred_activities: Optional[list] = None,
    event_preferences: Optional[list] = None,
    source_city: str = "New Delhi, India",
) -> TripState:
    """
    Run the full multi-agent pipeline and return the final TripState.

    Parameters
    ----------
    destination          : Human-readable destination, e.g. "Bali, Indonesia"
    start_date           : Departure date in "YYYY-MM-DD" format
    end_date             : Return date in "YYYY-MM-DD" format
    budget_usd           : Total trip budget in US dollars
    num_travelers        : Number of travellers (default 1)
    travel_style         : "Budget" | "Mid-range" | "Luxury"
    trip_purpose         : "Leisure" | "Business" | "Family" | "Adventure" | "Romantic" | "Solo"
    preferred_activities : e.g. ["Sightseeing", "Food & Dining", "Nature"]
    event_preferences    : e.g. ["Music", "Sports", "Arts"]
    source_city          : Departure city for visa requirement lookup
                           e.g. "New Delhi, India" | "New York, USA"
    """
    initial: TripState = {
        "destination":          destination,
        "start_date":           start_date,
        "end_date":             end_date,
        "budget_usd":           budget_usd,
        "num_travelers":        num_travelers,
        "travel_style":         travel_style,
        "trip_purpose":         trip_purpose,
        "preferred_activities": preferred_activities or [],
        "event_preferences":    event_preferences or [],
        "source_city":          source_city,
        "flight_results":       None,
        "stay_results":         None,
        "activity_results":     None,
        "event_results":        None,
        "weather_info":         None,
        "packing_list":         None,
        "food_culture_tips":    None,
        "travel_guides":        None,
        "travel_tips":          None,
        "restaurant_results":   None,
        "transport_info":       None,
        "visa_info":            None,
        "daily_itinerary":      None,
        "nights":               None,
        "budget_breakdown":     None,
        "final_plan":           None,
        "errors":               [],
    }
    logger.info(
        "plan_trip invoked: %s %s->%s $%.0f | %d traveler(s) | %s | %s | from %s",
        destination, start_date, end_date, budget_usd,
        num_travelers, travel_style, trip_purpose, source_city,
    )
    return _app.invoke(initial)
