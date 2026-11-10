"""Constraint extraction and Gemini response generation with an offline fallback."""

import os
import re
from typing import Any, Dict, List, Tuple

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - environment fallback
    def load_dotenv() -> None:
        return None

try:
    from langchain_core.documents import Document
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import PromptTemplate
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_google_genai._common import GoogleGenerativeAIError
except ImportError:  # pragma: no cover - optional AI dependencies may be absent
    class Document:  # type: ignore[override]
        def __init__(self, page_content: str, metadata: Dict[str, Any] | None = None):
            self.page_content = page_content
            self.metadata = metadata or {}

    StrOutputParser = None
    PromptTemplate = None
    ChatGoogleGenerativeAI = None
    GoogleGenerativeAIError = Exception

from src.scraper import get_route_buses, normalize_city
from src.time_format import format_departure_time
from src.vector_store import CLEANED_PATH, hybrid_search

load_dotenv()

PROMPT = """You are an expert Indian intercity bus travel assistant.
Use only the inventory context below. Never invent an operator, route, price,
time, or duration. If the context says no matching inventory was found, say
that clearly. Be concise and use markdown bullets.

Inventory context:
{context}

User question: {question}
"""


def extract_route(query: str) -> str | None:
    """Extract a route from either 'from X to Y' or 'Y bus from X' wording."""
    # Route text ends before any preference or information intent.
    route_end = r"(?=\s+(?:under|below|less than|within|budget|maximum|with|for|at|by|normal|ordinary|regular|non[\s-]?ac|ac|cheap|cheapest|affordable|best|fastest|quickest|timings?|schedule|operators?|buses?|bus)\b|$)"
    match = re.search(
        rf"\bfrom\s+([a-z][a-z .-]*?)\s+to\s+([a-z][a-z .-]*?){route_end}",
        query,
        re.IGNORECASE,
    )
    if match:
        return _format_route(match.group(1), match.group(2))

    match = re.search(
        rf"\b(?:(?:cheap|best|affordable|normal|ordinary|regular)\s+)?([a-z]+(?:\s+[a-z]+)?)\s+bus(?:es)?\s+from\s+([a-z][a-z .-]*?){route_end}",
        query,
        re.IGNORECASE,
    )
    if match:
        destination = match.group(1).strip().title()
        source = match.group(2).strip().title()
        return _format_route(source, destination)

    match = re.search(
        rf"\b(?:bus(?:es)?\s+)?([a-z]+(?:\s+[a-z]+)?)\s+to\s+([a-z]+(?:\s+[a-z]+)?){route_end}",
        query,
        re.IGNORECASE,
    )
    if match:
        return _format_route(match.group(1), match.group(2))
    return None


def _format_route(source: str, destination: str) -> str:
    return f"{normalize_city(source)} to {normalize_city(destination)}"


def extract_query_constraints(query: str) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    price = re.search(
        r"(?:under|below|less than|within|budget(?:\s+of)?|maximum(?:\s+of)?)\s*(?:₹|rs\.?|inr)?\s*(\d+)",
        query,
        re.IGNORECASE,
    )
    if price:
        filters["max_price"] = int(price.group(1))
    if re.search(r"\bnon[\s-]?ac\b", query, re.IGNORECASE):
        filters["normal_bus"] = True
    elif re.search(r"\bac[\s-]?sleeper\b|\bsleeper\b", query, re.IGNORECASE):
        filters["seat_type"] = "AC Sleeper"
    elif re.search(r"\bac\s+bus(?:es)?\b|\bair[-\s]?conditioned\s+bus(?:es)?\b", query, re.IGNORECASE):
        filters["ac_bus"] = True
    elif re.search(r"\b(normal|ordinary|regular|government)\s+bus", query, re.IGNORECASE):
        filters["normal_bus"] = True
    if re.search(r"\b(cheapest|cheapest fare|lowest price|most affordable)\b", query, re.IGNORECASE):
        filters["intent"] = "cheapest"
    elif re.search(r"\b(fastest|quickest|shortest travel time)\b", query, re.IGNORECASE):
        filters["intent"] = "fastest"
    elif re.search(r"\b(operator|operators|company|companies)\b", query, re.IGNORECASE):
        filters["intent"] = "operators"
    elif re.search(r"\b(timing|timings|schedule|departure|departures)\b", query, re.IGNORECASE):
        filters["intent"] = "timings"
    elif re.search(r"\b(all buses|every bus|show all|list all)\b", query, re.IGNORECASE):
        filters["intent"] = "all"
    return filters


