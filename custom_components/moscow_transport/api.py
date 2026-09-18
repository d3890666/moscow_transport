"""API client for Moscow Transport."""
from __future__ import annotations

import logging
from typing import Any
import aiohttp

from .const import (
    API_STOP_URL,
    USER_AGENT,
    extract_stop_id_from_input,
)

_LOGGER = logging.getLogger(__name__)


class MoscowTransportError(Exception):
    """Base exception for Moscow Transport errors."""


class CannotConnect(MoscowTransportError):
    """Exception to indicate connection error."""


class InvalidStopId(MoscowTransportError):
    """Exception to indicate invalid stop ID."""


class MoscowTransportApiClient:
    """Client for Moscow Transport API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize API client."""
        self._session = session

    async def async_resolve_stop_id(self, user_input: str) -> str:
        """Resolve stop ID from input (raw UUID, stop URL, or short sharing URL)."""
        clean_input = user_input.strip()
        stop_id = extract_stop_id_from_input(clean_input)
        if stop_id:
            return stop_id

        # If it's a URL without UUID in string (like short sharing link https://moscowapp.mos.ru/l/XYZ)
        if clean_input.startswith(("http://", "https://")):
            headers = {"User-Agent": USER_AGENT}
            try:
                # Follow redirects to get final URL
                async with self._session.get(
                    clean_input,
                    headers=headers,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    final_url = str(response.url)
                    stop_id = extract_stop_id_from_input(final_url)
                    if stop_id:
                        return stop_id
            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.warning("Failed to follow sharing URL redirect: %s", err)
                raise CannotConnect(f"Cannot resolve URL {clean_input}") from err

        raise InvalidStopId(f"Cannot extract valid stop UUID from input: {user_input}")

    async def async_get_stop_info(self, stop_id: str) -> dict[str, Any]:
        """Fetch stop data from API by stop UUID."""
        url = API_STOP_URL.format(stop_id)
        headers = {"User-Agent": USER_AGENT}

        try:
            async with self._session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    raise InvalidStopId(f"Stop {stop_id} returned HTTP status {response.status}")

                data = await response.json()
        except aiohttp.ClientError as err:
            raise CannotConnect(f"Error connecting to Moscow Transport API: {err}") from err
        except Exception as err:
            if isinstance(err, MoscowTransportError):
                raise
            raise CannotConnect(f"Unexpected error: {err}") from err

        if not isinstance(data, dict) or data.get("name") == "Exception":
            raise InvalidStopId(f"Stop with stop_id={stop_id} does not exist")

        return data

    @staticmethod
    def get_available_routes(stop_info: dict[str, Any]) -> list[str]:
        """Extract unique list of route numbers passing through the stop."""
        routes: list[str] = []
        for route in stop_info.get("routePath", []):
            num = route.get("number")
            if num and num not in routes:
                routes.append(num)
        return sorted(routes)
