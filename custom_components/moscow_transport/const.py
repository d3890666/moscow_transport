"""Constants for Moscow Transport integration."""
from __future__ import annotations

import re
from typing import Final

DOMAIN: Final = "moscow_transport"

CONF_STOP_ID: Final = "stop_id"
CONF_STOP_INPUT: Final = "stop_input"
CONF_ROUTES: Final = "routes"
CONF_NAME: Final = "name"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_NAME: Final = "Moscow Transport"
DEFAULT_SCAN_INTERVAL: Final = 60
MIN_SCAN_INTERVAL: Final = 15

STOP_NAME: Final = "stop_name"
ALL_ROUTES: Final = "all"

USER_AGENT: Final = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
API_STOP_URL: Final = "https://moscowtransport.app/api/stop_v2/{}"
ATTRIBUTION: Final = "Данные Московского транспорта по телеметрии (* - данные из расписания)"

UUID_REGEX = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def extract_stop_id_from_input(user_input: str) -> str | None:
    """Extract stop UUID from raw user input (UUID string or URL)."""
    if not user_input:
        return None
    match = UUID_REGEX.search(user_input.strip())
    if match:
        return match.group(0).lower()
    return None
