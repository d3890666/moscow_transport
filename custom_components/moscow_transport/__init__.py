"""Moscow Transport integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

import os
from typing import Any

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


FRONTEND_URL = "/moscow_transport/moscow-transport-card.js"
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "frontend", "moscow-transport-card.js")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Moscow Transport component and register static assets."""
    hass.data.setdefault(DOMAIN, {})

    # Register Lovelace card static path
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
            _LOGGER.debug("Static path registration skipped or failed: %s", err)

    return True



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Moscow Transport from a config entry."""
    hass.data.setdefault(DOMAIN, {})

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
