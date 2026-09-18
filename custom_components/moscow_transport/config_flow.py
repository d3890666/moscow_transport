"""Config flow for Moscow Transport integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    CannotConnect,
    InvalidStopId,
    MoscowTransportApiClient,
)
from .const import (
    CONF_NAME,
    CONF_ROUTES,
    CONF_SCAN_INTERVAL,
    CONF_STOP_ID,
    CONF_STOP_INPUT,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class MoscowTransportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Moscow Transport."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._stop_id: str | None = None
        self._stop_name: str | None = None
        self._available_routes: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: enter stop URL or UUID."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_input = user_input.get(CONF_STOP_INPUT, "").strip()
            session = async_get_clientsession(self.hass)
            client = MoscowTransportApiClient(session)

            try:
                stop_id = await client.async_resolve_stop_id(stop_input)
                await self.async_set_unique_id(stop_id)
                self._abort_if_unique_id_configured()

                stop_info = await client.async_get_stop_info(stop_id)
                self._stop_id = stop_id
                self._stop_name = stop_info.get("name") or DEFAULT_NAME
                self._available_routes = client.get_available_routes(stop_info)

                return await self.async_step_routes()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidStopId:
                errors["base"] = "invalid_stop_id"
            except Exception as err:
                _LOGGER.exception("Unexpected exception in config flow: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP_INPUT): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            multiline=False,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the route selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME) or self._stop_name or DEFAULT_NAME
            routes = user_input.get(CONF_ROUTES) or []

            return self.async_create_entry(
                title=name,
                data={
                    CONF_STOP_ID: self._stop_id,
                    CONF_NAME: name,
                    CONF_ROUTES: routes,
                },
            )

        route_options = [
            selector.SelectOptionDict(value=r, label=r)
            for r in self._available_routes
        ]

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NAME,
                    default=self._stop_name or "",
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }
        )

        if route_options:
            data_schema = data_schema.extend(
                {
                    vol.Optional(
                        CONF_ROUTES,
                        default=[],
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=route_options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )

        return self.async_show_form(
            step_id="routes",
            data_schema=data_schema,
            description_placeholders={"stop_name": self._stop_name or ""},
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Import config from configuration.yaml."""
        stop_id = import_data.get(CONF_STOP_ID)
        if not stop_id:
            return self.async_abort(reason="invalid_stop_id")

        await self.async_set_unique_id(stop_id)
        self._abort_if_unique_id_configured()

        session = async_get_clientsession(self.hass)
        client = MoscowTransportApiClient(session)

        try:
            stop_info = await client.async_get_stop_info(stop_id)
            default_name = stop_info.get("name") or DEFAULT_NAME
        except Exception:
            default_name = DEFAULT_NAME

        name = import_data.get(CONF_NAME) or default_name
        routes = import_data.get(CONF_ROUTES) or []

        return self.async_create_entry(
            title=name,
            data={
                CONF_STOP_ID: stop_id,
                CONF_NAME: name,
                CONF_ROUTES: routes,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return MoscowTransportOptionsFlowHandler(config_entry)


class MoscowTransportOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Moscow Transport."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        stop_id = self.config_entry.data.get(CONF_STOP_ID)
        session = async_get_clientsession(self.hass)
        client = MoscowTransportApiClient(session)

        available_routes: list[str] = []
        stop_name = self.config_entry.title

        try:
            stop_info = await client.async_get_stop_info(stop_id)
            available_routes = client.get_available_routes(stop_info)
            if not stop_name:
                stop_name = stop_info.get("name") or DEFAULT_NAME
        except Exception as err:
            _LOGGER.warning("Could not fetch available routes for options flow: %s", err)

        # Merge already selected routes with available routes to avoid dropping unknown routes
        current_routes = self.config_entry.options.get(
            CONF_ROUTES, self.config_entry.data.get(CONF_ROUTES, [])
        )
        all_options = sorted(list(set(available_routes + current_routes)))

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        route_options = [
            selector.SelectOptionDict(value=r, label=r) for r in all_options
        ]

        schema_dict: dict[Any, Any] = {
            vol.Optional(
                CONF_ROUTES,
                default=current_routes,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=route_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=current_interval,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=600,
                    step=5,
                    unit_of_measurement="seconds",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"stop_name": stop_name},
        )
