"""
tools.py
--------
Thin fetch wrappers around SerpAPI, Tavily, and OpenWeatherMap.

Each function returns raw text / structured data that the calling agent
feeds into the LLM for normalisation into the typed schema.

Required environment variables
───────────────────────────────
  SERPAPI_API_KEY          — https://serpapi.com/manage-api-key
  TAVILY_API_KEY           — https://app.tavily.com/home
  OPENWEATHERMAP_API_KEY   — https://openweathermap.org/api

Tool assignment
───────────────
  flight_agent      → fetch_flights()         (SerpAPI Google Flights)
  stay_agent        → fetch_hotels()          (SerpAPI Google Hotels)
  activities_agent  → fetch_activities()      (Tavily web search)
  info_agent        → fetch_weather()         (OpenWeatherMap: geocode + current + 5-day)
                    → fetch_travel_guides()   (Tavily web search)
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from trip_planner.config import (
    SERPAPI_API_KEY,
    TAVILY_API_KEY,
    OPENWEATHERMAP_API_KEY,
    TICKETMASTER_API_KEY,
    GOOGLE_API_KEY,
    FLIGHT_ORIGIN_IATA,
    FLIGHT_CURRENCY,
    FLIGHT_LANGUAGE,
    _CITY_TO_IATA
)

logger = logging.getLogger(__name__)

_PLACES_PHOTO_BASE = "https://maps.googleapis.com/maps/api/place"


def _google_place_photo_url(name: str, destination: str) -> str:
    """
    Look up a place by name+destination via Google Places Text Search,
    return a direct Google Places Photo URL (redirects to CDN image).
    Returns "" on any error or if no photo is available.
    """
    import requests
    api_key = GOOGLE_API_KEY
    if not api_key:
        return ""
    try:
        resp = requests.get(
            f"{_PLACES_PHOTO_BASE}/textsearch/json",
            params={"query": f"{name} {destination}", "key": api_key},
            timeout=8,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return ""
        photos = results[0].get("photos", [])
        if not photos:
            return ""
        ref = photos[0]["photo_reference"]
        return (
            f"{_PLACES_PHOTO_BASE}/photo"
            f"?maxwidth=600&photo_reference={ref}&key={api_key}"
        )
    except Exception as exc:
        logger.debug("_google_place_photo_url('%s'): %s", name, exc)
        return ""


def attach_google_photos(items: list[dict], destination: str, max_workers: int = 6) -> None:
    """
    Mutates each dict in *items* in-place: fills photo_url via Google Places
    for any item that currently has an empty photo_url.
    Runs requests in parallel to minimise latency.
    """
    needs = [(i, it) for i, it in enumerate(items) if not (it.get("photo_url") or "").strip()]
    if not needs:
        return

    def _fetch(idx_item):
        idx, item = idx_item
        return idx, _google_place_photo_url(item.get("name", ""), destination)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch, pair): pair for pair in needs}
        for fut in as_completed(futures):
            try:
                idx, url = fut.result()
                items[idx]["photo_url"] = url
            except Exception:
                pass

# Month name lookup — avoids importing calendar or locale
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ─────────────────────────────────────────────────────────────────────────────
# IATA airport-code lookup
# ─────────────────────────────────────────────────────────────────────────────
# SerpAPI Google Flights requires a valid 3-letter IATA code (e.g. "NRT") or a
# Wikidata Freebase ID (e.g. "/m/07dfk") for departure_id / arrival_id.
# Plain city names such as "Tokyo" cause a 400 error.
#
# Layer 1 – fast static dict for the most common destinations.
# Layer 2 – SerpAPI Google Flights Autocomplete API for anything not in the dict.




def _resolve_iata(city: str, api_key: str) -> str:
    """
    Resolve a city name to an IATA airport code.

    Layer 1 — O(1) static lookup in ``_CITY_TO_IATA``.
    Layer 2 — SerpAPI Google Flights Autocomplete API (one extra HTTP call).
    Layer 3 — Return the original city string and let SerpAPI handle it
              (last resort; may still 400, but worth trying).
    """
    normalised = city.strip().lower()

    # Layer 1: static dict
    if normalised in _CITY_TO_IATA:
        code = _CITY_TO_IATA[normalised]
        logger.info("_resolve_iata: '%s' → %s (static dict)", city, code)
        return code

    # Layer 2: SerpAPI autocomplete
    try:
        import serpapi
        client = serpapi.Client(api_key=api_key)
        resp   = client.search({"engine": "google_flights_autocomplete", "q": city})
        # Response has an 'airports' list; each item may have 'id' (IATA) and 'name'
        for item in resp.get("airports", []):
            for airport in item.get("airports", [item]):
                code = airport.get("id", "")
                if code and len(code) == 3 and code.isalpha():
                    logger.info("_resolve_iata: '%s' → %s (autocomplete)", city, code)
                    return code.upper()
    except Exception as exc:
        logger.warning("_resolve_iata: autocomplete failed for '%s': %s", city, exc)

    # Layer 3: fall back — return as-is (may 400, but at least we tried)
    logger.warning("_resolve_iata: no IATA code found for '%s', using raw value", city)
    return city


# ─────────────────────────────────────────────────────────────────────────────
# SerpAPI  —  Google Flights
# ─────────────────────────────────────────────────────────────────────────────

def fetch_flights(
    destination: str,
    start_date: str,       # "YYYY-MM-DD"
    end_date: str,         # "YYYY-MM-DD"
    budget_usd: float,
) -> str:
    """
    Query SerpAPI's Google Flights engine and return a condensed JSON summary
    of the cheapest available options.

    departure_id / arrival_id must be valid IATA codes (e.g. "NRT", "CDG").
    City names are resolved via _resolve_iata() before the API call.
    """
    try:
        api_key = SERPAPI_API_KEY
        if not api_key:
            raise KeyError("SERPAPI_API_KEY")
        import serpapi

        origin = FLIGHT_ORIGIN_IATA

        # Resolve destination city → IATA code
        city         = destination.split(",")[0].strip()
        arrival_iata = _resolve_iata(city, api_key)

        params = {
            "engine":        "google_flights",
            "departure_id":  origin,
            "arrival_id":    arrival_iata,
            "outbound_date": start_date,
            "return_date":   end_date,
            "currency":      FLIGHT_CURRENCY,
            "hl":            FLIGHT_LANGUAGE,
            "type":          "1",   # 1 = round-trip
        }

        client = serpapi.Client(api_key=api_key)
        logger.info(
            "fetch_flights: %s → %s  (%s to %s)",
            origin, arrival_iata, start_date, end_date,
        )
        results = client.search(params)

        flights = []
        for section in ("best_flights", "other_flights"):
            for group in results.get(section, []):
                for leg in group.get("flights", []):
                    flights.append({
                        "airline":     leg.get("airline", "Unknown"),
                        "departure":   leg.get("departure_airport", {}).get("time", ""),
                        "arrival":     leg.get("arrival_airport", {}).get("time", ""),
                        "duration":    f"{group.get('total_duration', 0) // 60}h "
                                       f"{group.get('total_duration', 0) % 60}m",
                        "stops":       len(group.get("flights", [])) - 1,
                        "price_usd":   group.get("price", 0),
                        "cabin_class": leg.get("travel_class", "Economy"),
                    })

        budget_slice = budget_usd * 0.30
        affordable = [f for f in flights if f["price_usd"] <= budget_slice] or flights
        affordable.sort(key=lambda x: x["price_usd"])

        logger.info("fetch_flights: %d options found (%d within budget)",
                    len(flights), len(affordable))
        return json.dumps(affordable[:6])

    except Exception as exc:
        logger.error("fetch_flights error: %s", exc)
        return json.dumps({"error": str(exc)})


# ─────────────────────────────────────────────────────────────────────────────
# SerpAPI  —  Google Hotels
# ─────────────────────────────────────────────────────────────────────────────

def fetch_hotels(
    destination: str,
    start_date: str,       # "YYYY-MM-DD"
    end_date: str,         # "YYYY-MM-DD"
    nightly_cap_usd: float,
) -> str:
    """
    Query SerpAPI's Google Hotels engine and return a condensed JSON summary
    of hotels within the nightly cap.
    """
    try:
        api_key = SERPAPI_API_KEY
        if not api_key:
            raise KeyError("SERPAPI_API_KEY")
        import serpapi

        params = {
            "engine":          "google_hotels",
            "q":               f"hotels in {destination}",
            "check_in_date":   start_date,
            "check_out_date":  end_date,
            "currency":        "USD",
            "hl":              "en",
            "gl":              "us",
            "max_price":       int(nightly_cap_usd),
        }

        client  = serpapi.Client(api_key=api_key)
        logger.info("fetch_hotels: querying SerpAPI Google Hotels → %s", destination)
        results = client.search(params)

        hotels = []
        for h in results.get("properties", []):
            # Pull the best available thumbnail from SerpAPI response
            images    = h.get("images") or []
            photo_url = (
                h.get("thumbnail")
                or (images[0].get("thumbnail") if images else "")
                or (images[0].get("original_image") if images else "")
                or ""
            )
            hotels.append({
                "name":                h.get("name", "Unknown"),
                "stars":               h.get("hotel_class", 3),
                "price_per_night_usd": h.get("rate_per_night", {}).get("lowest", 0),
                "rating":              h.get("overall_rating", 0),
                "reviews":             h.get("reviews", 0),
                "amenities":           h.get("amenities", [])[:6],
                "location":            h.get("neighborhood_overview",
                                             h.get("address", destination)),
                "description":         h.get("description", ""),
                "photo_url":           photo_url,
            })

        hotels.sort(key=lambda x: (
            -(x["rating"] or 0),
            x["price_per_night_usd"],
        ))

        logger.info("fetch_hotels: %d properties found", len(hotels))
        return json.dumps(hotels[:8])

    except Exception as exc:
        logger.error("fetch_hotels error: %s", exc)
        return json.dumps({"error": str(exc)})


# ─────────────────────────────────────────────────────────────────────────────
# Tavily  —  Activity search
# ─────────────────────────────────────────────────────────────────────────────

def fetch_activities(
    destination: str,
    start_date: str,
    end_date: str,
    budget_usd: float,
) -> str:
    """
    Run multiple targeted Tavily searches to discover real activities,
    tours, and experiences at the destination.
    """
    api_key = TAVILY_API_KEY
    if not api_key:
        raise KeyError("TAVILY_API_KEY")

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)

        queries = [
            f"best things to do in {destination} tourist activities",
            f"top tours and experiences in {destination} with prices",
            f"outdoor adventure activities {destination}",
            f"cultural food experiences {destination} {start_date[:4]}",
        ]

        combined_results: list[str] = []
        seen_urls: set[str] = set()

        for query in queries:
            logger.info("fetch_activities: Tavily search → %s", query)
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=4,
                include_answer=True,
            )

            if response.get("answer"):
                combined_results.append(f"[Search: {query}]\n{response['answer']}")

            for r in response.get("results", []):
                url = r.get("url", "")
                if url not in seen_urls:
                    seen_urls.add(url)
                    combined_results.append(
                        f"Source: {r.get('title','')}\n"
                        f"URL: {url}\n"
                        f"{r.get('content', '')[:400]}"
                    )

        logger.info("fetch_activities: %d content blocks collected", len(combined_results))
        return "\n\n---\n\n".join(combined_results)

    except Exception as exc:
        logger.error("fetch_activities error: %s", exc)
        return f"Error fetching activities: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# OpenWeatherMap  —  Weather (current + 5-day forecast)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_weather(destination: str) -> str:
    """
    Fetch live weather data from OpenWeatherMap for the destination city.

    Steps
    -----
    1. Geocoding API   — resolve destination name → (lat, lon)
    2. Current weather — /data/2.5/weather  (temperature, humidity, wind, …)
    3. 5-day forecast  — /data/2.5/forecast (3-hourly slots aggregated to daily)

    Returns a human-readable report string that info_agent passes to the LLM
    so it can build a structured weather_summary for the trip plan.
    """
    import requests
    from datetime import datetime as dt

    api_key = OPENWEATHERMAP_API_KEY
    if not api_key:
        raise KeyError("OPENWEATHERMAP_API_KEY")
    city    = destination.split(",")[0].strip()

    try:
        # ── Step 1: Geocode city name → lat / lon ─────────────────────────
        geo_resp = requests.get(
            "http://api.openweathermap.org/geo/1.0/direct",
            params={"q": city, "limit": 1, "appid": api_key},
            timeout=10,
        )
        geo_resp.raise_for_status()
        geo = geo_resp.json()

        if not geo:
            logger.warning("fetch_weather: geocode returned no results for '%s'", city)
            return f"Error fetching weather: could not geocode '{city}'"

        lat             = geo[0]["lat"]
        lon             = geo[0]["lon"]
        resolved_city   = geo[0].get("name", city)
        resolved_country= geo[0].get("country", "")
        logger.info("fetch_weather: geocoded '%s' → %.4f, %.4f", city, lat, lon)

        common_params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}

        # ── Step 2: Current weather ────────────────────────────────────────
        curr_resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params=common_params,
            timeout=10,
        )
        curr_resp.raise_for_status()
        curr = curr_resp.json()

        cond        = curr["weather"][0]["description"].title()
        temp_c      = curr["main"]["temp"]
        feels_c     = curr["main"]["feels_like"]
        temp_min_c  = curr["main"]["temp_min"]
        temp_max_c  = curr["main"]["temp_max"]
        humidity    = curr["main"]["humidity"]
        wind_speed  = curr["wind"]["speed"]
        wind_deg    = curr["wind"]["deg"]
        clouds      = curr["clouds"]["all"]
        visibility  = curr.get("visibility", "N/A")
        sunrise     = dt.fromtimestamp(curr["sys"]["sunrise"]).strftime("%H:%M")
        sunset      = dt.fromtimestamp(curr["sys"]["sunset"]).strftime("%H:%M")

        lines = [
            "=== CURRENT WEATHER REPORT ===",
            f"Location   : {resolved_city}, {resolved_country}"
            f"  (lat {lat:.4f}, lon {lon:.4f})",
            f"Condition  : {cond}",
            f"Temperature: {temp_c:.1f} C  "
            f"(feels like {feels_c:.1f} C,  min {temp_min_c:.1f} C,  max {temp_max_c:.1f} C)",
            f"Humidity   : {humidity}%",
            f"Wind       : {wind_speed} m/s  direction {wind_deg} deg",
            f"Cloud cover: {clouds}%",
            f"Visibility : {visibility} m" if visibility != "N/A" else "Visibility : N/A",
            f"Sunrise    : {sunrise}   Sunset: {sunset}",
        ]

        # ── Step 3: 5-day / 3-hour forecast  →  aggregate to daily ────────
        fore_resp = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={**common_params, "cnt": 40},   # up to ~5 days of 3-hourly slots
            timeout=10,
        )
        fore_resp.raise_for_status()
        fore = fore_resp.json()

        # Group slots by date
        daily: dict[str, dict] = {}
        for slot in fore.get("list", []):
            day_str = slot["dt_txt"][:10]
            if day_str not in daily:
                daily[day_str] = {"temps": [], "descs": [], "humidity": [], "wind": []}
            daily[day_str]["temps"].append(slot["main"]["temp"])
            daily[day_str]["descs"].append(slot["weather"][0]["description"].title())
            daily[day_str]["humidity"].append(slot["main"]["humidity"])
            daily[day_str]["wind"].append(slot["wind"]["speed"])

        lines.append("")
        lines.append("=== 5-DAY FORECAST ===")
        for day_str, vals in list(daily.items())[:5]:
            lo   = min(vals["temps"])
            hi   = max(vals["temps"])
            desc = max(set(vals["descs"]), key=vals["descs"].count)  # most frequent
            avg_hum  = sum(vals["humidity"]) / len(vals["humidity"])
            avg_wind = sum(vals["wind"]) / len(vals["wind"])
            lines.append(
                f"  {day_str}: {desc},  {lo:.1f}-{hi:.1f} C,"
                f"  Humidity {avg_hum:.0f}%,  Wind {avg_wind:.1f} m/s"
            )

        # ── Step 4: Structured 3-hourly slots for LLM hourly breakdown ────
        def _period(hour: int) -> str:
            if 5 <= hour < 12:  return "Morning"
            if 12 <= hour < 17: return "Afternoon"
            if 17 <= hour < 21: return "Evening"
            return "Night"

        hourly_slots: list[dict] = []
        for slot in fore.get("list", []):
            slot_dt   = dt.strptime(slot["dt_txt"], "%Y-%m-%d %H:%M:%S")
            hourly_slots.append({
                "date":        slot["dt_txt"][:10],
                "time":        slot["dt_txt"][11:16],
                "temp_c":      round(slot["main"]["temp"], 1),
                "feels_c":     round(slot["main"]["feels_like"], 1),
                "humidity":    slot["main"]["humidity"],
                "wind_ms":     round(slot["wind"]["speed"], 1),
                "description": slot["weather"][0]["description"].title(),
                "rain_mm":     round(slot.get("rain", {}).get("3h", 0.0), 2),
                "period":      _period(slot_dt.hour),
            })

        import json as _json
        lines.append("")
        lines.append("=== HOURLY_SLOTS_JSON ===")
        lines.append(_json.dumps(hourly_slots))

        report = "\n".join(lines)
        logger.info("fetch_weather: report generated for %s (%d forecast days, %d hourly slots)",
                    resolved_city, len(daily), len(hourly_slots))
        return report

    except Exception as exc:
        logger.error("fetch_weather error: %s", exc)
        return f"Error fetching weather: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# Ticketmaster Discovery API  —  Events
# ─────────────────────────────────────────────────────────────────────────────

def fetch_events(
    destination: str,
    start_date: str,       # "YYYY-MM-DD"
    end_date: str,         # "YYYY-MM-DD"
    preferences: list | None = None,
) -> str:
    """
    Fetch live events from the Ticketmaster Discovery API for the destination
    during the stay window.

    Parameters
    ----------
    destination  : City (and optional country), e.g. "Tokyo, Japan"
    start_date   : Trip start in "YYYY-MM-DD"
    end_date     : Trip end in "YYYY-MM-DD"
    preferences  : Optional list of preferred event categories,
                   e.g. ["Music", "Sports", "Comedy"]

    Returns
    -------
    JSON string — list of up to 15 raw event dicts.
    Raises KeyError if TICKETMASTER_API_KEY is not configured.
    """
    import requests

    api_key = TICKETMASTER_API_KEY
    if not api_key:
        raise KeyError("TICKETMASTER_API_KEY not configured")

    city     = destination.split(",")[0].strip()
    start_dt = f"{start_date}T00:00:00Z"
    end_dt   = f"{end_date}T23:59:59Z"

    params: dict = {
        "apikey":        api_key,
        "city":          city,
        "startDateTime": start_dt,
        "endDateTime":   end_dt,
        "size":          20,
        "sort":          "relevance,desc",
    }

    if preferences:
        params["keyword"] = " ".join(preferences[:3])

    logger.info(
        "fetch_events: Ticketmaster → %s  (%s to %s)  prefs=%s",
        city, start_date, end_date, preferences,
    )

    try:
        resp = requests.get(
            "https://app.ticketmaster.com/discovery/v2/events.json",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("fetch_events: HTTP error: %s", exc)
        return json.dumps({"error": str(exc)})

    raw_events = data.get("_embedded", {}).get("events", [])

    events: list[dict] = []
    for ev in raw_events:
        venues = ev.get("_embedded", {}).get("venues", [{}])
        venue  = venues[0] if venues else {}
        prs    = ev.get("priceRanges", [])
        clsf   = ev.get("classifications", [{}])

        city_n  = venue.get("city",  {}).get("name", "")
        state_n = venue.get("state", {}).get("name", "")
        address = ", ".join(filter(None, [city_n, state_n])) or destination

        segment = (clsf[0].get("segment", {}).get("name", "Event")
                   if clsf else "Event")

        events.append({
            "name":          ev.get("name", "Unknown Event"),
            "venue":         venue.get("name", "Unknown Venue"),
            "venue_address": address,
            "date":          ev.get("dates", {}).get("start", {}).get("localDate", ""),
            "time":          ev.get("dates", {}).get("start", {}).get("localTime", ""),
            "category":      segment,
            "price_min":     prs[0].get("min", 0) if prs else 0,
            "price_max":     prs[0].get("max", 0) if prs else 0,
            "url":           ev.get("url", ""),
            "description":   (ev.get("info") or ev.get("pleaseNote") or "")[:150],
        })

    logger.info("fetch_events: %d events found", len(events))
    return json.dumps(events[:15])


# ─────────────────────────────────────────────────────────────────────────────
# Tavily  —  Travel guide links
# ─────────────────────────────────────────────────────────────────────────────

def fetch_travel_guides(
    destination: str,
    start_date: str,   # "YYYY-MM-DD"
) -> list[dict]:
    """
    Search Tavily for the top 5 travel guide articles for the destination
    in the travel month.  Returns a list of {title, url, snippet} dicts.
    """
    api_key = TAVILY_API_KEY
    if not api_key:
        raise KeyError("TAVILY_API_KEY")

    try:
        from tavily import TavilyClient

        client     = TavilyClient(api_key=api_key)
        month_idx  = int(start_date[5:7]) - 1
        month_name = _MONTHS[month_idx]
        city       = destination.split(",")[0].strip()

        query = (
            f"complete travel guide {city} {month_name} "
            f"top attractions tips itinerary"
        )
        logger.info("fetch_travel_guides: Tavily search → %s", query)
        resp = client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
        )

        guides: list[dict] = []
        seen:   set[str]   = set()
        for r in resp.get("results", []):
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                guides.append({
                    "title":   r.get("title", ""),
                    "url":     url,
                    "snippet": r.get("content", "")[:200],
                })

        logger.info("fetch_travel_guides: %d guides found", len(guides))
        return guides[:5]

    except Exception as exc:
        logger.error("fetch_travel_guides error: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# SerpAPI  —  Restaurant search (Google Local)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_restaurants(destination: str, hotel_location: str = "") -> str:
    """
    Query SerpAPI's Google Local engine for restaurants at the destination.

    Returns a JSON string with up to 15 raw restaurant results.
    Falls back to a Tavily web search if SerpAPI is unavailable.
    """
    city = destination.split(",")[0].strip()
    location_hint = hotel_location or city

    # Primary: SerpAPI google_local
    api_key = SERPAPI_API_KEY
    if api_key:
        try:
            import serpapi
            client = serpapi.Client(api_key=api_key)
            params = {
                "engine":   "google_local",
                "q":        f"best restaurants in {city}",
                "location": location_hint,
                "hl":       "en",
                "gl":       "us",
            }
            logger.info("fetch_restaurants: SerpAPI google_local → %s", city)
            results = client.search(params)

            restaurants: list[dict] = []
            for r in results.get("local_results", []):
                restaurants.append({
                    "name":        r.get("title", ""),
                    "rating":      r.get("rating", 0),
                    "reviews":     r.get("reviews", 0),
                    "price_level": r.get("price", "$$"),
                    "cuisine":     r.get("type", ""),
                    "address":     r.get("address", ""),
                    "description": r.get("description", ""),
                    "hours":       r.get("hours", ""),
                    "photo_url":   r.get("thumbnail", ""),
                })

            logger.info("fetch_restaurants: %d results", len(restaurants))
            return json.dumps(restaurants[:15])
        except Exception as exc:
            logger.warning("fetch_restaurants: SerpAPI failed (%s), falling back to Tavily", exc)

    # Fallback: Tavily web search
    tavily_key = TAVILY_API_KEY
    if tavily_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=tavily_key)
            queries = [
                f"best restaurants {city} local food dining guide",
                f"top rated restaurants {city} cuisine prices",
            ]
            combined: list[str] = []
            for q in queries:
                resp = client.search(query=q, search_depth="advanced", max_results=5,
                                     include_answer=True)
                if resp.get("answer"):
                    combined.append(f"[{q}]\n{resp['answer']}")
                for r in resp.get("results", []):
                    combined.append(f"Source: {r.get('title','')}\n{r.get('content','')[:300]}")
            return "\n\n---\n\n".join(combined)
        except Exception as exc:
            logger.error("fetch_restaurants: Tavily fallback failed (%s)", exc)

    return json.dumps({"error": "No API available for restaurant search"})


# ─────────────────────────────────────────────────────────────────────────────
# Tavily  —  Visa & Entry Requirements
# ─────────────────────────────────────────────────────────────────────────────

def fetch_visa_info(source_city: str, destination: str) -> str:
    """
    Search Tavily for visa requirements, processing times, and application
    links from the source city/country to the destination.

    Returns a multi-block text string that visa_agent feeds to the LLM.
    """
    api_key = TAVILY_API_KEY
    if not api_key:
        raise KeyError("TAVILY_API_KEY")

    dest_country = destination.split(",")[-1].strip() if "," in destination else destination
    src_country  = source_city.split(",")[-1].strip()  if "," in source_city  else source_city

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)

        queries = [
            f"visa requirements for {src_country} citizens visiting {dest_country}",
            f"{src_country} passport {dest_country} tourist visa application process fees",
            f"{dest_country} entry requirements processing time {src_country}",
        ]

        combined: list[str] = []
        seen_urls: set[str] = set()
        for q in queries:
            logger.info("fetch_visa_info: Tavily search → %s", q)
            resp = client.search(
                query=q,
                search_depth="advanced",
                max_results=4,
                include_answer=True,
            )
            if resp.get("answer"):
                combined.append(f"[Search: {q}]\n{resp['answer']}")
            for r in resp.get("results", []):
                url = r.get("url", "")
                if url not in seen_urls:
                    seen_urls.add(url)
                    combined.append(
                        f"Source: {r.get('title','')}\nURL: {url}\n"
                        f"{r.get('content', '')[:400]}"
                    )

        logger.info("fetch_visa_info: %d content blocks collected", len(combined))
        return "\n\n---\n\n".join(combined)

    except Exception as exc:
        logger.error("fetch_visa_info error: %s", exc)
        return f"Error fetching visa info: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# Tavily  —  Local Transportation
# ─────────────────────────────────────────────────────────────────────────────

def fetch_transport_info(destination: str) -> str:
    """
    Search Tavily for local transportation options at the destination:
    airport transfers, public transit passes, taxi/rideshare costs.

    Returns a multi-block text string that transport_agent feeds to the LLM.
    """
    api_key = TAVILY_API_KEY
    if not api_key:
        raise KeyError("TAVILY_API_KEY")

    city = destination.split(",")[0].strip()

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)

        queries = [
            f"airport transfer options costs {city} getting from airport to city center",
            f"public transport {city} metro bus pass price tourist card",
            f"uber taxi cost {city} average price per ride",
            f"getting around {city} local transport guide tips",
        ]

        combined: list[str] = []
        seen_urls: set[str] = set()
        for q in queries:
            logger.info("fetch_transport_info: Tavily search → %s", q)
            resp = client.search(
                query=q,
                search_depth="advanced",
                max_results=3,
                include_answer=True,
            )
            if resp.get("answer"):
                combined.append(f"[Search: {q}]\n{resp['answer']}")
            for r in resp.get("results", []):
                url = r.get("url", "")
                if url not in seen_urls:
                    seen_urls.add(url)
                    combined.append(
                        f"Source: {r.get('title','')}\nURL: {url}\n"
                        f"{r.get('content', '')[:400]}"
                    )

        logger.info("fetch_transport_info: %d content blocks collected", len(combined))
        return "\n\n---\n\n".join(combined)

    except Exception as exc:
        logger.error("fetch_transport_info error: %s", exc)
        return f"Error fetching transport info: {exc}"
