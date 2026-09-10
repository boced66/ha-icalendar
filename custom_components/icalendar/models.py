"""Data models for iCalendar integration runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Any

from .const import (CONF_CALENDAR_ENTITY_ID, CONF_CALENDAR_ENTITY_IDS,
                    CONF_FUTURE_WEEKS, CONF_HISTORY_WEEKS, CONF_SELECTION_MODE,
                    DEFAULT_FUTURE_WEEKS, DEFAULT_HISTORY_WEEKS, MODE_INCLUDE)


def calendar_selection(data: Mapping[str, Any]) -> tuple[str, list[str]]:
    """Read selection, including legacy single-calendar entries."""
    entities = data.get(CONF_CALENDAR_ENTITY_IDS)
    if entities is None:
        entity = data.get(CONF_CALENDAR_ENTITY_ID)
        entities = [entity] if entity else []
    return data.get(CONF_SELECTION_MODE, MODE_INCLUDE), list(dict.fromkeys(entities))


def calendar_range(data: Mapping[str, Any]) -> tuple[int, int]:
    """Read history/future range in weeks, falling back to defaults."""
    history = data.get(CONF_HISTORY_WEEKS)
    future = data.get(CONF_FUTURE_WEEKS)
    history = DEFAULT_HISTORY_WEEKS if history is None else history
    future = DEFAULT_FUTURE_WEEKS if future is None else future
    return int(history), int(future)


@dataclass(slots=True)
class ICalendarRuntimeData:
    """Runtime data for one config entry."""

    calendar_entity_ids: list[str]
    selection_mode: str
    secret: str
    geocoding_url: str = ""
    history_weeks: int = DEFAULT_HISTORY_WEEKS
    future_weeks: int = DEFAULT_FUTURE_WEEKS

    cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    store: Any = None
