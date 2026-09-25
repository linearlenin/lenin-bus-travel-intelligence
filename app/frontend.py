"""Streamlit dashboard for inventory analytics and travel assistance."""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.genai_agent import extract_route, process_travel_query
from src.prepare_data import run_pipeline
from src.scraper import scrape_bus_data


DATA_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "bus_cleaned.csv"))

st.set_page_config(page_title="Intercity Bus Intelligence", page_icon="🚌", layout="wide")
st.caption("Build: route-aware-v4")
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
    .section-header {
        background: linear-gradient(135deg, #991b1b, #ea580c);
        border-radius: 15px;
        color: white;
        margin: 1.3rem 0 0.85rem;
        padding: 0.85rem 1rem;
    }
    .section-header h3 {
        color: white;
        font-size: 1.05rem;
        letter-spacing: 0.06em;
        margin: 0;
        text-transform: uppercase;
    }
    .route-pill {
        background: #fff7ed;
        border: 1px solid #fdba74;
        border-radius: 999px;
        color: #9a3412;
        display: inline-block;
        font-size: 0.82rem;
        font-weight: 800;
        margin-top: 0.45rem;
        padding: 0.3rem 0.75rem;
    }
    div[data-testid="stDataFrame"] {
        border: 2px solid #fed7aa;
        border-radius: 14px;
        overflow: hidden;
    }
    .assistant-card {
        background: #ffffff;
        border: 2px solid #ea580c;
        border-radius: 16px;
        margin-bottom: 1rem;
        padding: 1rem 1.1rem;
    }
    .assistant-card h3 {
        color: #991b1b;
        font-size: 1.1rem;
        font-weight: 900;
        letter-spacing: 0.05em;
        margin: 0;
    }
    .assistant-card p {
        color: #431407;
        font-size: 0.95rem;
        font-weight: 600;
        margin: 0.45rem 0 0;
    }
    .chart-card {
        background: rgba(255, 255, 255, 0.88);
        border: 1px solid #fed7aa;
        border-radius: 16px;
        box-shadow: 0 6px 18px rgba(127, 29, 29, 0.08);
        padding: 1rem;
    }
    .price-row {
        align-items: center;
        display: flex;
        gap: 0.65rem;
        margin: 0.65rem 0;
    }
    .price-name {
        color: #7f1d1d;
        flex: 0 0 34%;
        font-size: 0.78rem;
        font-weight: 800;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .price-track {
        background: #ffedd5;
        border-radius: 999px;
        flex: 1;
        height: 1.15rem;
        overflow: hidden;
    }
    .price-bar {
        background: linear-gradient(90deg, #b91c1c, #f97316);
        border-radius: 999px;
        height: 100%;
    }
    .price-value {
        color: #9a3412;
        flex: 0 0 4.1rem;
        font-size: 0.82rem;
        font-weight: 900;
        text-align: right;
    }
    .answer-card {
        background: #ffffff;
        border: 2px solid #f97316;
        border-radius: 14px;
        box-shadow: 0 5px 16px rgba(127, 29, 29, 0.08);
        color: #26120b;
        font-size: 1rem;
        font-weight: 600;
        line-height: 1.6;
        margin-top: 0.5rem;
        padding: 0.8rem 1rem;
    }
    .answer-card p, .answer-card li, .answer-card strong {
        color: #26120b !important;
    }
    div[data-testid="stChatMessage"] {
        color: #26120b;
    }
    div[data-testid="stChatMessage"] p,
    div[data-testid="stChatMessage"] li {
        color: #26120b !important;
        font-size: 0.98rem;
        line-height: 1.55;
    }
    div[data-testid="stChatMessage"] code {
        background: #ffedd5;
        color: #7c2d12;
    }
    div[data-testid="stTextInput"] label,
    div[data-testid="stTextInput"] label p {
        color: #111111 !important;
        font-size: 1rem !important;
        font-weight: 900 !important;
    }
    div[data-testid="stTextInput"] input {
        background: #ffffff !important;
        border: 2px solid #991b1b !important;
        border-radius: 12px !important;
        color: #111111 !important;
        font-size: 1rem !important;
        font-weight: 800 !important;
        min-height: 2.8rem;
    }
    div[data-testid="stTextInput"] input::placeholder {
        color: #6b7280 !important;
        opacity: 1 !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 0.35rem;
    }
    div[data-testid="stTabs"] button[role="tab"] {
        background: linear-gradient(135deg, #fecaca, #fed7aa) !important;
        border: 2px solid #991b1b !important;
        border-radius: 12px !important;
        color: #111111 !important;
        font-size: 0.95rem !important;
        font-weight: 900 !important;
        margin-right: 0.35rem;
        padding: 0.65rem 1rem;
        opacity: 1 !important;
    }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #fecaca, #fed7aa) !important;
        border: 2px solid #991b1b !important;
        color: #111111 !important;
        box-shadow: none !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:hover {
        background: linear-gradient(135deg, #fecaca, #fed7aa) !important;
        color: #111111 !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background: #7f1d1d;
        height: 2px;
    }
    div[data-testid="stMetric"] {
        display: none;
    }
    .kpi-card {
        min-height: 142px;
        border-radius: 16px;
        padding: 1rem 1.05rem;
        color: #ffffff;
        box-shadow: 0 8px 22px rgba(127, 29, 29, 0.16);
        overflow-wrap: anywhere;
    }
    .kpi-card.fare { background: linear-gradient(145deg, #b91c1c, #dc2626); }
    .kpi-card.average { background: linear-gradient(145deg, #c2410c, #ea580c); }
    .kpi-card.time { background: linear-gradient(145deg, #9f1239, #e11d48); }
    .kpi-card.count { background: linear-gradient(145deg, #7c2d12, #c2410c); }
    .kpi-label {
        color: #ffedd5;
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        line-height: 1.25;
        text-transform: uppercase;
    }
    .kpi-value {
        font-size: clamp(1.35rem, 3vw, 1.85rem);
        font-weight: 900;
        line-height: 1.15;
        margin-top: 0.55rem;
    }
    .kpi-detail {
        color: #fff7ed;
        font-size: 0.84rem;
        font-weight: 600;
        line-height: 1.25;
        margin-top: 0.35rem;
    }
    @media (max-width: 640px) {
        .block-container {
            padding: 1.25rem 0.8rem 2rem;
        }
        .kpi-card {
            min-height: 118px;
            padding: 0.9rem;
        }
        .kpi-value {
            font-size: 1.55rem;
        }
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

st.markdown('<div class="route-card"><h3>SEARCH BUSES ACROSS INDIA</h3><span class="route-pill">DEFAULT DEMO: CHENNAI → BANGALORE</span></div>', unsafe_allow_html=True)
route_columns = st.columns([1, 0.12, 1], gap="small")
with route_columns[0]:
    if "route_source" not in st.session_state:
        st.session_state.route_source = "Chennai"
    source = st.text_input("From", placeholder="e.g. Delhi", key="route_source")
with route_columns[1]:
    st.markdown("<div style='text-align:center;padding-top:2rem;font-size:1.4rem'>→</div>", unsafe_allow_html=True)
with route_columns[2]:
    if "route_destination" not in st.session_state:
        st.session_state.route_destination = "Bangalore"
    destination = st.text_input("To", placeholder="e.g. Mumbai", key="route_destination")

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
        cheapest = frame.loc[frame["price_inr"].idxmin()]
        fastest = int(frame["duration_mins"].min())
        kpis = st.columns(4, gap="small")
        cards = [
            ("fare", "💰 LOWEST FARE", f"₹{int(frame['price_inr'].min())}", str(cheapest["operator"])),
            ("average", "📊 AVERAGE FARE", f"₹{int(frame['price_inr'].mean())}", "Across this route"),
            ("time", "⏱ SHORTEST JOURNEY", f"{fastest // 60}h {fastest % 60}m", "Fastest available bus"),
            ("count", "🚌 INDEXED BUSES", str(len(frame)), "Available inventory"),
        ]
        for column, (style, label, value, detail) in zip(kpis, cards):
            with column:
                st.markdown(
                    f'<div class="kpi-card {style}">'
                    f'<div class="kpi-label">{label}</div>'
                    f'<div class="kpi-value">{value}</div>'
                    f'<div class="kpi-detail">{detail}</div>'
                    "</div>",
                    unsafe_allow_html=True,
                )
        st.markdown(
            f'<div class="section-header"><h3>🚌 CURRENT FLEET INVENTORY</h3>'
            f'<span class="route-pill">{active_route}</span></div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            frame[["operator", "route", "departure", "seat_type", "price_inr", "duration"]],
            use_container_width=True,
            hide_index=True,
        )
        st.markdown(
            '<div class="section-header"><h3>💰 PRICE BY FLEET OPERATOR</h3></div>',
            unsafe_allow_html=True,
        )
        max_price = max(int(frame["price_inr"].max()), 1)
        bars = []
        for row in frame.sort_values("price_inr", ascending=False).itertuples():
            width = max(8, int(row.price_inr / max_price * 100))
            bars.append(
                f'<div class="price-row"><div class="price-name">{row.operator}</div>'
                f'<div class="price-track"><div class="price-bar" style="width:{width}%"></div></div>'
                f'<div class="price-value">₹{int(row.price_inr)}</div></div>'
            )
        st.markdown(f'<div class="chart-card">{"".join(bars)}</div>', unsafe_allow_html=True)

with chat_tab:
    st.markdown(
        '<div class="assistant-card"><h3>🤖 FLEET AI DISPATCHER</h3>'
        '<p>Ask for the cheapest, fastest, or most comfortable bus for any route.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
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
        query_route = extract_route(question)
        if query_route:
            if query_route.casefold() != active_route.casefold():
                query_source, query_destination = query_route.split(" to ", maxsplit=1)
                with st.spinner(f"Switching inventory to {query_route}..."):
                    scrape_bus_data(query_source, query_destination)
                    run_pipeline()
                st.session_state.route = query_route
                active_route = query_route
                st.session_state.chat_history = []
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching the inventory..."):
                answer, count = process_travel_query(question, route=active_route)
            st.markdown('<div class="answer-card">', unsafe_allow_html=True)
            st.markdown(answer)
            st.markdown("</div>", unsafe_allow_html=True)
            st.caption(f"Matched {count} inventory records.")
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
