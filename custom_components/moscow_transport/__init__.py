"""Moscow Transport integration for Home Assistant."""
from __future__ import annotations

import logging
import os
from typing import Any

from .const import DOMAIN
from .coordinator import MoscowTransportCoordinator

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    PLATFORMS: list[Platform] = [Platform.SENSOR]
except ImportError:
    ConfigEntry = Any  # type: ignore[misc,assignment]
    Platform = Any  # type: ignore[misc,assignment]
    HomeAssistant = Any  # type: ignore[misc,assignment]
    ConfigType = Any  # type: ignore[misc,assignment]
    PLATFORMS = ["sensor"]  # type: ignore[assignment]

_LOGGER = logging.getLogger(__name__)

FRONTEND_URL = "/moscow_transport/moscow-transport-card.js"
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "frontend", "moscow-transport-card.js")


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register Lovelace frontend card and resources."""
    if hass.data.setdefault(f"{DOMAIN}_frontend_registered", False):
        return
    hass.data[f"{DOMAIN}_frontend_registered"] = True

    # 1. Register static path in HTTP server
    if hasattr(hass, "http"):
        try:
            if hasattr(hass.http, "async_register_static_paths"):
                from homeassistant.components.http import StaticPathConfig
                await hass.http.async_register_static_paths([
                    StaticPathConfig(FRONTEND_URL, FRONTEND_PATH, cache_headers=False)
                ])
            elif hasattr(hass.http, "register_static_path"):
                hass.http.register_static_path(FRONTEND_URL, FRONTEND_PATH, cache_headers=False)
        except Exception as err:
            _LOGGER.debug("Static path registration failed: %s", err)

    # 2. Automatically register extra JS URL in Lovelace frontend
    try:
        from homeassistant.components.frontend import add_extra_js_url
        add_extra_js_url(hass, FRONTEND_URL)
        _LOGGER.debug("Added extra JS url: %s", FRONTEND_URL)
    except Exception as err:
        _LOGGER.debug("Could not add extra JS URL: %s", err)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Moscow Transport component, register static assets and services."""
    hass.data.setdefault(DOMAIN, {})
    await async_register_frontend(hass)

    # Register LLM/Assist action: moscow_transport.get_arrivals
    async def handle_get_arrivals(call: Any) -> dict[str, Any]:
        """Handle get_arrivals action for automations and LLM agents."""
        target_entity = call.data.get("entity_id")
        target_route = call.data.get("route")
        target_stop_id = call.data.get("stop_id")

        if target_route:
            target_route = str(target_route).strip()

        # Find coordinator
        coordinators: list[MoscowTransportCoordinator] = [
            c for c in hass.data.get(DOMAIN, {}).values()
            if isinstance(c, MoscowTransportCoordinator)
        ]

        if not coordinators:
            return {
                "error": "Интеграция 'Московский транспорт' не настроена или нет активных остановок."
            }

        selected_coordinator = None
        if target_stop_id:
            for c in coordinators:
                if c.stop_id == target_stop_id:
                    selected_coordinator = c
                    break
        elif target_entity:
            for c in coordinators:
                if c.stop_id in str(target_entity):
                    selected_coordinator = c
                    break

        if not selected_coordinator:
            selected_coordinator = coordinators[0]

        data = selected_coordinator.data or {}
        stop_name = selected_coordinator.entry.data.get("name") or data.get("stop_name") or "Остановка"
        all_arrivals = data.get("all_arrivals", [])

        # Filter by route if specified
        if target_route:
            filtered_arrivals = [a for a in all_arrivals if str(a.get("route")) == target_route]
        else:
            filtered_arrivals = all_arrivals

        arrivals_list = []
        for arr in filtered_arrivals[:10]:
            is_live_gps = arr.get("by_telemetry") == 1
            arrivals_list.append({
                "route": arr.get("route"),
                "minutes": arr.get("minutes"),
                "time": arr.get("time_formatted", "").replace("*", ""),
                "is_live_gps": is_live_gps,
            })

        if target_route:
            if arrivals_list:
                first = arrivals_list[0]
                tel_text = "по живой GPS-телеметрии" if first["is_live_gps"] else "по расписанию"
                summary = f"Автобус {target_route} прибудет на остановку '{stop_name}' через {first['minutes']} мин ({first['time']}, {tel_text})."
                if len(arrivals_list) > 1:
                    next_str = ", ".join([f"{a['minutes']} мин" for a in arrivals_list[1:4]])
                    summary += f" Следующие рейсы: {next_str}."
            else:
                summary = f"Сейчас нет данных о приближении автобуса {target_route} к остановке '{stop_name}'."
        else:
            if arrivals_list:
                first = arrivals_list[0]
                tel_text = "по GPS" if first["is_live_gps"] else "по расписанию"
                summary = f"Ближайший транспорт на остановке '{stop_name}': автобус {first['route']} через {first['minutes']} мин ({tel_text})."
                others = [f"{a['route']} ({a['minutes']} мин)" for a in arrivals_list[1:5]]
                if others:
                    summary += f" Также ожидаются: {', '.join(others)}."
            else:
                summary = f"На остановке '{stop_name}' сейчас нет активных рейсов."

        return {
            "stop_name": stop_name,
            "stop_id": selected_coordinator.stop_id,
            "target_route": target_route,
            "arrivals_count": len(arrivals_list),
            "arrivals": arrivals_list,
            "summary": summary,
        }

    try:
        from homeassistant.core import SupportsResponse
        supports_resp = SupportsResponse.ONLY
    except Exception:
        supports_resp = None

    if hasattr(hass, "services") and not hass.services.has_service(DOMAIN, "get_arrivals"):
        if supports_resp:
            hass.services.async_register(
                DOMAIN,
                "get_arrivals",
                handle_get_arrivals,
                supports_response=supports_resp,
            )
        else:
            hass.services.async_register(
                DOMAIN,
                "get_arrivals",
                handle_get_arrivals,
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Moscow Transport from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await async_register_frontend(hass)

    coordinator = MoscowTransportCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry after options change."""
    await hass.config_entries.async_reload(entry.entry_id)
