"""Streamlit dashboard for inventory analytics and travel assistance."""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.genai_agent import process_travel_query
from src.prepare_data import run_pipeline
from src.scraper import scrape_bus_data
from src.vector_store import build_vector_store


DATA_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "bus_cleaned.csv"))

st.set_page_config(page_title="Intercity Bus Intelligence", page_icon="🚌", layout="wide")
st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at 8% 0%, rgba(255, 237, 213, 0.9), transparent 28rem),
            linear-gradient(145deg, #fff7ed 0%, #fff1f2 48%, #fee2e2 100%);
    }
    .block-container {
        max-width: 1180px;
        padding-top: 2.5rem;
        padding-bottom: 3rem;
    }
    .hero-title {
        background: linear-gradient(90deg, #b91c1c, #ea580c);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        font-size: clamp(1.6rem, 4vw, 2.65rem);
        font-weight: 900;
        letter-spacing: 0.06em;
        line-height: 1.2;
        margin-bottom: 0.35rem;
        text-transform: uppercase;
    }
    .hero-caption {
        color: #7f1d1d;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    div[data-testid="stTabs"] button[role="tab"] {
        color: #991b1b;
        font-weight: 700;
    }
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid #fecaca;
        border-radius: 14px;
        padding: 0.8rem;
        box-shadow: 0 5px 18px rgba(127, 29, 29, 0.07);
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="hero-title">🚌 INTERCITY BUS FLEET INTELLIGENCE &amp; AI PLANNER</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="hero-caption">Search buses across India and find the best fare, timing, and seat type for your journey.</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    .route-card {
        background: linear-gradient(135deg, #fff7ed, #ffffff);
        border: 1px solid #fed7aa;
        border-radius: 18px;
        padding: 1.4rem 1.5rem 1rem;
        margin: 1.5rem auto 1.75rem;
        max-width: 980px;
        text-align: center;
    }
    .route-card h3 {
        color: #9a3412;
        font-size: clamp(1rem, 2vw, 1.35rem);
        font-weight: 800;
        letter-spacing: 0.14em;
        line-height: 1.4;
        margin: 0;
        text-transform: uppercase;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="route-card"><h3>SEARCH BUSES ACROSS INDIA</h3></div>', unsafe_allow_html=True)
route_columns = st.columns([1, 0.12, 1], gap="small")
with route_columns[0]:
    source = st.text_input("From", value="Chennai", placeholder="e.g. Delhi", key="route_source")
with route_columns[1]:
    st.markdown("<div style='text-align:center;padding-top:2rem;font-size:1.4rem'>→</div>", unsafe_allow_html=True)
with route_columns[2]:
    destination = st.text_input("To", value="Bangalore", placeholder="e.g. Mumbai", key="route_destination")

search_column = st.columns([1, 2, 1])[1]
with search_column:
    refresh_route = st.button("🔎 Search buses", type="primary", use_container_width=True)

if refresh_route:
    source = source.strip().title()
    destination = destination.strip().title()
    if not source or not destination:
        st.error("Please enter both From and To locations.")
    elif source.casefold() == destination.casefold():
        st.error("From and To locations must be different.")
    else:
        route = f"{source} to {destination}"
        with st.spinner(f"Finding buses from {source} to {destination}..."):
            scrape_bus_data(source, destination)
            run_pipeline()
            if os.getenv("GEMINI_API_KEY"):
                build_vector_store()
        st.session_state.route = route
        st.session_state.chat_history = []
        st.success(f"Route loaded: {route}")

active_route = st.session_state.get("route", "Chennai to Bangalore")

analytics_tab, chat_tab = st.tabs(["📊 Inventory & Route Analytics", "🤖 Conversational Assistant"])

with analytics_tab:
    if not os.path.exists(DATA_FILE):
        st.warning("Inventory is not available. Run `python src/scraper.py` followed by `python src/prepare_data.py`.")
    else:
        frame = pd.read_csv(DATA_FILE)
        metrics = st.columns(4)
        cheapest = frame.loc[frame["price_inr"].idxmin()]
        fastest = int(frame["duration_mins"].min())
        metrics[0].metric("Lowest Fare", f"₹{int(frame['price_inr'].min())}", str(cheapest["operator"]))
        metrics[1].metric("Average Fare", f"₹{int(frame['price_inr'].mean())}")
        metrics[2].metric("Shortest Journey", f"{fastest // 60}h {fastest % 60}m")
        metrics[3].metric("Indexed Buses", len(frame))
        st.subheader(f"Current Fleet Inventory: {active_route}")
        st.dataframe(
            frame[["operator", "route", "departure", "seat_type", "price_inr", "duration"]],
            use_container_width=True,
            hide_index=True,
        )
        st.subheader("Price by Fleet Operator")
        st.bar_chart(frame.set_index("operator")["price_inr"])

with chat_tab:
    st.subheader("Fleet AI Dispatcher")
    st.caption(f"Ask for the best bus on {active_route}, with budget, timing, or comfort preferences.")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "Welcome! I can help compare bus timings, fares, and seating choices.",
            }
        ]
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if question := st.chat_input("Enter your travel requirements..."):
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching the inventory..."):
                answer, count = process_travel_query(question, route=active_route)
            st.markdown(answer)
            st.caption(f"Matched {count} inventory records.")
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
