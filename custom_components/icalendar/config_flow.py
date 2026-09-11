"""Config flow for iCalendar API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import secrets
import re
from urllib.parse import quote

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_USER, FlowType
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CONF_CALENDAR_ENTITY_ID,
    CONF_CALENDAR_ENTITY_IDS,
    CONF_FEED_NAME,
    CONF_FUTURE_WEEKS,
    CONF_HISTORY_WEEKS,
    CONF_SELECTION_MODE,
    DEFAULT_FUTURE_WEEKS,
    DEFAULT_HISTORY_WEEKS,
    MAX_FEED_NAME_LENGTH,
    MAX_FUTURE_WEEKS,
    MAX_HISTORY_WEEKS,
    MODE_INCLUDE,
    MODE_EXCLUDE,
    CONF_SECRET,
    DOMAIN,
    NAME,
    URL_PATH_PREFIX,
)

from .models import calendar_range, calendar_selection, feed_name
from .location import CONF_GEOCODING_URL, is_valid_geocoding_url


def _generate_secret() -> str:
    """Generate a URL-safe secret."""
    return secrets.token_urlsafe(24)


def _is_secret_valid(secret: str) -> bool:
    """Validate secret length/strength for URL auth."""
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{20,}", secret))


def _build_feed_urls(hass: HomeAssistant, entry_id: str, secret: str) -> tuple[str, str]:
    """Build local/internal and external URLs where available."""
    path = f"{URL_PATH_PREFIX}/{entry_id}/{quote(secret, safe='')}.ics"

    local_base = hass.config.internal_url or ""
    external_base = hass.config.external_url or ""

    local_url = f"{local_base.rstrip('/')}{path}" if local_base else ""
    external_url = f"{external_base.rstrip('/')}{path}" if external_base else ""

    return local_url, external_url


def _build_urls_text(local_url: str, external_url: str) -> str:
    """Create URL description block with only available URLs."""
    lines: list[str] = []
    if local_url:
        lines.append(f"Current local URL:\n{local_url}")
    if external_url:
        lines.append(f"Current external URL:\n{external_url}")
    return "\n".join(lines)


def _title_for_selection(mode: str, entity_ids: list[str], custom_name: str = "") -> str:
    """Build a title describing the feed selection."""
    if custom_name:
        return custom_name
    return f"{NAME} ({mode}: {', '.join(entity_ids) or 'none'})"


def _selection_errors(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, str]:
    if not is_valid_geocoding_url(data.get(CONF_GEOCODING_URL, "")):
        return {CONF_GEOCODING_URL: "invalid_geocoding_url"}
    mode, entities = calendar_selection(data)
    if mode not in (MODE_INCLUDE, MODE_EXCLUDE):
        return {CONF_SELECTION_MODE: "invalid_selection_mode"}
    if mode == MODE_INCLUDE and not entities:
        return {CONF_CALENDAR_ENTITY_IDS: "no_calendars"}
    if any(not entity.startswith("calendar.") or hass.states.get(entity) is None
           for entity in entities):
        return {CONF_CALENDAR_ENTITY_IDS: "entity_not_found"}
    try:
        history_weeks, future_weeks = calendar_range(data)
    except (TypeError, ValueError):
        return {CONF_HISTORY_WEEKS: "invalid_range"}
    if not (0 <= history_weeks <= MAX_HISTORY_WEEKS):
        return {CONF_HISTORY_WEEKS: "invalid_range"}
    if not (0 < future_weeks <= MAX_FUTURE_WEEKS):
        return {CONF_FUTURE_WEEKS: "invalid_range"}
    if len(feed_name(data)) > MAX_FEED_NAME_LENGTH:
        return {CONF_FEED_NAME: "feed_name_too_long"}
    return {}


def _same_selection(data: Mapping[str, Any], mode: str, entities: list[str]) -> bool:
    existing_mode, existing_entities = calendar_selection(data)
    return existing_mode == mode and set(existing_entities) == set(entities)


class ICalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iCalendar API."""

    VERSION = 1

    async def async_on_create_entry(self, result):
        """Continue to options flow after setup to show the generated feed URL."""
        if self.source != SOURCE_USER:
            return result

        options_result = await self.hass.config_entries.options.async_init(result["result"].entry_id)
        result["next_flow"] = (FlowType.OPTIONS_FLOW, options_result["flow_id"])
        return result

    async def async_step_user(self, user_input: Mapping[str, Any] | None = None):
        """Handle initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mode, entity_ids = calendar_selection(user_input)
            history_weeks, future_weeks = calendar_range(user_input)
            custom_name = feed_name(user_input)
            if errors := _selection_errors(self.hass, user_input):
                return self.async_show_form(
                    step_id="user", data_schema=_build_user_schema(user_input), errors=errors
                )
            for entry in self._async_current_entries():
                if _same_selection(entry.data, mode, entity_ids):
                    return self.async_abort(reason="already_configured")

            secret = _generate_secret()
            data = {
                CONF_GEOCODING_URL: user_input.get(CONF_GEOCODING_URL, "").strip(),
                CONF_CALENDAR_ENTITY_IDS: entity_ids,
                CONF_SELECTION_MODE: mode,
                CONF_HISTORY_WEEKS: history_weeks,
                CONF_FUTURE_WEEKS: future_weeks,
                CONF_FEED_NAME: custom_name,
                CONF_SECRET: secret,
            }

            return self.async_create_entry(
                title=_title_for_selection(mode, entity_ids, custom_name),
                data=data,
            )

        return self.async_show_form(step_id="user", data_schema=_build_user_schema(), errors=errors)

    async def async_step_reconfigure(self, user_input: Mapping[str, Any] | None = None):
        """Handle reconfiguration from the UI."""
        entry = self._get_reconfigure_entry()

        existing_secret = entry.data.get(CONF_SECRET, "")
        local_url, external_url = _build_feed_urls(self.hass, entry.entry_id, existing_secret)
        if user_input is not None:
            mode, entity_ids = calendar_selection(user_input)
            history_weeks, future_weeks = calendar_range(user_input)
            custom_name = feed_name(user_input)
            if errors := _selection_errors(self.hass, user_input):
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=_build_reconfigure_schema(entry),
                    errors=errors,
                    description_placeholders={
                        "url_block": _build_urls_text(local_url, external_url),
                    },
                )
            for existing_entry in self._async_current_entries():
                if (
                    existing_entry.entry_id != entry.entry_id
                    and _same_selection(existing_entry.data, mode, entity_ids)
                ):
                    return self.async_abort(reason="already_configured")

            updated_data = {
                **entry.data,
                CONF_GEOCODING_URL: user_input.get(CONF_GEOCODING_URL, "").strip(),
                CONF_CALENDAR_ENTITY_IDS: entity_ids,
                CONF_SELECTION_MODE: mode,
                CONF_HISTORY_WEEKS: history_weeks,
                CONF_FUTURE_WEEKS: future_weeks,
                CONF_FEED_NAME: custom_name,
            }

            updated_data.pop(CONF_CALENDAR_ENTITY_ID, None)

            new_secret = user_input.get(CONF_SECRET)
            if new_secret:
                if not _is_secret_valid(new_secret):
                    return self.async_show_form(
                        step_id="reconfigure",
                        data_schema=_build_reconfigure_schema(entry),
                        errors={CONF_SECRET: "invalid_secret"},
                        description_placeholders={
                            "url_block": _build_urls_text(local_url, external_url),
                        },
                    )
                updated_data[CONF_SECRET] = new_secret

            self.hass.config_entries.async_update_entry(
                entry,
                title=_title_for_selection(mode, entity_ids, custom_name),
                data=updated_data,
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_reconfigure_schema(entry),
            description_placeholders={
                "url_block": _build_urls_text(local_url, external_url),
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get options flow."""
        return ICalendarOptionsFlow()