def _offline_search(
    query: str,
    filters: Dict[str, Any],
    k: int = 4,
    route_inventory: List[Dict[str, Any]] | None = None,
) -> List[Document]:
    import pandas as pd

    frame = pd.DataFrame(route_inventory) if route_inventory is not None else pd.read_csv(CLEANED_PATH)
    if "price_inr" not in frame:
        frame["price_inr"] = frame["price"].astype(str).str.replace(r"[^\d]", "", regex=True).astype(int)
    if filters.get("max_price") is not None:
        frame = frame[frame["price_inr"] <= filters["max_price"]]
    if filters.get("min_price") is not None:
        frame = frame[frame["price_inr"] >= filters["min_price"]]
    if filters.get("seat_type"):
        frame = frame[frame["seat_type"].str.casefold() == filters["seat_type"].casefold()]
    if filters.get("normal_bus"):
        frame = frame[~frame["seat_type"].str.match(r"^AC\b", case=False, na=False)]
    if filters.get("ac_bus"):
        frame = frame[frame["seat_type"].str.match(r"^AC\b", case=False, na=False)]
    if filters.get("route"):
        frame = frame[frame["route"].str.casefold() == filters["route"].casefold()]
    words = set(re.findall(r"[a-z0-9]+", query.casefold()))
    frame = frame.copy()
    frame["_score"] = frame.apply(
        lambda row: len(words.intersection(set(re.findall(r"[a-z0-9]+", " ".join(map(str, row.values)))))),
        axis=1,
    )
    frame = frame.sort_values(["_score", "price_inr"], ascending=[False, True]).head(k)
    return [
        Document(
            page_content=(
                f"Bus Operator: {row.operator}. Route: {row.route}. Departure Time: {format_departure_time(getattr(row, 'departure_display', row.departure))}. "
                f"Duration: {row.duration}. Seating Category: {row.seat_type}. Ticket Fare: INR {row.price_inr}."
            ),
            metadata={"price_inr": int(row.price_inr)},
        )
        for row in frame.itertuples()
    ]


def _offline_response(documents: List[Document], question: str) -> str:
    if not documents:
        return "I could not find a matching bus in the current inventory. Try increasing your budget or broadening the seating preference."
    lines = [f"- {document.page_content}" for document in documents]
    return "Here are the matching buses from the current inventory:\n" + "\n".join(lines)


def process_travel_query(user_query: str, route: str | None = None) -> Tuple[str, int]:
    filters = extract_query_constraints(user_query)
    requested_route = extract_route(user_query)
    route = requested_route or route
    if route:
        filters["route"] = route
    # Recommendations are intentionally deterministic. This prevents an LLM
    # from inventing a route, fare, operator, or schedule not in the CSV.
    active_route = requested_route or route
    if not active_route or " to " not in active_route:
        documents = _offline_search(user_query, filters, k=4)
        return _offline_response(documents, user_query), len(documents)
    source, destination = active_route.split(" to ", maxsplit=1)
    intent = filters.pop("intent", None)
    result_limit = 7 if intent in {"all", "cheapest", "fastest", "operators", "timings"} else 4
    inventory, inventory_warning = get_route_buses(source, destination)
    documents = _offline_search(
        user_query,
        filters,
        k=result_limit,
        route_inventory=inventory,
    )
    if intent in {"cheapest", "fastest"} and documents:
        def duration_minutes(document: Document) -> int:
            match = re.search(r"Duration: (\d+)h (\d+)m", document.page_content)
            return int(match.group(1)) * 60 + int(match.group(2)) if match else 10**9

        documents.sort(
            key=lambda document: (
                int(document.metadata["price_inr"]) if intent == "cheapest" else duration_minutes(document)
            )
        )
        documents = documents[:4] if intent == "cheapest" else documents[:1]
    if intent == "operators" and documents:
        documents = [
            Document(
                page_content=document.page_content.split(". Route:", 1)[0],
                metadata=document.metadata,
            )
            for document in documents
        ]
    if not documents and filters and not route:
        documents = _offline_search(user_query, {}, k=4)
    answer = _offline_response(documents, user_query)
    if inventory_warning:
        answer = f"⚠️ {inventory_warning}\n\n{answer}"
    return answer, len(documents)
