# Intercity Bus Fleet Intelligence & AI Planner

An end-to-end bus travel intelligence application that lets users search
routes across India, compare fares and journey times, and ask a Gemini-powered
assistant for grounded recommendations.

The application uses a **cloud-safe route inventory generator**. It does not
depend on Playwright, Chromium, or browser automation at runtime. This avoids
deployment failures on Streamlit Cloud while still providing route-specific
fares, operators, timings, durations, and seat categories for any searched
Indian city pair. Gemini is an optional enhancement for semantic retrieval and
natural-language responses.

## Features

- Search any source and destination in the Streamlit interface.
- Route-aware fallback inventory rather than one repeated hardcoded route.
- Fare, duration, departure-time, and seat-type normalization.
- Dashboard KPIs:
  - lowest available fare,
  - average fare,
  - shortest journey,
  - indexed bus count.
- ChromaDB vector index with metadata filters for:
  - maximum fare,
  - minimum fare,
  - seat type,
  - route.
- Gemini grounded answers based only on retrieved inventory context.
- Deterministic local ranking when a Gemini key is unavailable.
- Responsive RedBus-inspired UI styling.
- Safe `.env` handling; secrets are excluded from Git.

## Architecture

```text
User enters From + To
          |
          v
Route-aware inventory generation
          |
          v
Raw CSV (data/bus_raw.csv)
          |
          v
Pandas validation and feature engineering
          |
          v
Clean CSV (data/bus_cleaned.csv)
          |
          v
Gemini embeddings + ChromaDB metadata index
          |
          v
Natural-language constraints
          |
          v
Hybrid retrieval: exact filters + semantic similarity
          |
          v
Gemini grounded answer
          |
          v
Streamlit dashboard and conversational assistant
```

## Repository structure

```text
bus-travel-intelligence/
├── app/
│   ├── __init__.py
│   └── frontend.py
├── data/
│   ├── bus_raw.csv              # generated ingestion output
│   ├── bus_cleaned.csv         # generated ETL output
│   │   └── chroma_db/              # optional local vector index, ignored by Git
├── src/
│   ├── __init__.py
│   ├── scraper.py
│   ├── prepare_data.py
│   ├── vector_store.py
│   └── genai_agent.py
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Technology stack

| Technology | Purpose |
| --- | --- |
| Python | Application and data-pipeline language |
| Streamlit | Interactive dashboard and chat interface |
| pandas | CSV processing and feature engineering |
| LangChain Core | Prompt and runnable composition |
| LangChain Google GenAI | Gemini chat and embedding integrations |
| ChromaDB | Persistent vector store and metadata filtering |
| Gemini | Text embeddings and grounded natural-language responses |
| python-dotenv | Local environment configuration |

## Requirements

- Windows, macOS, or Linux
- Python 3.10 or later
- Internet access for package installation
- A Gemini API key for optional embeddings and LLM responses

Python 3.14 may require newer dependency releases, which is why the project
uses compatible minimum versions in `requirements.txt` instead of outdated
exact pins.

## Installation on Windows

Open PowerShell in the project directory:

```powershell
cd C:\Users\<your-user>\Desktop\bus-travel-intelligence
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and add a newly generated key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Never commit `.env` or paste a live key into source code, screenshots, GitHub,
or chat. If a key is exposed, revoke it and generate a replacement.

## Run the data pipeline

The application pipeline is intentionally sequential:

```powershell
python src\scraper.py
python src\prepare_data.py
```

### 1. `src/scraper.py`

`scrape_bus_data(source, destination)`:

1. Creates the `data` directory.
2. Generates route-aware inventory using the selected cities.
3. Derives operator, route, departure, duration, seat type, and price.
4. Writes `data/bus_raw.csv`.

The generator estimates road distance using known Indian city coordinates. It
derives realistic durations and fares from distance, and uses route-seeded
operator pools and departure schedules. Therefore Chennai → Vellore, Chennai
→ Kochi, and Mumbai → Delhi do not reuse the same inventory. Chennai →
Bangalore retains a curated demo dataset suitable for evaluation.

Browser automation is intentionally not part of this application. A future
live provider integration should run as a separate ingestion service, not
inside the Streamlit request lifecycle.

### 2. `src/prepare_data.py`

`run_pipeline()` validates the raw schema and creates:

- `price_inr`: numeric fare extracted from currency text.
- `departure_hour`: 24-hour departure value.
- `duration_mins`: total journey duration.
- normalized text fields.
- duplicate-free rows.

The result is stored in `data/bus_cleaned.csv`.

