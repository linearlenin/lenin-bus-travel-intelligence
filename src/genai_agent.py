"""Constraint extraction and Gemini response generation with an offline fallback."""

import os
import re
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from src.vector_store import CLEANED_PATH, hybrid_search

load_dotenv()

PROMPT = """You are an expert Indian intercity bus travel assistant.
Use only the inventory context below. If it does not satisfy a constraint, say so
and offer the closest available alternatives. Be concise and use markdown bullets.

Inventory context:
{context}

User question: {question}
"""


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
        filters["seat_type"] = "Non-AC Sleeper"
    elif re.search(r"\bac[\s-]?sleeper\b|\bsleeper\b", query, re.IGNORECASE):
        filters["seat_type"] = "AC Sleeper"
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
    if route:
        filters["route"] = route
    use_gemini = bool(os.getenv("GEMINI_API_KEY")) and os.getenv("GEMINI_API_KEY") != "your_gemini_api_key_here"
    if use_gemini:
        documents = hybrid_search(user_query, filters=filters, k=4)
        if not documents and filters and not route:
            documents = hybrid_search(user_query, filters=None, k=4)
        context = "\n\n".join(document.page_content for document in documents) or "No matching inventory found."
        model = ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0.2)
        chain = PromptTemplate(template=PROMPT, input_variables=["context", "question"]) | model | StrOutputParser()
        return chain.invoke({"context": context, "question": user_query}), len(documents)

    documents = _offline_search(user_query, filters)
    if not documents and filters and not route:
        documents = _offline_search(user_query, {}, k=4)
    return _offline_response(documents, user_query), len(documents)
