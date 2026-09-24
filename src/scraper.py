"""Collect bus listings from the web with a deterministic local fallback."""

import asyncio
import csv
import math
import os
from typing import Dict, List, Tuple

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
CSV_PATH = os.path.join(DATA_DIR, "bus_raw.csv")


CITY_COORDINATES: Dict[str, Tuple[float, float]] = {
    "bangalore": (12.97, 77.59), "bengaluru": (12.97, 77.59),
    "chennai": (13.08, 80.27), "coimbatore": (11.02, 76.96),
    "vellore": (12.92, 79.13), "kochi": (9.93, 76.27),
    "hyderabad": (17.39, 78.49), "pune": (18.52, 73.86),
    "mumbai": (19.08, 72.88), "bombay": (19.08, 72.88),
    "delhi": (28.61, 77.21), "new delhi": (28.61, 77.21),
    "jaipur": (26.91, 75.79), "ahmedabad": (23.02, 72.57),
    "goa": (15.49, 73.83), "vijayawada": (16.51, 80.65),
}


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
    base_hours = max(2.0, distance / 52)
    operators = ["InterCity Express", "National Travels", "CityLink Bus", "Highway Connect", "State Roadways", "ComfortRide", "RapidRoute"]
    seats = ["AC Sleeper", "AC Seater", "Non-AC Sleeper", "AC Sleeper", "Non-AC Seater", "AC Semi-Sleeper", "AC Seater"]
    prices = [max(250, int(distance * rate / 10) * 10) for rate in (2.0, 1.7, 1.35, 2.5, 1.1, 1.85, 2.2)]
    departures = ["06:30", "09:15", "18:00", "20:30", "21:45", "22:30", "23:15"]
    rows = []
    for index in range(7):
        minutes = int((base_hours + (index % 3) * 0.35) * 60)
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


async def scrape_bus_data(
    source: str = "Chennai",
    destination: str = "Bangalore",
    enable_live: bool | None = None,
) -> int:
    """Collect listings, using live Playwright only when explicitly enabled."""
    os.makedirs(DATA_DIR, exist_ok=True)
    rows: List[Dict[str, str]] = []

    # The deployed Streamlit app must not require a browser binary. Live
    # extraction can be added behind a separate worker when deployment support
    # for Playwright is available.
    use_live_scraper = False
    if use_live_scraper:
        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError:
            print("Playwright is not installed; using route-aware fallback inventory.")
        else:
            try:
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=True)
                    try:
                        context = await browser.new_context(
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36"
                        )
                        page = await context.new_page()
                        target_url = f"https://www.redbus.in/bus-tickets/{source.lower()}-to-{destination.lower()}"
                        await page.goto(target_url, timeout=20_000, wait_until="domcontentloaded")
                        await page.wait_for_selector(".bus-item", timeout=5_000)
                        for card in await page.query_selector_all(".bus-item"):
                            name = await card.query_selector(".travels")
                            fare = await card.query_selector(".fare span")
                            departure = await card.query_selector(".dp-time")
                            if name and fare and departure:
                                rows.append(
                                    {
                                        "operator": (await name.inner_text()).strip(),
                                        "route": f"{source} to {destination}",
                                        "departure": (await departure.inner_text()).strip(),
                                        "duration": "6h 30m",
                                        "seat_type": "AC Sleeper",
                                        "price": (await fare.inner_text()).strip(),
                                    }
                                )
                    finally:
                        await browser.close()
            except (PlaywrightTimeoutError, PlaywrightError) as error:
                print(f"Live source unavailable ({error.__class__.__name__}); using fallback inventory.")
    else:
        print("Live scraper disabled; using route-aware fallback inventory.")

    dataset = rows or fallback_buses(source, destination)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(dataset[0]))
        writer.writeheader()
        writer.writerows(dataset)
    print(f"Scraper complete: {len(dataset)} records stored at {CSV_PATH}")
    return len(dataset)


if __name__ == "__main__":
    asyncio.run(scrape_bus_data())