### 3. `src/vector_store.py`

The module converts each cleaned row into a LangChain `Document` containing:

- natural-language page content for semantic similarity,
- metadata for deterministic filtering.

The current embedding model is `models/gemini-embedding-001`. Chroma is
optional: the application attempts semantic retrieval only when available and
falls back to deterministic pandas filtering if embeddings, quota, or model
availability fails. The optional local collection is stored under
`data/chroma_db/`.

## Hybrid search behavior

The assistant extracts constraints from questions such as:

```text
Find an AC sleeper under 800 rupees
```

This becomes:

```python
{
    "max_price": 800,
    "seat_type": "AC Sleeper"
}
```

Chroma applies metadata constraints first, then ranks the remaining documents
semantically against the user question. Route filtering is added by the UI so
answers stay within the selected source and destination.

Supported examples:

```text
Find the cheapest bus under 700 rupees
Show an AC sleeper under ₹1200
Find a non-AC sleeper for this route
Which bus is the fastest?
```

## Start the application

```powershell
python -m streamlit run app\frontend.py
```

Open:

```text
http://localhost:8501
```

### User flow

1. Enter a city in **From**.
2. Enter a city in **To**.
3. Click **Search buses**.
4. The route-specific ingestion and ETL pipeline runs.
5. The route inventory refreshes; optional Gemini retrieval is used when available.
6. The analytics tab displays route metrics and inventory.
7. The assistant tab accepts budget and comfort requirements.

Examples:

```text
Chennai → Bangalore
Chennai → Vellore
Chennai → Kochi
Mumbai → Pune
Delhi → Jaipur
Bangalore → Hyderabad
```

## Verification commands

Syntax validation:

```powershell
python -m compileall -q src app
```

Constraint parser check:

```powershell
python -c "from src.genai_agent import extract_query_constraints; print(extract_query_constraints('AC sleeper under 800'))"
```

Gemini query check:

```powershell
python -c "from src.genai_agent import process_travel_query; print(process_travel_query('Find an AC sleeper under 800 rupees'))"
```

The query function returns:

```text
(response_text, retrieved_document_count)
```

## Design decisions

### Why use generated route inventory?

The project must be reliable on Streamlit Cloud, where browser binaries and
third-party scraping are not guaranteed. Route-aware generation keeps the
dashboard and query logic available without pretending that generated demo
records are live booking inventory.

### Why use both metadata and vectors?

Semantic similarity alone may return a bus over the requested budget.
Metadata filters enforce fare, seat, and route constraints exactly, while
embeddings rank the remaining candidates by intent such as affordability,
comfort, or convenience.

### Why regenerate the index after route search?

Each selected route produces a new CSV inventory snapshot. Route filtering is
applied to recommendations so results from a previous route do not leak into
the current answer.

## Troubleshooting

### `GEMINI_API_KEY is not configured`

The application still works with deterministic local filtering and ranking.
For Gemini responses, ensure `.env` is located in the project root and
contains a non-placeholder value. Restart Streamlit after changing `.env`.

### Gemini model not found

Use the current models configured in the source:

- `models/gemini-embedding-001`
- `gemini-3.6-flash`

Model availability can vary by account and region. Check Google AI Studio if
the API reports a model availability change.

### Gemini embeddings or chat returns an API error

This is non-fatal. The assistant falls back to local route, fare, seat-type,
and lexical ranking logic. Check the key, model availability, quota, and
Streamlit Secrets if Gemini responses are required.

## Deployment

For Streamlit Community Cloud:

1. Push this repository to GitHub.
2. Create a new Streamlit app.
3. Select the repository and `main` branch.
4. Set the entry point to `app/frontend.py`.
5. Add `GEMINI_API_KEY` under App Settings → Secrets (optional).
6. Deploy or reboot the app.

The deployed app does not require Playwright, Chromium, or any browser
installation. If Streamlit logs mention `playwright._impl`, the deployment is
running an outdated commit; confirm that the app uses the repository's `main`
branch and redeploy.

Do not put the API key in `README.md`, `requirements.txt`, source files, or
GitHub Actions logs.

## Limitations and future improvements

- Add a separate provider ingestion worker if live listings are required.
- Add a provider abstraction for multiple bus aggregators.
- Add date-of-travel and seat-availability fields.
- Add caching to avoid re-scraping unchanged routes.
- Add route autocomplete backed by a city database.
- Add unit and integration tests in CI.
- Add booking/deep-link support after confirming provider terms.

## License

This project is provided for educational and portfolio use. Add an explicit
license before redistributing it commercially.
