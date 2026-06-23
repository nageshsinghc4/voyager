"""
chat.py
-------
Conversational interface for asking questions about a generated trip plan.

Usage
-----
    from trip_planner.chat import chat_trip, ChatSession

    # One-shot
    answer = chat_trip(state, "What should I pack for rainy weather?")

    # Stateful session (maintains conversation history)
    session = ChatSession(state)
    print(session.ask("What's the best restaurant for day 2?"))
    print(session.ask("How do I get there from the hotel?"))
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from trip_planner.llm import get_llm

if TYPE_CHECKING:
    from trip_planner.state import TripState

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a knowledgeable, friendly travel assistant helping a traveller
with their upcoming trip.  You have full access to their trip plan below.

Answer questions concisely and specifically, always referencing the actual
trip details (hotel names, activity names, dates, prices) where relevant.
If the plan does not contain the information needed, say so and offer a
general recommendation.

TRIP PLAN:
{context}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Context builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_context(state: dict) -> str:
    """Assemble a compact, readable summary of the trip state for the LLM."""
    parts: list[str] = []

    dest  = state.get("destination", "")
    start = state.get("start_date", "")
    end   = state.get("end_date", "")
    nights = state.get("nights", 0)
    budget = state.get("budget_usd", 0)
    parts.append(
        f"Destination: {dest}\n"
        f"Dates: {start} to {end} ({nights} nights)\n"
        f"Budget: ${budget:,.0f}"
    )

    # Weather
    w = state.get("weather_info") or {}
    if w:
        parts.append(
            f"Weather: {w.get('conditions','')} | "
            f"{w.get('temp_range','')} | "
            f"Rain: {w.get('rain_chance','')}"
        )

    # Flights
    flights = state.get("flight_results") or []
    if flights:
        lines = ["Flights:"]
        for f in flights:
            lines.append(
                f"  {f.get('airline','?')} "
                f"{f.get('departure','?')}→{f.get('arrival','?')} "
                f"${f.get('price_usd',0):,.0f} {f.get('cabin_class','')} "
                f"{f.get('stops',0)} stop(s)"
            )
        parts.append("\n".join(lines))

    # Hotels
    stays = state.get("stay_results") or []
    if stays:
        lines = ["Hotels:"]
        for h in stays:
            lines.append(
                f"  {h.get('name','?')} "
                f"{'*'*h.get('stars',3)} "
                f"${h.get('price_per_night_usd',0):,.0f}/night "
                f"Rating:{h.get('rating','?')} "
                f"Location:{h.get('location','?')}"
            )
        parts.append("\n".join(lines))

    # Activities
    acts = state.get("activity_results") or []
    if acts:
        lines = ["Activities:"]
        for a in acts:
            lines.append(
                f"  {a.get('name','?')} [{a.get('category','?')}] "
                f"${a.get('price_usd',0)}/person {a.get('duration','?')}"
            )
        parts.append("\n".join(lines))

    # Daily itinerary
    daily = state.get("daily_itinerary") or []
    if daily:
        lines = ["Day-by-Day Itinerary:"]
        for d in daily:
            lines.append(f"  Day {d.get('day','?')} ({d.get('date','')})")
            lines.append(f"    Morning: {d.get('morning','')}")
            lines.append(f"    Afternoon: {d.get('afternoon','')}")
            lines.append(f"    Evening: {d.get('evening','')}")
            dining = d.get("dining") or []
            if dining:
                lines.append(f"    Dining: {' | '.join(dining)}")
            if d.get("notes"):
                lines.append(f"    Notes: {d.get('notes')}")
        parts.append("\n".join(lines))

    # Food & Culture
    food = state.get("food_culture_tips") or {}
    if food:
        must = ", ".join(food.get("must_try_foods") or [])
        if must:
            parts.append(f"Must-try foods: {must}")
        if food.get("dining_customs"):
            parts.append(f"Dining customs: {food['dining_customs']}")
        if food.get("tipping"):
            parts.append(f"Tipping: {food['tipping']}")

    # Packing list
    packing = state.get("packing_list") or []
    if packing:
        parts.append("Packing list: " + ", ".join(packing[:12]))

    # Events
    events = state.get("event_results") or []
    if events:
        lines = ["Events during stay:"]
        for e in events:
            price_str = (f"${e.get('price_min',0):.0f}–${e.get('price_max',0):.0f}"
                         if e.get("price_max", 0) > 0 else "Free/TBD")
            lines.append(
                f"  {e.get('name','?')} [{e.get('category','?')}] "
                f"{e.get('date','')} {e.get('time','')} "
                f"@ {e.get('venue','?')} | {price_str}"
            )
            nearby = e.get("nearby_hotels") or []
            if nearby:
                lines.append(f"    Nearby hotels: {', '.join(nearby)}")
        parts.append("\n".join(lines))

    # Travel tips
    tips = state.get("travel_tips") or []
    if tips:
        parts.append("Travel tips: " + " | ".join(tips))

    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# One-shot helper
# ─────────────────────────────────────────────────────────────────────────────

def chat_trip(state: dict, question: str) -> str:
    """
    Ask a single question about the trip plan.

    Parameters
    ----------
    state    : TripState dict returned by plan_trip()
    question : Natural-language question from the user

    Returns
    -------
    LLM answer as a plain string.
    """
    llm     = get_llm()
    context = _build_context(state)
    prompt  = _SYSTEM_PROMPT.format(context=context) + f"\nQuestion: {question}"
    try:
        return llm.invoke(prompt)
    except Exception as exc:
        logger.error("chat_trip failed: %s", exc)
        return f"Sorry, I couldn't answer that right now ({exc})."


# ─────────────────────────────────────────────────────────────────────────────
# Stateful session
# ─────────────────────────────────────────────────────────────────────────────

class ChatSession:
    """
    Maintains a rolling conversation history so follow-up questions work.

    Example
    -------
        session = ChatSession(state)
        print(session.ask("What should I do on day 3?"))
        print(session.ask("How long does that take?"))   # follow-up
    """

    def __init__(self, state: dict, max_history: int = 10) -> None:
        self._llm         = get_llm()
        self._context     = _build_context(state)
        self._history:    list[dict] = []
        self._max_history = max_history

    def ask(self, question: str) -> str:
        """Ask a question; conversation history is preserved across calls."""
        history_text = ""
        for msg in self._history[-(self._max_history * 2):]:
            role    = msg["role"].upper()
            content = msg["content"]
            history_text += f"{role}: {content}\n"

        prompt = (
            _SYSTEM_PROMPT.format(context=self._context)
            + (f"\nConversation so far:\n{history_text}" if history_text else "")
            + f"\nUser: {question}\nAssistant:"
        )

        try:
            answer = self._llm.invoke(prompt)
        except Exception as exc:
            logger.error("ChatSession.ask failed: %s", exc)
            answer = f"Sorry, I couldn't answer that ({exc})."

        self._history.append({"role": "user",      "content": question})
        self._history.append({"role": "assistant", "content": answer})
        return answer

    def clear(self) -> None:
        """Reset conversation history."""
        self._history.clear()
