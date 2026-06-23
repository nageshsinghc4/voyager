"""
llm.py
------
Central LLM factory.

All agents import `get_llm()` from here — one place to swap providers,
adjust temperature, or add retry logic for the whole system.

Supports:
  - Azure OpenAI  (default, requires AZURE_OPENAI_* vars)
  - OpenAI        (set LLM_PROVIDER=openai + OPENAI_API_KEY)
  - Mock          (set LLM_PROVIDER=mock  — no key needed, for tests)
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from langchain_openai import AzureChatOpenAI, ChatOpenAI

from trip_planner.config import (
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    OPENAI_API_VERSION,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT,
    OPENAI_API_KEY,
)

# ── Provider protocol ─────────────────────────────────────────────────────────

class LLMClient(Protocol):
    def invoke(self, prompt: str) -> str: ...


# ── Real providers ────────────────────────────────────────────────────────────

class _OpenAIClient:
    def __init__(self) -> None:
        
        self._llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

    def invoke(self, prompt: str) -> str:
        return self._llm.invoke(prompt).content

class _AzureOpenAIClient:
    """
    Azure OpenAI via LangChain's AzureChatOpenAI.
 
    Required environment variables
    ───────────────────────────────
    AZURE_OPENAI_API_KEY    — your Azure resource key
    AZURE_OPENAI_ENDPOINT   — e.g. https://<resource>.openai.azure.com/
    AZURE_OPENAI_DEPLOYMENT — deployment name (e.g. "gpt-4o")
    OPENAI_API_VERSION      — e.g. "2024-12-01-preview" (defaults to that if unset)
    """
    def __init__(self) -> None:

        self._llm = AzureChatOpenAI(
            azure_deployment=AZURE_OPENAI_DEPLOYMENT,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=OPENAI_API_VERSION,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
 
    def invoke(self, prompt: str) -> str:
        return self._llm.invoke(prompt).content
    

# ── Mock provider (deterministic, no API key) ─────────────────────────────────

class _MockClient:
    """Returns realistic but static JSON so the graph runs without any API key."""

    _FLIGHTS = [
        {"airline": "Air India", "departure": "06:20", "arrival": "13:45",
         "price_usd": 310, "cabin_class": "Economy", "stops": 0, "duration": "7h 25m"},
        {"airline": "Emirates", "departure": "14:00", "arrival": "05:30+1",
         "price_usd": 495, "cabin_class": "Economy", "stops": 1, "duration": "15h 30m"},
        {"airline": "IndiGo", "departure": "22:10", "arrival": "06:05+1",
         "price_usd": 225, "cabin_class": "Economy", "stops": 0, "duration": "7h 55m"},
        {"airline": "Singapore Airlines", "departure": "09:00", "arrival": "19:30",
         "price_usd": 640, "cabin_class": "Business", "stops": 0, "duration": "10h 30m"},
    ]

    _HOTELS = [
        {"name": "The Grand Heritage", "stars": 4, "price_per_night_usd": 98,
         "amenities": ["Pool", "WiFi", "Breakfast", "Gym"], "location": "City Centre", "rating": 4.6},
        {"name": "Budget Inn Express", "stars": 3, "price_per_night_usd": 42,
         "amenities": ["WiFi", "AC", "24h Reception"], "location": "Near Airport", "rating": 4.1},
        {"name": "Boutique Stays", "stars": 4, "price_per_night_usd": 115,
         "amenities": ["Spa", "WiFi", "Rooftop Bar", "Concierge"], "location": "Old Town", "rating": 4.8},
        {"name": "Traveller's Lodge", "stars": 2, "price_per_night_usd": 28,
         "amenities": ["WiFi", "Shared Kitchen"], "location": "Backpacker District", "rating": 3.9},
    ]

    _ACTIVITIES = [
        {"name": "City Heritage Walk", "category": "Culture",
         "price_usd": 15, "duration": "3h", "rating": 4.8,
         "description": "Guided tour of historic landmarks and temples."},
        {"name": "Local Street Food Tour", "category": "Food",
         "price_usd": 38, "duration": "4h", "rating": 4.9,
         "description": "Sample 10+ dishes across the best local markets."},
        {"name": "Adventure Zip-line Park", "category": "Adventure",
         "price_usd": 55, "duration": "2h", "rating": 4.7,
         "description": "Canopy zip-line through tropical rainforest."},
        {"name": "Sunset Boat Cruise", "category": "Leisure",
         "price_usd": 30, "duration": "2h", "rating": 4.6,
         "description": "Relaxing cruise with cocktails and panoramic views."},
        {"name": "Cooking Class", "category": "Food",
         "price_usd": 45, "duration": "3h", "rating": 4.8,
         "description": "Learn to cook three traditional local dishes."},
        {"name": "National Park Day Hike", "category": "Nature",
         "price_usd": 20, "duration": "6h", "rating": 4.7,
         "description": "Guided hike through protected national parkland."},
    ]

    def invoke(self, prompt: str) -> str:
        p = prompt.lower()
        if "flight" in p:
            return json.dumps(self._FLIGHTS)
        if "hotel" in p or "stay" in p or "accommodation" in p:
            return json.dumps(self._HOTELS)
        return json.dumps(self._ACTIVITIES)


# ── Public factory ────────────────────────────────────────────────────────────

def get_llm() -> LLMClient:
    """
    Returns the correct LLM client based on environment variables.
 
    Priority:
      LLM_PROVIDER=mock    → _MockClient         (no API key needed)
      LLM_PROVIDER=openai  → _OpenAIClient       (requires OPENAI_API_KEY)
      default / azure      → _AzureOpenAIClient  (requires AZURE_OPENAI_* vars)
    """
    provider = LLM_PROVIDER
    if provider == "mock":
        return _MockClient()
    if provider == "openai":
        return _OpenAIClient()
    return _AzureOpenAIClient()
 


def clean_json(raw: str) -> str:
    """Strip markdown fences that LLMs sometimes wrap around JSON."""
    return re.sub(r"```(?:json)?|```", "", raw).strip()