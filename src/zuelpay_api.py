"""Small ZuelPay bus-search client with strict response normalization."""

import json
import os
from datetime import date
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("ZUELPAY_BASE_URL", "https://api.zuelpay.in")


def _secret(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name, ""))
    except (ImportError, KeyError, FileNotFoundError):
        return ""


def is_configured() -> bool:
    return bool(_secret("ZUELPAY_API_KEY") and _secret("ZUELPAY_CLIENT_SECRET"))


def _headers() -> Dict[str, str]:
    token = _secret("ZUELPAY_API_KEY")
    checksum = _secret("ZUELPAY_CHECKSUM") or _secret("ZUELPAY_CLIENT_SECRET")
    if not token or not checksum:
        raise ValueError("ZuelPay credentials are not configured.")
    return {
        "Content-Type": "application/json",
        "Token": token,
        "checkSum": checksum,
    }


def _first_value(row: Dict[str, Any], *names: str) -> Any:
    lowered = {str(key).casefold(): value for key, value in row.items()}
    for name in names:
        if name.casefold() in lowered:
            return lowered[name.casefold()]
    return ""


def _find_rows(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        rows = [item for item in value if isinstance(item, dict)]
        if rows:
            return rows
        for item in value:
            rows = _find_rows(item)
            if rows:
                return rows
    if isinstance(value, dict):
        for key in ("busList", "busDetails", "result", "data", "buses", "bus"):
            if key in value:
                rows = _find_rows(value[key])
                if rows:
                    return rows
        for item in value.values():
            rows = _find_rows(item)
            if rows:
                return rows
    return []


def _normalize(row: Dict[str, Any], source: str, destination: str) -> Dict[str, str]:
    operator = _first_value(row, "operator", "operatorName", "travels", "travelsName", "busOperator")
    departure = _first_value(row, "departure", "departureTime", "arrivalTime", "startTime")
    duration = _first_value(row, "duration", "travelTime", "journeyTime")
    seat_type = _first_value(row, "seatType", "busType", "busCategory", "serviceType")
    price = _first_value(row, "fare", "price", "baseFare", "ticketFare", "minimumFare")
    if not operator or not departure or price == "":
        return {}
    return {
        "operator": str(operator),
        "route": f"{source} to {destination}",
        "departure": str(departure),
        "duration": str(duration or "Not provided"),
        "seat_type": str(seat_type or "Bus service"),
        "price": f"₹{price}",
    }


def search_buses(source: str, destination: str, travel_date: str | None = None) -> List[Dict[str, str]]:
    """Fetch and normalize real ZuelPay search results for one route."""
    payload = {
        "sourceCity": source,
        "destinationCity": destination,
        "doj": travel_date or date.today().isoformat(),
    }
    request = Request(
        f"{BASE_URL.rstrip('/')}/travel/bus/searchBus",
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ZuelPay bus search failed: {exc}") from exc
    rows = [_normalize(row, source, destination) for row in _find_rows(body)]
    rows = [row for row in rows if row]
    if not rows:
        raise RuntimeError("ZuelPay returned no recognizable bus records for this route.")
    return rows