class ICalendarOptionsFlow(config_entries.OptionsFlow):
    """Handle options for iCalendar API."""

    async def async_step_init(self, user_input: Mapping[str, Any] | None = None):
        """Manage options."""
        errors: dict[str, str] = {}
        existing_secret = self.config_entry.data.get(CONF_SECRET, "")
        local_url, external_url = _build_feed_urls(
            self.hass, self.config_entry.entry_id, existing_secret
        )
        if user_input is not None:
            mode, entity_ids = calendar_selection(user_input)
            history_weeks, future_weeks = calendar_range(user_input)
            custom_name = feed_name(user_input)
            errors = _selection_errors(self.hass, user_input)
            new_secret = user_input.get(CONF_SECRET)
            if new_secret and not _is_secret_valid(new_secret):
                errors[CONF_SECRET] = "invalid_secret"
            if not errors:
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if (
                        entry.entry_id != self.config_entry.entry_id
                        and _same_selection(entry.data, mode, entity_ids)
                    ):
                        errors["base"] = "already_configured"
                        break
            if errors:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_build_options_schema(self.config_entry, user_input),
                    errors=errors,
                    description_placeholders={
                        "url_block": _build_urls_text(local_url, external_url),
                    },
                )
            updated_data = {
                **self.config_entry.data,
                CONF_GEOCODING_URL: user_input.get(CONF_GEOCODING_URL, "").strip(),
                CONF_CALENDAR_ENTITY_IDS: entity_ids,
                CONF_SELECTION_MODE: mode,
                CONF_HISTORY_WEEKS: history_weeks,
                CONF_FUTURE_WEEKS: future_weeks,
                CONF_FEED_NAME: custom_name,
                CONF_SECRET: new_secret or existing_secret,
            }
            updated_data.pop(CONF_CALENDAR_ENTITY_ID, None)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                title=_title_for_selection(mode, entity_ids, custom_name),
                data=updated_data,
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(self.config_entry),
            description_placeholders={
                "url_block": _build_urls_text(local_url, external_url),
            },
        )


