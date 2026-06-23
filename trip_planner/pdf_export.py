"""
pdf_export.py
-------------
Generates a well-formatted PDF of the complete trip plan using fpdf2.

Usage
-----
    from trip_planner.pdf_export import export_pdf, export_pdf_bytes

    # Save to file
    path = export_pdf(state, "my_trip.pdf")

    # Get BytesIO for in-memory use (dashboard FileDownload)
    buf = export_pdf_bytes(state)
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# ── Colour palette ────────────────────────────────────────────────────────────
_WHITE   = (255, 255, 255)
_DARK    = (30,  30,  30)
_GREY    = (120, 120, 120)
_LGREY   = (220, 220, 220)
_GREEN   = (22,  163,  74)   # green-600
_GREEN_D = (21,  128,  61)   # green-700  (text on light bg)
_GREEN_L = (220, 252, 231)   # green-100  (light fills)
_PURPLE  = (58,  167, 232)   # #3aa7e8 brand blue (events / itinerary)
_PURPLE_L= (224, 244, 253)   # #e0f4fd light blue tint
_AMBER   = (180, 100,   0)   # warm amber for warnings
_RED     = (185,  28,  28)

# ── Character sanitiser ───────────────────────────────────────────────────────
_CHAR_MAP: dict[str, str] = {
    "•": "-",  "·": "-",   "–": "-",  "—": "--",
    "‘": "'",  "’": "'", "“": '"', "”": '"',
    "…": "...","→": "->","←": "<-","x": "x",
    "°": "deg", "€": "EUR", "¥": "JPY",
}


def _safe(text: str) -> str:
    if not text:
        return ""
    for src, dst in _CHAR_MAP.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def export_pdf(state: dict, output_path: str = "trip_plan.pdf") -> str:
    """Build PDF, save to *output_path*, return absolute path."""
    _check_fpdf()
    builder = _TripPDF(state)
    builder.build()
    builder.pdf.output(output_path)
    abs_path = os.path.abspath(output_path)
    logger.info("export_pdf: saved to %s", abs_path)
    return abs_path


def export_pdf_bytes(state: dict) -> "io.BytesIO":
    """Build PDF in-memory and return a BytesIO buffer (for FileDownload)."""
    import io as _io
    _check_fpdf()
    builder = _TripPDF(state)
    builder.build()
    raw: bytes = builder.pdf.output()
    buf = _io.BytesIO(raw)
    buf.seek(0)
    logger.info("export_pdf_bytes: %d bytes", len(raw))
    return buf


def _check_fpdf():
    try:
        from fpdf import FPDF  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("fpdf2 is required. Run: pip install fpdf2") from exc


# ─────────────────────────────────────────────────────────────────────────────
# Page constants
# ─────────────────────────────────────────────────────────────────────────────
_PW   = 210   # A4 width  (mm)
_PH   = 297   # A4 height (mm)
_LM   = 16    # left  margin
_RM   = 16    # right margin
_TM   = 16    # top   margin
_BM   = 16    # bottom margin
_CW   = _PW - _LM - _RM   # content width


# ─────────────────────────────────────────────────────────────────────────────
# Internal PDF builder
# ─────────────────────────────────────────────────────────────────────────────

class _TripPDF:

    def __init__(self, state: dict) -> None:
        from fpdf import FPDF

        self.state = state
        self.pdf   = FPDF()
        self.pdf.set_auto_page_break(auto=True, margin=_BM + 8)
        self.pdf.set_margins(left=_LM, top=_TM, right=_RM)

    # ─────────────────────────────────────────────────────────────────────
    # Entry point
    # ─────────────────────────────────────────────────────────────────────

    def build(self) -> None:
        self._cover_page()
        self.pdf.add_page()
        self._weather_section()
        self._flights_section()
        self._hotels_section()
        self._activities_section()
        self._events_section()
        self._itinerary_section()
        self._food_culture_section()
        self._packing_section()
        self._guides_section()
        self._budget_section()

    # ─────────────────────────────────────────────────────────────────────
    # Low-level drawing helpers
    # ─────────────────────────────────────────────────────────────────────

    def _page_footer(self) -> None:
        pdf = self.pdf
        pdf.set_y(-12)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*_GREY)
        pdf.cell(0, 5, f"Voyager AI Trip Planner  |  Page {pdf.page_no()}",
                 align="C")
        pdf.set_text_color(*_DARK)

    def _section_header(self, title: str, colour: tuple = _GREEN) -> None:
        """Full-width coloured banner with white bold title."""
        pdf = self.pdf
        pdf.ln(3)
        pdf.set_fill_color(*colour)
        pdf.set_text_color(*_WHITE)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(_CW, 9, f"  {_safe(title)}", fill=True,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_DARK)
        pdf.ln(2)

    def _item_row(self, num: int, title: str,
                  right_val: str = "", colour: tuple = _DARK) -> None:
        """Numbered item row: bold title on left, right-aligned value."""
        pdf = self.pdf
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*colour)
        if right_val:
            pdf.cell(_CW - 40, 6, _safe(f"  {num}. {title}"))
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*_GREEN_D)
            pdf.cell(40, 6, _safe(right_val), align="R",
                     new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(_CW, 6, _safe(f"  {num}. {title}"),
                     new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_DARK)

    def _detail_line(self, text: str, indent: int = 10,
                     italic: bool = False, colour: tuple = _GREY) -> None:
        """Indented detail line in grey."""
        pdf = self.pdf
        pdf.set_x(_LM + indent)
        pdf.set_font("Helvetica", "I" if italic else "", 9)
        pdf.set_text_color(*colour)
        pdf.multi_cell(_CW - indent, 5, _safe(text))
        pdf.set_text_color(*_DARK)

    def _kv_line(self, key: str, value: str, indent: int = 6) -> None:
        """Key in bold-grey, value in dark, same line."""
        pdf = self.pdf
        pdf.set_x(_LM + indent)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_GREY)
        kw = 36 - indent
        pdf.cell(kw, 5, _safe(f"{key}:"))
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_DARK)
        pdf.multi_cell(_CW - kw - indent, 5, _safe(value))

    def _bullet(self, text: str, indent: int = 10) -> None:
        pdf = self.pdf
        pdf.set_x(_LM + indent)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_DARK)
        pdf.multi_cell(_CW - indent, 5, _safe(f"- {text}"))

    def _light_divider(self) -> None:
        pdf = self.pdf
        pdf.ln(1)
        pdf.set_draw_color(*_LGREY)
        pdf.set_line_width(0.2)
        pdf.line(_LM, pdf.get_y(), _PW - _RM, pdf.get_y())
        pdf.ln(3)

    def _section_end(self) -> None:
        self.pdf.ln(2)
        self._light_divider()

    # ─────────────────────────────────────────────────────────────────────
    # Cover page
    # ─────────────────────────────────────────────────────────────────────

    def _cover_page(self) -> None:
        pdf = self.pdf
        pdf.add_page()

        # ── Hero banner ──
        BANNER_H = 62
        pdf.set_fill_color(*_GREEN)
        pdf.rect(0, 0, _PW, BANNER_H, style="F")
        # subtle darker strip at bottom of banner
        pdf.set_fill_color(*_GREEN_D)
        pdf.rect(0, BANNER_H - 6, _PW, 6, style="F")

        # App name (small, light)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(200, 240, 210)
        pdf.set_y(9)
        pdf.cell(_PW, 5, "VOYAGER  |  AI-POWERED TRIP PLANNER", align="C",
                 new_x="LMARGIN", new_y="NEXT")

        # Destination (large)
        dest = _safe(self.state.get("destination", "Your Destination"))
        pdf.set_font("Helvetica", "B", 26)
        pdf.set_text_color(*_WHITE)
        pdf.set_y(18)
        pdf.cell(_PW, 14, dest, align="C", new_x="LMARGIN", new_y="NEXT")

        # Dates & meta
        start  = self.state.get("start_date", "")
        end    = self.state.get("end_date", "")
        nights = self.state.get("nights", 0)
        budget = self.state.get("budget_usd", 0)
        n_trav = self.state.get("num_travelers", 1)
        style  = self.state.get("travel_style", "")
        purpose= self.state.get("trip_purpose", "")

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(210, 245, 220)
        pdf.cell(_PW, 7,
                 f"{start}  to  {end}   |   {nights} nights   |   {n_trav} traveler(s)",
                 align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(_PW, 6,
                 f"Budget: ${budget:,.0f}   |   {style}   |   {purpose}",
                 align="C", new_x="LMARGIN", new_y="NEXT")

        # ── Stat boxes ──
        pdf.set_y(BANNER_H + 8)
        self._stat_boxes()

        # ── Trip summary paragraph ──
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_GREEN_D)
        pdf.cell(_CW, 6, "Trip Overview", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        rows = [
            ("Destination",  self.state.get("destination", "")),
            ("Travel dates", f"{start}  to  {end}  ({nights} nights)"),
            ("Travelers",    f"{n_trav} person(s)"),
            ("Budget",       f"${budget:,.0f} total"),
            ("Travel style", style),
            ("Trip purpose", purpose),
        ]
        for k, v in rows:
            self._kv_line(k, str(v), indent=4)

        # Page footer
        self._page_footer()

    def _stat_boxes(self) -> None:
        pdf   = self.pdf
        state = self.state
        stats = [
            ("Flights",    len(state.get("flight_results") or [])),
            ("Hotels",     len(state.get("stay_results") or [])),
            ("Activities", len(state.get("activity_results") or [])),
            ("Events",     len(state.get("event_results") or [])),
        ]
        gap   = 4
        n     = len(stats)
        box_w = (_CW - gap * (n - 1)) / n
        x0    = _LM
        y0    = pdf.get_y()
        BOX_H = 18

        for i, (label, val) in enumerate(stats):
            x = x0 + i * (box_w + gap)
            # Box background
            pdf.set_fill_color(*_GREEN_L)
            pdf.rect(x, y0, box_w, BOX_H, style="F")
            # Top accent line
            pdf.set_fill_color(*_GREEN)
            pdf.rect(x, y0, box_w, 2.5, style="F")
            # Number
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(*_GREEN_D)
            pdf.set_xy(x, y0 + 2.5)
            pdf.cell(box_w, 8, str(val), align="C",
                     new_x="RIGHT", new_y="TOP")
            # Label
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*_GREY)
            pdf.set_xy(x, y0 + 11)
            pdf.cell(box_w, 5, label, align="C",
                     new_x="RIGHT", new_y="TOP")

        pdf.set_y(y0 + BOX_H + 4)
        pdf.set_text_color(*_DARK)

    # ─────────────────────────────────────────────────────────────────────
    # Content sections
    # ─────────────────────────────────────────────────────────────────────

    def _weather_section(self) -> None:
        w = self.state.get("weather_info") or {}
        if not w:
            return
        self._section_header("WEATHER FORECAST")
        self._kv_line("Conditions",   w.get("conditions", "N/A"))
        self._kv_line("Temperature",  w.get("temp_range",  "N/A"))
        self._kv_line("Rain chance",  w.get("rain_chance", "N/A"))
        for line in (w.get("forecast") or [])[:5]:
            self._bullet(line)
        self._section_end()

    def _flights_section(self) -> None:
        flights = self.state.get("flight_results") or []
        self._section_header("FLIGHT OPTIONS")
        if not flights:
            self._detail_line("No flight data available.", colour=_GREY)
            self._section_end()
            return
        for i, f in enumerate(flights, 1):
            price  = f"${f.get('price_usd', 0):,.0f}"
            airline = f.get("airline", "Unknown Airline")
            cabin   = f.get("cabin_class", "")
            self._item_row(i, f"{airline}  [{cabin}]", right_val=price)
            dep  = f.get("departure", "?")
            arr  = f.get("arrival",   "?")
            dur  = f.get("duration",  "?")
            stops= f.get("stops", 0)
            self._detail_line(
                f"{dep}  ->  {arr}   |   Duration: {dur}   |   "
                f"{'Non-stop' if stops == 0 else f'{stops} stop(s)'}"
            )
            if i < len(flights):
                self._light_divider()
        self._section_end()

    def _hotels_section(self) -> None:
        stays = self.state.get("stay_results") or []
        self._section_header("HOTEL OPTIONS")
        if not stays:
            self._detail_line("No hotel data available.", colour=_GREY)
            self._section_end()
            return
        for i, h in enumerate(stays, 1):
            stars    = "*" * h.get("stars", 3)
            name     = h.get("name", "?")
            pn_usd   = h.get("price_per_night_usd", 0)
            tot_usd  = h.get("total_cost_usd", 0)
            price_str= f"${pn_usd:,.0f}/night"
            self._item_row(i, f"{stars}  {name}", right_val=price_str)
            rating    = h.get("rating", "?")
            location  = h.get("location", "?")
            amenities = ", ".join(h.get("amenities", [])[:5])
            self._detail_line(f"Location: {location}   |   Rating: {rating}/5.0")
            self._detail_line(f"Total for stay: ${tot_usd:,.0f}")
            if amenities:
                self._detail_line(f"Amenities: {amenities}")
            if i < len(stays):
                self._light_divider()
        self._section_end()

    def _activities_section(self) -> None:
        acts = self.state.get("activity_results") or []
        self._section_header("ACTIVITIES")
        if not acts:
            self._detail_line("No activity data available.", colour=_GREY)
            self._section_end()
            return
        for i, a in enumerate(acts, 1):
            name     = a.get("name", "?")
            cat      = a.get("category", "")
            price    = f"${a.get('price_usd', 0):,.0f}/person"
            self._item_row(i, f"{name}  [{cat}]", right_val=price)
            dur      = a.get("duration", "?")
            rating   = a.get("rating", "?")
            desc     = a.get("description", "")
            self._detail_line(f"Duration: {dur}   |   Rating: {rating}/5.0")
            if desc:
                self._detail_line(desc[:160] + ("..." if len(desc) > 160 else ""),
                                  italic=True)
            if i < len(acts):
                self._light_divider()
        self._section_end()

    def _events_section(self) -> None:
        events = self.state.get("event_results") or []
        if not events:
            return
        self._section_header("EVENTS DURING YOUR STAY", _PURPLE)
        for i, e in enumerate(events, 1):
            name     = e.get("name", "?")
            cat      = e.get("category", "")
            p_min    = e.get("price_min", 0)
            p_max    = e.get("price_max", 0)
            price_str= (f"${p_min:.0f}-${p_max:.0f}"
                        if p_max > 0 else "Free/TBD")
            self._item_row(i, f"{name}  [{cat}]", right_val=price_str,
                           colour=_PURPLE)
            date_str = e.get("date", "")
            time_str = e.get("time", "")
            venue    = e.get("venue", "?")
            addr     = e.get("venue_address", "")
            self._detail_line(f"{date_str}  {time_str}   |   {venue}")
            if addr:
                self._detail_line(addr)
            nearby = ", ".join(e.get("nearby_hotels") or [])
            if nearby:
                self._detail_line(f"Nearby hotels: {nearby}",
                                  colour=_GREEN_D)
            if i < len(events):
                self._light_divider()
        self._section_end()

    def _itinerary_section(self) -> None:
        daily = self.state.get("daily_itinerary") or []
        self._section_header("DAY-BY-DAY ITINERARY", _PURPLE)
        if not daily:
            self._detail_line("Itinerary not available.", colour=_GREY)
            self._section_end()
            return

        for day in daily:
            # Day header card
            pdf = self.pdf
            pdf.set_fill_color(*_PURPLE_L)
            pdf.set_text_color(*_PURPLE)
            pdf.set_font("Helvetica", "B", 10)
            day_label = _safe(
                f"  Day {day.get('day','?')}   |   {day.get('date','')}"
            )
            pdf.cell(_CW, 7, day_label, fill=True,
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*_DARK)
            pdf.ln(1)

            for slot, icon in [("morning","AM"), ("afternoon","PM"), ("evening","EVE")]:
                val = day.get(slot, "")
                if val:
                    self._kv_line(icon, val, indent=6)

            dining = day.get("dining") or []
            if dining:
                self._kv_line("Dining", " / ".join(dining[:3]), indent=6)

            notes = day.get("notes", "")
            if notes:
                self._detail_line(f"Note: {notes}", indent=6,
                                  italic=True, colour=_AMBER)
            pdf.ln(3)

        self._section_end()

    def _food_culture_section(self) -> None:
        food = self.state.get("food_culture_tips") or {}
        tips = self.state.get("travel_tips") or []
        if not food and not tips:
            return
        self._section_header("FOOD, CULTURE & TIPS")
        if food:
            must_try = food.get("must_try_foods") or []
            if must_try:
                self._kv_line("Must-try foods", ", ".join(must_try))
            if food.get("dining_customs"):
                self._kv_line("Dining customs", food["dining_customs"])
            if food.get("tipping"):
                self._kv_line("Tipping",        food["tipping"])
            for tip in (food.get("cultural_tips") or []):
                self._bullet(tip)
        if tips:
            self.pdf.ln(2)
            self.pdf.set_font("Helvetica", "B", 9)
            self.pdf.set_text_color(*_GREEN_D)
            self.pdf.cell(_CW, 5, "  Practical Travel Tips",
                          new_x="LMARGIN", new_y="NEXT")
            self.pdf.set_text_color(*_DARK)
            for tip in tips:
                self._bullet(tip)
        self._section_end()

    def _packing_section(self) -> None:
        packing = self.state.get("packing_list") or []
        if not packing:
            return
        self._section_header("PACKING LIST")
        pdf   = self.pdf
        col_w = (_CW - 6) / 2
        half  = (len(packing) + 1) // 2
        left  = packing[:half]
        right = packing[half:]
        start_y = pdf.get_y()

        # Left column
        for item in left:
            pdf.set_x(_LM)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(col_w, 5.5, _safe(f"[ ] {item}"),
                     new_x="LMARGIN", new_y="NEXT")
        end_left_y = pdf.get_y()

        # Right column — reset Y to top, shift X
        pdf.set_y(start_y)
        for item in right:
            pdf.set_x(_LM + col_w + 6)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(col_w, 5.5, _safe(f"[ ] {item}"),
                     new_x="LMARGIN", new_y="NEXT")
        end_right_y = pdf.get_y()

        pdf.set_y(max(end_left_y, end_right_y))
        self._section_end()

    def _guides_section(self) -> None:
        guides = self.state.get("travel_guides") or []
        if not guides:
            return
        self._section_header("TOP TRAVEL GUIDES")
        for i, g in enumerate(guides, 1):
            self._item_row(i, g.get("title", "Guide"))
            url = (g.get("url") or "").encode("ascii", errors="ignore").decode("ascii")
            if url:
                self._detail_line(url[:90], italic=True, colour=_GREEN_D)
            snippet = g.get("snippet", "")
            if snippet:
                self._detail_line(snippet[:160] + ("..." if len(snippet) > 160 else ""))
            if i < len(guides):
                self._light_divider()
        self._section_end()

    def _budget_section(self) -> None:
        bd = self.state.get("budget_breakdown") or {}
        if not bd:
            return
        self._section_header("BUDGET SUMMARY")
        pdf = self.pdf

        rows = [
            ("Flights",       bd.get("flights", 0)),
            ("Accommodation", bd.get("accommodation", 0)),
            ("Activities",    bd.get("activities", 0)),
        ]
        total     = bd.get("total", 0)
        budget    = self.state.get("budget_usd", 0)
        remaining = bd.get("remaining", 0)
        rem_colour= _GREEN_D if remaining >= 0 else _RED

        # Budget rows
        for label, amt in rows:
            pdf.set_x(_LM + 4)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*_DARK)
            pdf.cell(_CW - 60, 6, _safe(label))
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(56, 6, _safe(f"${amt:>10,.0f}"), align="R",
                     new_x="LMARGIN", new_y="NEXT")

        # Divider before totals
        pdf.ln(1)
        pdf.set_draw_color(*_LGREY)
        pdf.set_line_width(0.4)
        pdf.line(_LM + 4, pdf.get_y(), _PW - _RM - 4, pdf.get_y())
        pdf.ln(3)

        # Estimated total
        pdf.set_x(_LM + 4)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_DARK)
        pdf.cell(_CW - 60, 6, "Estimated total")
        pdf.cell(56, 6, _safe(f"${total:>10,.0f}  of  ${budget:,.0f}"),
                 align="R", new_x="LMARGIN", new_y="NEXT")

        # Remaining / over-budget
        pdf.set_x(_LM + 4)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*rem_colour)
        label = "Remaining" if remaining >= 0 else "Over budget"
        pdf.cell(_CW - 60, 6, label)
        pdf.cell(56, 6, _safe(f"${abs(remaining):>10,.0f}"), align="R",
                 new_x="LMARGIN", new_y="NEXT")

        # Sign-off
        pdf.set_text_color(*_DARK)
        pdf.ln(8)
        pdf.set_fill_color(*_GREEN_L)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*_GREEN_D)
        pdf.cell(_CW, 10, "  Have a great trip!", fill=True,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_DARK)

        self._page_footer()
