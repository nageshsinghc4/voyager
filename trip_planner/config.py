"""
config.py
---------
Single source of truth for all configuration.

All environment variable reads and tuneable constants live here.
Import from this module instead of calling os.getenv() across files.

Note: load_dotenv() must be called (e.g. in cli.py) before trip_planner
is first imported, so these module-level os.getenv() calls resolve correctly.
"""

from __future__ import annotations

import os

# ── API Keys ──────────────────────────────────────────────────────────────────
SERPAPI_API_KEY         = os.getenv("SERPAPI_API_KEY", "")
TAVILY_API_KEY          = os.getenv("TAVILY_API_KEY", "")
OPENWEATHERMAP_API_KEY  = os.getenv("OPENWEATHERMAP_API_KEY", "")
TICKETMASTER_API_KEY    = os.getenv("TICKETMASTER_API_KEY", "")
AZURE_OPENAI_API_KEY    = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT   = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
OPENAI_API_KEY          = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY          = os.getenv("GOOGLE_API_KEY", "")
GEOAPIFY_API_KEY        = os.getenv("GEOAPIFY_API_KEY", "")

# ── LLM settings ──────────────────────────────────────────────────────────────
LLM_PROVIDER            = os.getenv("LLM_PROVIDER", "azure").lower()
OPENAI_API_VERSION      = os.getenv("OPENAI_API_VERSION", "2024-12-01-preview")
LLM_TEMPERATURE: float  = 0.3
LLM_MAX_TOKENS: int     = 4096

# ── Flight defaults ───────────────────────────────────────────────────────────
FLIGHT_ORIGIN_IATA      = os.getenv("FLIGHT_ORIGIN_IATA", "DEL")
FLIGHT_CURRENCY         = "USD"
FLIGHT_LANGUAGE         = "en"

# ── Budget allocation  (must sum to 1.0) ──────────────────────────────────────
BUDGET_FLIGHT_PCT: float      = 0.30
BUDGET_HOTEL_PCT: float       = 0.40
BUDGET_ACTIVITIES_PCT: float  = 0.30

