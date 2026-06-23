"""
_base.py
--------
Shared utilities imported by every agent module.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from rich.console import Console

console = Console()
logger  = logging.getLogger(__name__)


def nights(state: dict) -> int:
    """Number of nights between start_date and end_date."""
    try:
        return (
            date.fromisoformat(state["end_date"]) -
            date.fromisoformat(state["start_date"])
        ).days
    except Exception:
        return 3


def is_tool_error(raw: str) -> bool:
    """Return True when the tool returned an error payload instead of real data."""
    try:
        data = json.loads(raw)
        return isinstance(data, dict) and "error" in data
    except Exception:
        return False
