"""Sensor platform for Moscow Transport integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_NAME, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util
from homeassistant.util import slugify

from . import data_mapper
from .const import (
    ATTRIBUTION,
    CONF_ROUTES,
    CONF_STOP_ID,
    DEFAULT_NAME,
    DOMAIN,
    STOP_NAME,
    USER_AGENT,
)
from .coordinator import MoscowTransportCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_ROUTE = "routes"
INTEGRATION_NAME = DOMAIN

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Optional(CONF_NAME, default=""): cv.string,
        vol.Optional(CONF_ROUTE, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Moscow Transport sensor from config entry."""
    coordinator: MoscowTransportCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MoscowTransportSensor(coordinator, entry)])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the moscow transport sensor from YAML and trigger import."""
    # Trigger Config Flow import for modern UI management
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=dict(config),
        )
    )

    stop_id = config[CONF_STOP_ID]
    name = config[CONF_NAME]
    routes = config[CONF_ROUTE]
    session = async_create_clientsession(hass)

    async_add_entities(
        [LegacyMoscowTransportSensor(session, stop_id, routes, name)], True
    )


def get_telemetry_suffix(by_telemetry: int | None) -> str:
    """Return asterisk if data is from schedule, empty string if GPS telemetry."""
    return "" if by_telemetry == 1 else "*"


class MoscowTransportSensor(CoordinatorEntity[MoscowTransportCoordinator], SensorEntity):
    """Modern Coordinator-backed Moscow Transport sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:bus-stop"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(
        self,
        coordinator: MoscowTransportCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self._stop_id = coordinator.stop_id
        self._custom_name = entry.data.get(CONF_NAME) or ""
        self._attr_unique_id = f"{self._stop_id}-moscow_transport"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for Home Assistant device registry."""
        stop_name = (
            self._custom_name
            or self.coordinator.data.get("stop_name")
            or DEFAULT_NAME
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self._stop_id)},
            name=f"Остановка {stop_name}",
            manufacturer="Московский транспорт",
            model="Остановка общественного транспорта",
            configuration_url=f"https://moscowtransport.app/api/stop_v2/{self._stop_id}",
        )

    @property
    def name(self) -> str:
        """Return friendly name with closest route."""
        data = self.coordinator.data or {}
        base_name = self._custom_name or data.get("stop_name") or DEFAULT_NAME
        closest = data.get("closest_route")
        if closest and len(closest) >= 3:
            suffix = get_telemetry_suffix(closest[2])
            return f"{base_name} ({closest[0]}{suffix})"
        return base_name

    @property
    def native_value(self) -> Any:
        """Return ETA timestamp of closest bus."""
        data = self.coordinator.data or {}
        closest = data.get("closest_route")
        if closest and len(closest) >= 2 and closest[1] is not None:
            return dt_util.utcnow() + timedelta(seconds=closest[1])
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.data or {}
        attrs: dict[str, Any] = dict(data.get("routes", {}))

        attrs[STOP_NAME] = data.get("stop_name", "")
        attrs["stop_id"] = self._stop_id
        attrs["all_arrivals"] = data.get("all_arrivals", [])
        attrs["routes_forecasts"] = data.get("routes_forecasts", {})

        closest = data.get("closest_route")
        if closest and len(closest) >= 3:
            attrs["closest_route"] = closest[0]
            attrs["closest_seconds"] = closest[1]
            attrs["closest_by_telemetry"] = closest[2]

        return attrs


class LegacyMoscowTransportSensor(SensorEntity):
    """Legacy implementation of moscow_transport sensor for backwards compatibility."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:bus"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, session, stop_id, routes, name) -> None:
        """Initialize legacy sensor."""
        self.session = session
        self._stop_id = stop_id
        self._routes = routes
        self._state = None
        self._name = name or DEFAULT_NAME
        self._custom_name = name
        self._attrs: dict[str, Any] | None = None
        self.entity_id = f"sensor.{stop_id}_{INTEGRATION_NAME}"
        self._attr_unique_id = f"{self._stop_id}-moscow_transport"

    async def async_update(self, *, tries=0) -> None:
        """Get the latest data from API and update state."""
        attrs: dict[str, Any] = {}

        try:
            stop_info = await self.get_stop_info()
        except Exception:
            _LOGGER.error(
                "Ошибка запроса к stop_id=%s, %s",
                self._stop_id,
                self._custom_name or self._name,
            )
            return

        if stop_info is None:
            return

        self._name = self._custom_name or stop_info.get("name", DEFAULT_NAME)
        slugify_name = slugify(f"{self._name}_{INTEGRATION_NAME}")
        self.entity_id = f"sensor.{slugify_name}"

        closest_route = data_mapper.get_closest_route(stop_info, self._routes)
        if closest_route:
            telemetry_suffix = get_telemetry_suffix(closest_route[2])
            self._name = f"{self._name} ({closest_route[0]}{telemetry_suffix})"
            self._state = dt_util.utcnow() + timedelta(seconds=closest_route[1])

        for route in stop_info.get("routePath", []):
            route_num = route.get("number")
            if self._routes and route_num not in self._routes:
                continue

            for event in route.get("externalForecast", []):
                if route_num not in attrs:
                    attrs[route_num] = []

                route_time = dt_util.now() + timedelta(seconds=event["time"])
                time_formatted = route_time.strftime("%H:%M")
                telemetry_suffix = get_telemetry_suffix(event["byTelemetry"])
                attrs[route_num].append(f"{time_formatted}{telemetry_suffix}")

        attrs[STOP_NAME] = stop_info.get("name", "")
        self._attrs = attrs

    async def get_stop_info(self) -> dict[str, Any]:
        """Fetch stop data directly."""
        request_url = f"https://moscowtransport.app/api/stop_v2/{self._stop_id}"
        headers = {"User-Agent": USER_AGENT}

        response = await self.session.request(
            "GET", request_url, headers=headers, timeout=10
        )
        data = await response.json()
        if data.get("name") == "Exception":
            error_message = f"Нет остановки с stop_id={self._stop_id}"
            _LOGGER.error(error_message)
            raise Exception(error_message)
        return data

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self._state

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return self._attrs
