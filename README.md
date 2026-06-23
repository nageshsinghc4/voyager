# Trip Planner — Multi-Agent AI Orchestration

A production-grade trip planning system that dispatches 8 specialized AI agents in parallel, integrates live data from 5 external APIs, and assembles a complete travel itinerary with budget breakdown, weather forecast, visa guidance, and PDF export.

Built with **LangGraph**, **LangChain**, and **Azure / OpenAI**.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Graph Topology](#graph-topology)
- [Multi-Agent Design](#multi-agent-design)
  - [Host Agent — Entry & Validation](#1-host-agent--entry--validation)
  - [Flight Agent](#2-flight-agent)
  - [Stay Agent](#3-stay-agent)
  - [Activities Agent](#4-activities-agent)
  - [Info Agent — Weather, Packing & Culture](#5-info-agent--weather-packing--culture)
  - [Events Agent](#6-events-agent)
  - [Restaurant Agent](#7-restaurant-agent)
  - [Transport Agent](#8-transport-agent)
  - [Visa Agent](#9-visa-agent)
  - [Merge Results — Barrier Node](#10-merge-results--barrier-node)
  - [Itinerary Agent](#11-itinerary-agent)
- [Shared State Schema](#shared-state-schema)
- [LLM Factory](#llm-factory)
- [Tools & External APIs](#tools--external-apis)
- [Error Handling & Fallbacks](#error-handling--fallbacks)
- [Supporting Modules](#supporting-modules)
- [Setup & Configuration](#setup--configuration)
- [Usage](#usage)
- [Testing](#testing)
- [Extending the System](#extending-the-system)

---

## Architecture Overview

```
                              ┌─────────────────┐
                              │   host_agent    │  Validation & normalisation
                              └────────┬────────┘
                                       │
                              ┌────────▼────────┐
                              │ dispatch_agents │  Returns list[Send] → parallel fan-out
                              └────────┬────────┘
                                       │
          ┌────────┬───────┬───────┬───┴────┬────────┬──────────┬──────────┐
          ▼        ▼       ▼       ▼        ▼        ▼          ▼          ▼
      flight    stay  activities  info    events  restaurant transport   visa
      _agent   _agent  _agent   _agent   _agent   _agent     _agent    _agent
          │        │       │       │        │        │          │          │
          └────────┴───────┴───────┴────────┴────────┴──────────┴──────────┘
                                       │
                              ┌────────▼────────┐
                              │  merge_results  │  Budget calculation, overview
                              └────────┬────────┘
                                       │
                              ┌────────▼────────┐
                              │ itinerary_agent │  Day-by-day schedule
                              └────────┬────────┘
                                       │
                                      END
```

The 8 parallel agents run **concurrently** via LangGraph's `Send()` mechanism. Each agent receives the full state, fetches live data from an external API, normalises the result through the LLM, and returns a partial dict containing only the keys it owns. LangGraph merges these partial updates automatically before passing control to `merge_results`.

---

## Graph Topology

Defined in `trip_planner/graph.py` using LangGraph's `StateGraph`:

```python
# Conditional edge dispatches all agents in one call
g.add_conditional_edges("host_agent", dispatch_agents, [...agent names...])

# All agents converge at the barrier node
for agent in PARALLEL_AGENTS:
    g.add_edge(agent, "merge_results")

# Sequential post-barrier
g.add_edge("merge_results", "itinerary_agent")
g.add_edge("itinerary_agent", END)
```

```python
# dispatch_agents returns a Send list — one per agent
def dispatch_agents(state: TripState) -> list[Send]:
    return [
        Send("flight_agent", state),
        Send("stay_agent", state),
        Send("activities_agent", state),
        Send("info_agent", state),
        Send("events_agent", state),
        Send("restaurant_agent", state),
        Send("transport_agent", state),
        Send("visa_agent", state),
    ]
```

---

## Multi-Agent Design

Every parallel agent follows a consistent two-track pattern:

```
Tool call (live API)
    │
    ├─ SUCCESS → LLM normalises raw response into typed schema
    │
    └─ FAILURE → LLM generates plausible data from context alone
```

This ensures the graph always completes, even when APIs are unavailable.

---

### 1. Host Agent — Entry & Validation

**File**: `trip_planner/agents/host.py`

The entry point for every trip request. Runs sequentially before parallel dispatch.

**Responsibilities**:
- Validates all required fields (`destination`, `start_date`, `end_date`, `budget_usd`)
- Normalises destination to title case
- Checks date ordering and positive budget
- Initialises all output buckets to `None` (prevents stale data across runs)
- Prints a rich welcome panel to the terminal

**Output keys**: All state keys reset to `None`; `errors` initialised; `destination` normalised.

---

### 2. Flight Agent

**File**: `trip_planner/agents/flight.py`  
**Tool**: SerpAPI Google Flights  
**Budget allocation**: 30% of total (`BUDGET_FLIGHT_PCT`)

**How it works**:

1. Resolves destination city → IATA code via a 3-layer lookup:
   - Layer 1: Static dict of 500+ city→IATA mappings (O(1))
   - Layer 2: SerpAPI Google Flights autocomplete
   - Layer 3: Raw city name as fallback
2. Queries Google Flights for round-trip options; returns the 6 cheapest
3. LLM normalises raw flight data into the output schema

**Output schema** (per flight):
```python
{
    "airline": str,
    "departure": "HH:MM",
    "arrival": "HH:MM",        # "HH:MM+1" for overnight
    "price_usd": float,
    "cabin_class": "Economy" | "Business" | "First",
    "stops": int,
    "duration": "Xh Ym"
}
```

---

### 3. Stay Agent

**File**: `trip_planner/agents/stay.py`  
**Tool**: SerpAPI Google Hotels  
**Budget allocation**: 40% of total, divided across nights

**How it works**:

1. Computes nightly budget cap: `total_budget × 0.40 / nights`
2. Queries Google Hotels with that cap
3. LLM normalises results, computes `total_cost_usd = price_per_night × nights`
4. Enriches results with photos via Google Places Photos API (parallel, 6 threads)
5. Sorts by value-for-money: `rating / price`

**Output schema** (per hotel):
```python
{
    "name": str,
    "stars": int,               # 2–5
    "price_per_night_usd": float,
    "amenities": list[str],     # up to 5
    "location": str,
    "rating": float,            # out of 5.0
    "total_cost_usd": float,
    "nights": int,
    "photo_url": str
}
```

---

### 4. Activities Agent

**File**: `trip_planner/agents/activities.py`  
**Tool**: Tavily Web Search  
**Budget allocation**: 30% of total

**How it works**:

1. Runs 4 targeted Tavily searches in parallel:
   - `"best things to do in {destination} tourist activities"`
   - `"top tours and experiences in {destination} with prices"`
   - `"outdoor adventure activities {destination}"`
   - `"cultural food experiences {destination} {year}"`
2. Concatenates all search results into an LLM context window
3. LLM extracts 5–6 real, named activities from the search corpus
4. Prioritises the user's `preferred_activities` list
5. Enforces diverse category mix and total price cap

**Output schema** (per activity):
```python
{
    "name": str,
    "category": "Culture" | "Food" | "Adventure" | "Leisure" | "Nature",
    "price_usd": float,
    "duration": "Xh" | "Xh Ym",
    "rating": float,
    "description": str
}
```

---

### 5. Info Agent — Weather, Packing & Culture

**File**: `trip_planner/agents/info.py`  
**Tools**: OpenWeatherMap API, Tavily Web Search

The most data-intensive parallel agent. It runs a multi-step pipeline inside a single node:

**Step 1 — Weather (OpenWeatherMap)**:
- Geocoding endpoint: city name → lat/lon
- Current weather: temperature, humidity, wind, visibility, sunrise/sunset
- 5-day forecast (3-hourly slots, aggregated to Morning / Afternoon / Evening / Night periods)
- Builds structured hourly forecast with icon mapping: `sunny | cloudy | partly-cloudy | rainy | stormy | snowy | windy`
- Generates outdoor caution flags: e.g., `"Day 2 afternoon: Heavy rain, avoid outdoor activities 14:00–17:00"`

**Step 2 — Travel Guides (Tavily)**:
- Searches for top travel guides for the destination and travel month
- Returns top 5 guides with titles, URLs, and snippets

**Step 3 — LLM Synthesis**:
- Receives full weather report + 3-hourly slots + guide snippets + month context
- Produces 4 structured outputs in a single LLM call:
  - `weather_summary` with hourly forecast and caution flags
  - `packing_list` (18–22 items grouped by category)
  - `food_culture` (must-try dishes, dining customs, tipping norms)
  - `travel_tips` (5 practical tips)

**Output schema** (partial):
```python
{
    "weather_info": {
        "conditions": str,
        "temp_range": "X–Y°C / A–B°F",
        "rain_chance": "Low" | "Moderate" | "High",
        "forecast": [str, ...],      # daily summaries
        "hourly_forecast": [...],    # per-day, per-period slots
        "outdoor_caution": [str, ...]
    },
    "packing_list": [str, ...],
    "food_culture_tips": {
        "must_try_foods": [str, ...],
        "dining_customs": str,
        "tipping": str,
        "cultural_tips": [str, ...]
    },
    "travel_tips": [str, ...]
}
```

---

### 6. Events Agent

**File**: `trip_planner/agents/events.py`  
**Tool**: Ticketmaster Discovery API

**How it works**:

1. Queries Ticketmaster for events between `start_date` and `end_date`
2. Optionally filters by `event_preferences`: `Music | Sports | Arts | Comedy | Family | Film`
3. LLM enriches each event result with `nearby_hotels` (1–2 closest hotels from `stay_results`)
4. On API failure: LLM generates 6 realistic events for the destination and date window

**Output schema** (per event):
```python
{
    "name": str,
    "venue": str,
    "venue_address": str,
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "category": str,
    "price_min": float,
    "price_max": float,
    "url": str,
    "description": str,
    "nearby_hotels": list[str]
}
```

---

### 7. Restaurant Agent

**File**: `trip_planner/agents/restaurants.py`  
**Tool**: SerpAPI Google Local (Tavily as fallback)

**How it works**:

1. Primary: SerpAPI Google Local search for restaurants in the destination
2. Fallback: Tavily web search if SerpAPI is unavailable
3. LLM normalises 10 restaurants ensuring:
   - Mix of cuisine types
   - Spread of price levels (`$` through `$$$$`)
   - At least 2 authentic local cuisine spots
   - A must-try dish for each
4. Photos enriched via Google Places Photos API (parallel workers)

**Output schema** (per restaurant):
```python
{
    "name": str,
    "cuisine": str,
    "price_level": "$" | "$$" | "$$$" | "$$$$",
    "rating": float,
    "address": str,
    "description": str,
    "must_try": str,
    "photo_url": str
}
```

---

### 8. Transport Agent

**File**: `trip_planner/agents/transport.py`  
**Tool**: Tavily Web Search

**How it works**:

Runs 4 targeted Tavily searches:
- `"airport transfer options costs {city}"`
- `"public transport {city} metro bus pass price"`
- `"uber taxi cost {city} average price"`
- `"getting around {city} local transport guide"`

LLM synthesises into a structured transport guide covering airport transfers, local day passes, and average per-ride estimates.

**Output schema** (partial):
```python
{
    "airport_transfer": [{"mode", "cost_usd", "duration", "frequency", "tips"}, ...],
    "local_transport": [{"mode", "pass_name", "daily_cost_usd", "coverage", "tips"}, ...],
    "between_activities_estimate": {"avg_ride_usd": float, "note": str},
    "tips": [str, ...]
}
```

---

### 9. Visa Agent

**File**: `trip_planner/agents/visa.py`  
**Tool**: Tavily Web Search

**How it works**:

Runs 3 targeted searches for visa requirements from `source_city` → `destination`. LLM synthesises into an authoritative visa brief.

**Output schema**:
```python
{
    "source_country": str,
    "destination_country": str,
    "requirement": "Visa Required" | "Visa on Arrival" | "Visa Free" | "eTA Required",
    "visa_type": str,
    "processing_time": str,
    "validity": str,
    "cost_usd": float,
    "application_url": str,
    "requirements_list": [str, ...],
    "notes": str
}
```

---

### 10. Merge Results — Barrier Node

**File**: `trip_planner/agents/host.py` (`merge_results`)

This is the **fan-in barrier**: LangGraph blocks here until all 8 parallel agents have written their results into state.

**Responsibilities**:
1. Computes `nights` from `start_date` / `end_date`
2. Selects the cheapest flight and cheapest hotel from each agent's results
3. Sums all activity costs
4. Calculates `budget_breakdown`:
   ```python
   {
       "flights": float,
       "accommodation": float,
       "activities": float,
       "total": float,
       "remaining": float      # negative = over budget
   }
   ```
5. Generates a human-readable `final_plan` overview string
6. Prints a formatted terminal panel summarising all results

---

### 11. Itinerary Agent

**File**: `trip_planner/agents/itinerary.py`

Runs **sequentially** after `merge_results`, with the full aggregated state available.

**Responsibilities**:
- Generates exactly `nights` day objects (one per travel day)
- Distributes activities across days (not front-loaded)
- Includes at least one downtime / relaxation block
- References specific restaurants from `restaurant_results`
- Provides morning / afternoon / evening breakdown with suggested times

**Output schema** (per day):
```python
{
    "day": int,                 # 1-based
    "date": "YYYY-MM-DD",
    "morning": str,             # activity + suggested time
    "afternoon": str,
    "evening": str,             # dinner plan + time
    "dining": [
        "Breakfast: ...",
        "Lunch: ...",
        "Dinner: ..."
    ],
    "notes": str                # transport tip, booking note, or downtime suggestion
}
```

---

## Shared State Schema

**File**: `trip_planner/state.py`

`TripState` is a `TypedDict` that flows through the entire graph. Each agent reads from it and returns a partial dict with only the keys it owns.

```python
class TripState(TypedDict):
    # ── Input ─────────────────────────────────────────────
    destination: str
    start_date: str
    end_date: str
    budget_usd: float
    num_travelers: int
    travel_style: str           # "Budget" | "Mid-range" | "Luxury"
    trip_purpose: str           # "Leisure" | "Business" | "Family" | ...
    preferred_activities: list[str]
    event_preferences: list[str]
    source_city: str

    # ── Parallel agent outputs ─────────────────────────────
    flight_results: list[FlightOption] | None
    stay_results: list[HotelOption] | None
    activity_results: list[ActivityOption] | None
    event_results: list[EventOption] | None
    weather_info: dict | None
    packing_list: list[str] | None
    food_culture_tips: dict | None
    travel_guides: list[dict] | None
    restaurant_results: list[RestaurantOption] | None
    transport_info: dict | None
    visa_info: dict | None
    travel_tips: list[str] | None

    # ── Derived (merge_results) ────────────────────────────
    nights: int
    budget_breakdown: dict[str, float]
    final_plan: str

    # ── Sequential output ──────────────────────────────────
    daily_itinerary: list[DayPlan] | None

    # ── Error accumulation (custom reducer) ───────────────
    errors: Annotated[list[str], _merge_errors]
```

The `errors` field uses a custom `_merge_errors` reducer so LangGraph can safely merge error lists from all 8 concurrent agents without overwriting.

---

## LLM Factory

**File**: `trip_planner/llm.py`

Centralises LLM construction and exposes a `clean_json()` helper used by every agent.

| Provider | Env var | Model |
|---|---|---|
| `azure` (default) | `AZURE_OPENAI_*` | Configurable via `AZURE_OPENAI_DEPLOYMENT` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `mock` | — | Returns static, pre-baked JSON responses |

```python
from trip_planner.llm import get_llm, clean_json

llm = get_llm()
raw = llm.invoke(prompt)
data = json.loads(clean_json(raw.content))   # strips markdown fences
```

**Settings** (from `config.py`):
- `LLM_TEMPERATURE`: `0.3` — deterministic but not rigid
- `LLM_MAX_TOKENS`: `4096`

---

## Tools & External APIs

All tool wrappers live in `trip_planner/tools.py` (860 lines).

| Tool function | API | Used by |
|---|---|---|
| `fetch_flights()` | SerpAPI Google Flights | flight_agent |
| `fetch_hotels()` | SerpAPI Google Hotels | stay_agent |
| `fetch_restaurants()` | SerpAPI Google Local | restaurant_agent |
| `fetch_activities()` | Tavily Web Search | activities_agent |
| `fetch_travel_guides()` | Tavily Web Search | info_agent |
| `fetch_visa_info()` | Tavily Web Search | visa_agent |
| `fetch_transport_info()` | Tavily Web Search | transport_agent |
| `fetch_weather()` | OpenWeatherMap (3 endpoints) | info_agent |
| `fetch_events()` | Ticketmaster Discovery | events_agent |
| `_google_place_photo_url()` | Google Places Text Search | stay_agent, restaurant_agent |
| `attach_google_photos()` | Google Places (parallel) | stay_agent, restaurant_agent |

**IATA resolution** (`_resolve_iata`): 3-layer lookup — static dict of 500+ cities → SerpAPI autocomplete → raw city name. Prevents flight search failures for lesser-known airports.

---

## Error Handling & Fallbacks

Every agent implements the same resilience pattern:

```
API call
  ├─ Success  →  LLM normalises into schema
  └─ Exception or error payload
       └─  LLM generates plausible data from trip context alone
```

- `is_tool_error(raw)` — shared helper in `agents/_base.py` that checks for error payloads
- Agent failures are appended to `state["errors"]` via the custom reducer — the graph always continues
- `merge_results` prints a warnings panel if any errors were collected
- `restaurant_agent` has an extra intermediate fallback: SerpAPI → Tavily → LLM

---

## Supporting Modules

| Module | Purpose |
|---|---|
| `trip_planner/config.py` | Single source of truth for all env vars, budget percentages, and IATA mappings |
| `trip_planner/chat.py` | Post-planning Q&A. `ChatSession` maintains rolling 10-message history |
| `trip_planner/pdf_export.py` | Generates a full PDF with FPDF2: cover, weather, flights, hotels, activities, events, itinerary, food tips, packing list, budget summary |
| `trip_planner/__init__.py` | Exports `plan_trip(...)` as the public API |
| `dashboard.py` | Panel + hvplot web dashboard with interactive charts and PDF download |
| `cli.py` | Interactive CLI with argument support and post-plan chat session |

---

## Setup & Configuration

**Install dependencies**:
```bash
pip install -r requirements.txt
```

**Create `.env`**:
```
# LLM (choose one)
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
OPENAI_API_VERSION=2024-12-01-preview

# or
LLM_PROVIDER=openai
OPENAI_API_KEY=...

# or (no API key needed, for testing)
LLM_PROVIDER=mock

# Data APIs
SERPAPI_API_KEY=...
TAVILY_API_KEY=...
OPENWEATHERMAP_API_KEY=...
TICKETMASTER_API_KEY=...
GOOGLE_API_KEY=...          # for photo enrichment (optional)

# Defaults
FLIGHT_ORIGIN_IATA=DEL
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
```

**Budget allocation** (in `config.py`, must sum to 1.0):
```python
BUDGET_FLIGHT_PCT     = 0.30
BUDGET_HOTEL_PCT      = 0.40
BUDGET_ACTIVITIES_PCT = 0.30
```

---

## Usage

**CLI (interactive)**:
```bash
python cli.py
```

**CLI (one-shot)**:
```bash
python cli.py \
  --destination "Tokyo, Japan" \
  --start 2025-10-01 \
  --end 2025-10-08 \
  --budget 3500
```

**Programmatic API**:
```python
from trip_planner import plan_trip

result = plan_trip(
    destination="Bali, Indonesia",
    start_date="2025-09-05",
    end_date="2025-09-12",
    budget_usd=2500,
    num_travelers=2,
    travel_style="Mid-range",
    trip_purpose="Leisure",
    preferred_activities=["Sightseeing", "Food & Dining"],
    event_preferences=["Music", "Arts"],
    source_city="New Delhi, India",
)

print(result["final_plan"])
for day in result["daily_itinerary"]:
    print(day["date"], day["morning"])
```

**Web dashboard**:
```bash
panel serve dashboard.py --show
```

**Export PDF from chat**:
```
> pdf
Trip plan exported to trip_plan.pdf
```

---

## Testing

```bash
# Run with mock LLM (no API keys needed)
LLM_PROVIDER=mock pytest tests/ -v

# Run integration test only
LLM_PROVIDER=mock pytest tests/test_graph.py::test_full_graph -v
```

Test coverage includes:
- Host agent validation (missing fields, invalid budget, reversed dates)
- Tool wrappers (mocked network calls)
- Each agent (tool success path + fallback path)
- Full graph integration (all tools patched, verifies schema and budget calculation)
- Graph resilience (all APIs failing simultaneously — plan must still complete)

---

## Extending the System

**Add a new parallel agent**:

1. Create `trip_planner/agents/new_agent.py`:
   ```python
   def new_agent(state: TripState) -> dict:
       raw = fetch_something(state["destination"])
       llm = get_llm()
       # normalise...
       return {"new_results": [...]}
   ```
2. Add the output key to `TripState` in `state.py`
3. Re-export in `trip_planner/agents/__init__.py`
4. Register the node in `graph.py`:
   ```python
   g.add_node("new_agent", new_agent)
   ```
5. Add to `dispatch_agents`:
   ```python
   Send("new_agent", state)
   ```
6. Add convergence edge:
   ```python
   g.add_edge("new_agent", "merge_results")
   ```

**Add a new LLM provider**: Add a case to `get_llm()` in `llm.py` returning a LangChain chat model.

**Add a new data source**: Implement in `tools.py` following the existing pattern — return a JSON string or error dict, let the agent's LLM normalise it.
