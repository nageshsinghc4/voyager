"""
state.py
--------
Single source of truth for the entire graph.

Every node receives a copy of TripState and returns a partial dict
containing only the keys it modified. LangGraph merges these updates
automatically before passing state to the next node.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict
import operator


def _merge_errors(existing: list[str], new: list[str]) -> list[str]:
    """Custom reducer: accumulate errors from all parallel branches."""
    return (existing or []) + (new or [])


class FlightOption(TypedDict):
    airline: str
    departure: str       # "HH:MM"
    arrival: str         # "HH:MM" or "HH:MM+1"
    price_usd: float
    cabin_class: str     # Economy | Business | First
    stops: int
    duration: str        # "Xh Ym"


class HotelOption(TypedDict):
    name: str
    stars: int
    price_per_night_usd: float
    total_cost_usd: float        # price x nights
    nights: int
    amenities: list[str]
    location: str
    rating: float                # out of 5


class ActivityOption(TypedDict):
    name: str
    category: str        # Culture | Food | Adventure | Leisure | Nature
    price_usd: float
    duration: str
    rating: float
    description: str


class EventOption(TypedDict):
    name: str
    venue: str
    venue_address: str
    date: str            # "YYYY-MM-DD"
    time: str            # "HH:MM"
    category: str        # Music | Sports | Arts | Comedy | Family | Film | Other
    price_min: float
    price_max: float
    url: str
    description: str
    nearby_hotels: list[str]


class DayPlan(TypedDict):
    day: int             # 1-based day number
    date: str            # "YYYY-MM-DD"
    morning: str
    afternoon: str
    evening: str
    dining: list[str]    # ["Breakfast: ...", "Lunch: ...", "Dinner: ..."]
    notes: str


class TravelGuide(TypedDict):
    title: str
    url: str
    snippet: str


class RestaurantOption(TypedDict):
    name: str
    cuisine: str
    price_level: str     # $ | $$ | $$$ | $$$$
    rating: float
    address: str
    description: str
    must_try: str


class TransportOption(TypedDict):
    mode: str            # Airport Transfer | Metro | Bus | Taxi | Rideshare | Train | Ferry
    description: str
    estimated_cost_usd: float
    cost_note: str       # "per trip" | "per person" | "daily pass"
    tips: str


class TripState(TypedDict):
    # ── Core inputs ───────────────────────────────────────────────────────────
    destination:      str
    start_date:       str          # "YYYY-MM-DD"
    end_date:         str          # "YYYY-MM-DD"
    budget_usd:       float

    # ── User preference inputs ────────────────────────────────────────────────
    num_travelers:        Optional[int]
    travel_style:         Optional[str]        # Budget | Mid-range | Luxury
    trip_purpose:         Optional[str]        # Leisure | Business | Family | Adventure | Romantic | Solo
    preferred_activities: Optional[list[str]]  # Sightseeing | Nature | Food & Dining | ...
    event_preferences:    Optional[list[str]]  # Music | Sports | Arts | Comedy | Family | Film
    source_city:          Optional[str]        # Departure city (used for visa requirements)

    # ── Sub-agent outputs (populated in parallel) ─────────────────────────────
    flight_results:   Optional[list[FlightOption]]
    stay_results:     Optional[list[HotelOption]]
    activity_results: Optional[list[ActivityOption]]
    event_results:    Optional[list[EventOption]]

    # ── Info-agent outputs (populated in parallel with above) ─────────────────
    weather_info:      Optional[dict]   # {conditions, temp_range, rain_chance, forecast,
                                        #  hourly_forecast, outdoor_caution}
    packing_list:      Optional[list[str]]
    food_culture_tips: Optional[dict]   # {must_try_foods, dining_customs, tipping, cultural_tips}
    travel_guides:     Optional[list[dict]]  # [{title, url, snippet}, ...]
    travel_tips:       Optional[list[str]]

    # ── New parallel-agent outputs ────────────────────────────────────────────
    restaurant_results: Optional[list[RestaurantOption]]
    transport_info:     Optional[dict]  # {airport_transfer: [...], local_transport: [...], tips: [...]}
    visa_info:          Optional[dict]  # {requirement, visa_type, processing_time, cost_usd, ...}

    # ── Itinerary-agent output (populated after merge_results) ────────────────
    daily_itinerary:  Optional[list[DayPlan]]

    # ── Derived fields added by merge_results ─────────────────────────────────
    nights:           Optional[int]
    budget_breakdown: Optional[dict[str, float]]

    # ── Final assembled plan ──────────────────────────────────────────────────
    final_plan:       Optional[str]

    # ── Error accumulator (parallel-safe custom reducer) ──────────────────────
    errors: Annotated[list[str], _merge_errors]
