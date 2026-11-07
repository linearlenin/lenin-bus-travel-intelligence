"""Collect bus listings from the web with a deterministic local fallback."""

import csv
import math
import os
import zlib
from typing import Dict, List, Tuple

from src.zuelpay_api import is_configured, search_buses

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
CSV_PATH = os.path.join(DATA_DIR, "bus_raw.csv")


CITY_COORDINATES: Dict[str, Tuple[float, float]] = {
    "bangalore": (12.97, 77.59), "bengaluru": (12.97, 77.59),
    "chennai": (13.08, 80.27), "coimbatore": (11.02, 76.96),
    "trichy": (10.79, 78.70), "tiruchirappalli": (10.79, 78.70),
    "namakkal": (11.22, 78.17), "namakal": (11.22, 78.17),
    "vellore": (12.92, 79.13), "kochi": (9.93, 76.27),
    "hyderabad": (17.39, 78.49), "pune": (18.52, 73.86),
    "mumbai": (19.08, 72.88), "bombay": (19.08, 72.88),
    "delhi": (28.61, 77.21), "new delhi": (28.61, 77.21),
    "jaipur": (26.91, 75.79), "ahmedabad": (23.02, 72.57),
    "goa": (15.49, 73.83), "vijayawada": (16.51, 80.65),
}

CITY_ALIASES = {
    "bengaluru": "Bangalore",
    "bombay": "Mumbai",
    "new delhi": "Delhi",
    "tiruchirappalli": "Trichy",
    "namakal": "Namakkal",
}


def normalize_city(city: str) -> str:
    """Return a stable display name while accepting common Indian city aliases."""
    cleaned = " ".join(city.strip().split())
    return CITY_ALIASES.get(cleaned.casefold(), cleaned.title())


def _road_distance_km(source: str, destination: str) -> int:
    start = CITY_COORDINATES.get(source.casefold())
    end = CITY_COORDINATES.get(destination.casefold())
    if not start or not end:
        return 350
    lat1, lon1 = map(math.radians, start)
    lat2, lon2 = map(math.radians, end)
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return max(60, int(6371 * 2 * math.asin(math.sqrt(a)) * 1.25))


def fallback_buses(source: str, destination: str) -> List[Dict[str, str]]:
    source = normalize_city(source)
    destination = normalize_city(destination)
    route = f"{source} to {destination}"
    if source.casefold() == "chennai" and destination.casefold() in {"bangalore", "bengaluru"}:
        return [
            {"operator": "KPN Travels", "route": route, "departure": "21:30", "duration": "6h 30m", "seat_type": "AC Sleeper", "price": "₹750"},
            {"operator": "IntrCity SmartBus", "route": route, "departure": "22:15", "duration": "5h 45m", "seat_type": "AC Seater", "price": "₹599"},
            {"operator": "SRS Travels", "route": route, "departure": "20:00", "duration": "7h 00m", "seat_type": "Non-AC Sleeper", "price": "₹499"},
            {"operator": "GreenLine Travels", "route": route, "departure": "23:00", "duration": "6h 00m", "seat_type": "AC Sleeper", "price": "₹999"},
            {"operator": "SETC Express", "route": route, "departure": "19:30", "duration": "7h 30m", "seat_type": "Ultra Deluxe Non-AC", "price": "₹420"},
            {"operator": "Jabbar Travels", "route": route, "departure": "06:00", "duration": "6h 15m", "seat_type": "AC Semi-Sleeper", "price": "₹650"},
            {"operator": "Asian Xpress", "route": route, "departure": "14:00", "duration": "6h 00m", "seat_type": "AC Sleeper", "price": "₹850"},
        ]

    distance = _road_distance_km(source, destination)
    route_seed = zlib.crc32(f"{source.casefold()}:{destination.casefold()}".encode())
    base_hours = max(2.0, distance / 52) + (route_seed % 25) / 100
    south_cities = {
        "chennai", "bangalore", "bengaluru", "coimbatore", "madurai",
        "vellore", "kochi", "hyderabad", "trichy", "tiruchirappalli",
        "namakkal", "namakal",
    }
    west_cities = {"mumbai", "bombay", "pune", "goa", "ahmedabad"}
    if source.casefold() in south_cities or destination.casefold() in south_cities:
        operator_pool = ["KPN Travels", "SRS Travels", "IntrCity SmartBus", "Orange Travels", "VRL Travels", "SETC Express", "Parveen Travels"]
    elif source.casefold() in west_cities or destination.casefold() in west_cities:
        operator_pool = ["Neeta Travels", "MSRTC Express", "VRL Travels", "Gujarat Travels", "Purple Bus", "IntrCity SmartBus", "Sharma Transports"]
    else:
        operator_pool = ["RSRTC Roadways", "Rajdhani Travels", "ZingBus", "UPSRTC Express", "IntrCity SmartBus", "National Travels", "Highway King"]
    offset = route_seed % len(operator_pool)
    operators = [operator_pool[(index + offset) % len(operator_pool)] for index in range(7)]
    seat_pool = ["AC Sleeper", "AC Seater", "Non-AC Sleeper", "AC Semi-Sleeper", "Non-AC Seater"]
    seats = [seat_pool[(index + route_seed) % len(seat_pool)] for index in range(7)]
    rates = [2.0, 1.7, 1.35, 2.5, 1.1, 1.85, 2.2]
    prices = [max(250, int(distance * rate / 10) * 10) for rate in rates]
    # Derive a different, stable schedule for every route instead of reusing
    # the same seven template times across all city pairs.
    departure_start = 4 * 60 + (route_seed % (19 * 60))
    departures = [
        f"{((departure_start + index * (97 + (route_seed % 29))) // 60) % 24:02d}:"
        f"{(departure_start + index * (97 + (route_seed % 29))) % 60:02d}"
        for index in range(7)
    ]
    rows = []
    for index in range(7):
        minutes = int((base_hours + ((route_seed >> (index % 8)) % 5) * 0.18) * 60)
        rows.append(
            {
                "operator": operators[index],
                "route": route,
                "departure": departures[index],
                "duration": f"{minutes // 60}h {minutes % 60:02d}m",
                "seat_type": seats[index],
                "price": f"₹{prices[index]}",
            }
        )
    return rows


def scrape_bus_data(source: str = "Chennai", destination: str = "Bangalore") -> int:
    """Fetch live inventory when ZuelPay is configured, otherwise use local demo data."""
    os.makedirs(DATA_DIR, exist_ok=True)
    dataset = search_buses(source, destination) if is_configured() else fallback_buses(source, destination)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(dataset[0]))
        writer.writeheader()
        writer.writerows(dataset)
    print(f"Scraper complete: {len(dataset)} records stored at {CSV_PATH}")
    return len(dataset)


if __name__ == "__main__":
    scrape_bus_data()
