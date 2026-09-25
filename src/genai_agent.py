"""Constraint extraction and Gemini response generation with an offline fallback."""

import os
import re
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai._common import GoogleGenerativeAIError

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
    match = re.search(
        r"\bfrom\s+([a-z][a-z .-]*?)\s+to\s+([a-z][a-z .-]*?)(?=\s+(?:under|below|with|for|at|by|normal|ordinary|regular)\b|$)",
        query,
        re.IGNORECASE,
    )
    if match:
        return f"{match.group(1).strip().title()} to {match.group(2).strip().title()}"

    match = re.search(
        r"\b(?:(?:cheap|best|affordable|normal|ordinary|regular)\s+)?([a-z]+(?:\s+[a-z]+)?)\s+bus(?:es)?\s+from\s+([a-z][a-z .-]*?)(?=\s+(?:under|below|with|for|at|by|normal|ordinary|regular)\b|$)",
        query,
        re.IGNORECASE,
    )
    if match:
        destination = match.group(1).strip().title()
        source = match.group(2).strip().title()
        return f"{source} to {destination}"

    match = re.search(
        r"\b(?:bus(?:es)?\s+)?([a-z]+(?:\s+[a-z]+)?)\s+to\s+([a-z]+(?:\s+[a-z]+)?)(?=\s+(?:under|below|with|for|at|by|normal|ordinary|regular)\b|$)",
        query,
        re.IGNORECASE,
    )
    if match:
        return f"{match.group(1).strip().title()} to {match.group(2).strip().title()}"
    return None


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
    elif re.search(r"\b(normal|ordinary|regular|government)\s+bus", query, re.IGNORECASE):
        filters["normal_bus"] = True
    return filters


def _offline_search(query: str, filters: Dict[str, Any], k: int = 4) -> List[Document]:
    import pandas as pd

    frame = pd.read_csv(CLEANED_PATH)
    if filters.get("max_price") is not None:
        frame = frame[frame["price_inr"] <= filters["max_price"]]
    if filters.get("min_price") is not None:
        frame = frame[frame["price_inr"] >= filters["min_price"]]
    if filters.get("seat_type"):
        frame = frame[frame["seat_type"].str.casefold() == filters["seat_type"].casefold()]
    if filters.get("normal_bus"):
        frame = frame[~frame["seat_type"].str.match(r"^AC\b", case=False, na=False)]
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
                f"Bus Operator: {row.operator}. Route: {row.route}. Departure Time: {row.departure}. "
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
    return "Here are the closest matches for your request:\n" + "\n".join(lines)


def process_travel_query(user_query: str, route: str | None = None) -> Tuple[str, int]:
    filters = extract_query_constraints(user_query)
    requested_route = extract_route(user_query)
    route = requested_route or route
    if route:
        filters["route"] = route
    # Recommendations are intentionally deterministic. This prevents an LLM
    # from inventing a route, fare, operator, or schedule not in the CSV.
    documents = _offline_search(user_query, filters)
    if not documents and filters and not route:
        documents = _offline_search(user_query, {}, k=4)
    return _offline_response(documents, user_query), len(documents)
