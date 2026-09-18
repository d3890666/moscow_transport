"""DataUpdateCoordinator for Moscow Transport integration."""
from __future__ import annotations

import datetime
from datetime import timedelta
import logging
from typing import Any

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
    import homeassistant.util.dt as dt_util
except ImportError:
    from typing import Generic, TypeVar
    _T = TypeVar("_T")

    ConfigEntry = Any  # type: ignore[misc,assignment]
    HomeAssistant = Any  # type: ignore[misc,assignment]

    class DataUpdateCoordinator(Generic[_T]):  # type: ignore[no-redef]
        """Fallback coordinator."""

    class UpdateFailed(Exception):  # type: ignore[misc]
        """Fallback error."""

    dt_util = None



from .api import CannotConnect, InvalidStopId, MoscowTransportApiClient
from .const import (
    CONF_ROUTES,
    CONF_SCAN_INTERVAL,
    CONF_STOP_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .data_mapper import get_closest_route

_LOGGER = logging.getLogger(__name__)


class MoscowTransportCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching Moscow Transport data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.entry = entry
        self.stop_id: str = entry.data[CONF_STOP_ID]
        self.session = async_get_clientsession(hass)
        self.client = MoscowTransportApiClient(self.session)

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.stop_id}",
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def configured_routes(self) -> list[str]:
        """Return configured route filters from options or data."""
        return self.entry.options.get(
            CONF_ROUTES, self.entry.data.get(CONF_ROUTES, [])
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest transport data from API."""
        try:
            stop_info = await self.client.async_get_stop_info(self.stop_id)
        except (CannotConnect, InvalidStopId) as err:
            raise UpdateFailed(f"Error fetching data for stop {self.stop_id}: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error for stop {self.stop_id}: {err}") from err

        return self._process_stop_data(stop_info)

    def _process_stop_data(self, stop_info: dict[str, Any]) -> dict[str, Any]:
        """Process and structure raw stop data for entities and Lovelace cards."""
        routes_filter = self.configured_routes
        closest = get_closest_route(stop_info, routes_filter)

        routes_dict: dict[str, list[str]] = {}
        routes_forecasts: dict[str, list[dict[str, Any]]] = {}
        all_arrivals: list[dict[str, Any]] = []

        for route in stop_info.get("routePath", []):
            route_number = route.get("number")
            if not route_number:
                continue

            if routes_filter and route_number not in routes_filter:
                continue

            forecast_list: list[dict[str, Any]] = []
            formatted_strings: list[str] = []

            for event in route.get("externalForecast", []):
                sec = event.get("time", 0)
                by_telemetry = event.get("byTelemetry", 0)
                telemetry_suffix = "" if by_telemetry == 1 else "*"

                now_dt = dt_util.now() if dt_util else datetime.datetime.now()
                arrival_dt = now_dt + timedelta(seconds=sec)
                time_str = arrival_dt.strftime("%H:%M")
                mins = max(0, sec // 60)

                item = {
                    "route": route_number,
                    "time_seconds": sec,
                    "minutes": mins,
                    "time_formatted": f"{time_str}{telemetry_suffix}",
                    "arrival_time": arrival_dt.isoformat(),
                    "by_telemetry": by_telemetry,
                }
                forecast_list.append(item)
                all_arrivals.append(item)
                formatted_strings.append(f"{time_str}{telemetry_suffix}")

            if formatted_strings:
                routes_dict[route_number] = formatted_strings
                routes_forecasts[route_number] = forecast_list

        # Sort all arrivals by arrival time in seconds
        all_arrivals.sort(key=lambda x: x["time_seconds"])

        return {
            "stop_id": self.stop_id,
            "stop_name": stop_info.get("name", ""),
            "closest_route": closest,
            "routes": routes_dict,
            "routes_forecasts": routes_forecasts,
            "all_arrivals": all_arrivals,
            "raw": stop_info,
        }