def _build_user_schema(user_input: Mapping[str, Any] | None = None) -> vol.Schema:
    """Build the calendar selection schema."""
    mode, entity_ids = calendar_selection(user_input or {})
    history_weeks, future_weeks = calendar_range(user_input or {})
    return vol.Schema({
        vol.Required(CONF_SELECTION_MODE, default=mode): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[MODE_INCLUDE, MODE_EXCLUDE], translation_key="selection_mode"
            )
        ),
        vol.Required(CONF_CALENDAR_ENTITY_IDS, default=entity_ids): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["calendar"], multiple=True)
        ),
        vol.Optional(CONF_FEED_NAME, default=feed_name(user_input or {})): vol.All(
            str, vol.Length(max=MAX_FEED_NAME_LENGTH)
        ),
        vol.Optional(CONF_GEOCODING_URL, default=(user_input or {}).get(CONF_GEOCODING_URL, "")): str,
        vol.Required(CONF_HISTORY_WEEKS, default=history_weeks): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=MAX_HISTORY_WEEKS, step=1, mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="weeks",
            )
        ),
        vol.Required(CONF_FUTURE_WEEKS, default=future_weeks): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1, max=MAX_FUTURE_WEEKS, step=1, mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="weeks",
            )
        ),
    })


def _build_reconfigure_schema(entry: config_entries.ConfigEntry) -> vol.Schema:
    """Build reconfigure schema with legacy selection defaults."""
    return _build_user_schema(entry.data).extend({
        vol.Optional(CONF_SECRET, default=entry.data.get(CONF_SECRET, "")): str,
    })


def _build_options_schema(
    entry: config_entries.ConfigEntry,
    user_input: Mapping[str, Any] | None = None,
) -> vol.Schema:
    """Build settings with the current selection or submitted values."""
    data = entry.data if user_input is None else user_input
    return _build_user_schema(data).extend({
        vol.Optional(CONF_SECRET, default=data.get(CONF_SECRET, "")): str,
    })
