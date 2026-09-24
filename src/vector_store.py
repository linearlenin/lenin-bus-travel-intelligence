"""Chroma-backed hybrid retrieval over cleaned bus inventory."""

import os
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv
from langchain_core.documents import Document

load_dotenv()

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
CLEANED_PATH = os.path.join(DATA_DIR, "bus_cleaned.csv")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
COLLECTION_NAME = "bus_inventory"


def get_embedding_model():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("GEMINI_API_KEY is not configured.")
    return GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)


def _documents_from_frame(frame: pd.DataFrame) -> List[Document]:
    documents = []
    for _, row in frame.iterrows():
        documents.append(
            Document(
                page_content=(
                    f"Bus Operator: {row['operator']}. Route: {row['route']}. "
                    f"Departure Time: {row['departure']}. Duration: {row['duration']} "
                    f"({row['duration_mins']} mins). Seating Category: {row['seat_type']}. "
                    f"Ticket Fare: INR {row['price_inr']}."
                ),
                metadata={
                    "operator": str(row["operator"]),
                    "price_inr": int(row["price_inr"]),
                    "departure_hour": int(row["departure_hour"]),
                    "seat_type": str(row["seat_type"]),
                    "route": str(row["route"]),
                },
            )
        )
    return documents


def build_vector_store():
    from langchain_chroma import Chroma

    if not os.path.exists(CLEANED_PATH):
        raise FileNotFoundError(f"Missing cleaned data file: {CLEANED_PATH}")
    frame = pd.read_csv(CLEANED_PATH)
    if frame.empty:
        raise ValueError("Cannot build a vector store from empty inventory.")
    os.makedirs(CHROMA_DIR, exist_ok=True)
    existing = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=get_embedding_model(),
        collection_name=COLLECTION_NAME,
    )
    existing.delete_collection()
    return Chroma.from_documents(
        documents=_documents_from_frame(frame),
        embedding=get_embedding_model(),
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME,
    )


def _chroma_filter(filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not filters:
        return None
    clauses = []
    if filters.get("max_price") is not None:
        clauses.append({"price_inr": {"$lte": int(filters["max_price"])}})
    if filters.get("min_price") is not None:
        clauses.append({"price_inr": {"$gte": int(filters["min_price"])}})
    if filters.get("seat_type"):
        clauses.append({"seat_type": {"$eq": str(filters["seat_type"])}})
    if filters.get("departure_hour") is not None:
        clauses.append({"departure_hour": {"$gte": int(filters["departure_hour"])}})
    if filters.get("route"):
        clauses.append({"route": {"$eq": str(filters["route"])}})
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses} if clauses else None


def hybrid_search(query: str, filters: Optional[Dict[str, Any]] = None, k: int = 4) -> List[Document]:
    from langchain_chroma import Chroma

    if not os.path.exists(CHROMA_DIR):
        build_vector_store()
    store = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=get_embedding_model(),
        collection_name=COLLECTION_NAME,
    )
    return store.similarity_search(query, k=k, filter=_chroma_filter(filters))


if __name__ == "__main__":
    store = build_vector_store()
    print(f"Vector database initialized with {store._collection.count()} records.")