_CITY_TO_IATA: dict[str, str] = {
    # ── Asia ──────────────────────────────────────────────────────────────
    "tokyo":            "NRT",
    "osaka":            "KIX",
    "kyoto":            "ITM",
    "hiroshima":        "HIJ",
    "sapporo":          "CTS",
    "beijing":          "PEK",
    "shanghai":         "PVG",
    "guangzhou":        "CAN",
    "chengdu":          "CTU",
    "hong kong":        "HKG",
    "singapore":        "SIN",
    "bangkok":          "BKK",
    "phuket":           "HKT",
    "chiang mai":       "CNX",
    "bali":             "DPS",
    "denpasar":         "DPS",
    "jakarta":          "CGK",
    "kuala lumpur":     "KUL",
    "penang":           "PEN",
    "manila":           "MNL",
    "cebu":             "CEB",
    "seoul":            "ICN",
    "busan":            "PUS",
    "taipei":           "TPE",
    "hanoi":            "HAN",
    "ho chi minh city": "SGN",
    "saigon":           "SGN",
    "da nang":          "DAD",
    "colombo":          "CMB",
    "kathmandu":        "KTM",
    "dhaka":            "DAC",
    "karachi":          "KHI",
    "lahore":           "LHE",
    "islamabad":        "ISB",
    "delhi":            "DEL",
    "new delhi":        "DEL",
    "mumbai":           "BOM",
    "bangalore":        "BLR",
    "bengaluru":        "BLR",
    "chennai":          "MAA",
    "hyderabad":        "HYD",
    "kolkata":          "CCU",
    "goa":              "GOI",
    "kochi":            "COK",
    "ahmedabad":        "AMD",
    "jaipur":           "JAI",
    "dubai":            "DXB",
    "abu dhabi":        "AUH",
    "doha":             "DOH",
    "riyadh":           "RUH",
    "jeddah":           "JED",
    "kuwait city":      "KWI",
    "muscat":           "MCT",
    "bahrain":          "BAH",
    "istanbul":         "IST",
    "ankara":           "ESB",
    "tel aviv":         "TLV",
    "amman":            "AMM",
    "beirut":           "BEY",
    "tehran":           "IKA",
    "baku":             "GYD",
    "tashkent":         "TAS",
    "almaty":           "ALA",
    "yangon":           "RGN",
    "ulaanbaatar":      "ULN",
    "phnom penh":       "PNH",
    "vientiane":        "VTE",
    "male":             "MLE",
    # ── Europe ────────────────────────────────────────────────────────────
    "london":           "LHR",
    "paris":            "CDG",
    "rome":             "FCO",
    "milan":            "MXP",
    "venice":           "VCE",
    "florence":         "FLR",
    "naples":           "NAP",
    "barcelona":        "BCN",
    "madrid":           "MAD",
    "seville":          "SVQ",
    "berlin":           "BER",
    "munich":           "MUC",
    "frankfurt":        "FRA",
    "hamburg":          "HAM",
    "amsterdam":        "AMS",
    "brussels":         "BRU",
    "vienna":           "VIE",
    "zurich":           "ZRH",
    "geneva":           "GVA",
    "stockholm":        "ARN",
    "oslo":             "OSL",
    "copenhagen":       "CPH",
    "helsinki":         "HEL",
    "athens":           "ATH",
    "lisbon":           "LIS",
    "porto":            "OPO",
    "prague":           "PRG",
    "budapest":         "BUD",
    "warsaw":           "WAW",
    "krakow":           "KRK",
    "dublin":           "DUB",
    "edinburgh":        "EDI",
    "manchester":       "MAN",
    "birmingham":       "BHX",
    "glasgow":          "GLA",
    "amsterdam":        "AMS",
    "bucharest":        "OTP",
    "sofia":            "SOF",
    "zagreb":           "ZAG",
    "belgrade":         "BEG",
    "dubrovnik":        "DBV",
    "split":            "SPU",
    "reykjavik":        "KEF",
    "riga":             "RIX",
    "tallinn":          "TLL",
    "vilnius":          "VNO",
    "luxembourg":       "LUX",
    "valletta":         "MLA",
    "nicosia":          "LCA",
    "monaco":           "NCE",
    "bern":             "BSL",
    "salzburg":         "SZG",
    "innsbruck":        "INN",
    # ── Americas ──────────────────────────────────────────────────────────
    "new york":         "JFK",
    "los angeles":      "LAX",
    "chicago":          "ORD",
    "miami":            "MIA",
    "san francisco":    "SFO",
    "seattle":          "SEA",
    "boston":           "BOS",
    "washington":       "IAD",
    "washington dc":    "IAD",
    "atlanta":          "ATL",
    "dallas":           "DFW",
    "houston":          "IAH",
    "denver":           "DEN",
    "las vegas":        "LAS",
    "orlando":          "MCO",
    "phoenix":          "PHX",
    "minneapolis":      "MSP",
    "detroit":          "DTW",
    "philadelphia":     "PHL",
    "san diego":        "SAN",
    "portland":         "PDX",
    "new orleans":      "MSY",
    "toronto":          "YYZ",
    "vancouver":        "YVR",
    "montreal":         "YUL",
    "calgary":          "YYC",
    "ottawa":           "YOW",
    "mexico city":      "MEX",
    "cancun":           "CUN",
    "guadalajara":      "GDL",
    "havana":           "HAV",
    "panama city":      "PTY",
    "san jose":         "SJO",
    "bogota":           "BOG",
    "medellin":         "MDE",
    "lima":             "LIM",
    "quito":            "UIO",
    "guayaquil":        "GYE",
    "sao paulo":        "GRU",
    "rio de janeiro":   "GIG",
    "brasilia":         "BSB",
    "buenos aires":     "EZE",
    "santiago":         "SCL",
    "montevideo":       "MVD",
    "asuncion":         "ASU",
    "la paz":           "VVI",
    "caracas":          "CCS",
    "kingston":         "KIN",
    # ── Africa ────────────────────────────────────────────────────────────
    "cairo":            "CAI",
    "casablanca":       "CMN",
    "marrakech":        "RAK",
    "tunis":            "TUN",
    "algiers":          "ALG",
    "tripoli":          "MJI",
    "lagos":            "LOS",
    "accra":            "ACC",
    "abidjan":          "ABJ",
    "dakar":            "DSS",
    "nairobi":          "NBO",
    "addis ababa":      "ADD",
    "dar es salaam":    "DAR",
    "entebbe":          "EBB",
    "kigali":           "KGL",
    "johannesburg":     "JNB",
    "cape town":        "CPT",
    "durban":           "DUR",
    "lusaka":           "LUN",
    "harare":           "HRE",
    "antananarivo":     "TNR",
    "maputo":           "MPM",
    # ── Oceania ───────────────────────────────────────────────────────────
    "sydney":           "SYD",
    "melbourne":        "MEL",
    "brisbane":         "BNE",
    "perth":            "PER",
    "adelaide":         "ADL",
    "gold coast":       "OOL",
    "auckland":         "AKL",
    "wellington":       "WLG",
    "christchurch":     "CHC",
    "fiji":             "NAN",
    "nadi":             "NAN",
    "honolulu":         "HNL",
    "guam":             "GUM",
}