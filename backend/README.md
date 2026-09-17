# Morning Pulse AI — M1: Data Collection & Processing

**Research Title:** Evidence-Grounded Temporal Market Intelligence Using Retrieval-Augmented Generation

---

## Quick Start (TL;DR)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # edit DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload  # API at http://localhost:8000
python scripts/run_m1_pipeline.py --mock   # test pipeline
pytest tests/ -v               # run tests
```

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                        ← FastAPI entry point
│   ├── api/routes/
│   │   ├── health.py                  ← GET /health
│   │   ├── documents.py               ← GET /api/v1/documents
│   │   ├── sources.py                 ← GET /api/v1/sources
│   │   ├── companies.py               ← GET /api/v1/companies
│   │   ├── clusters.py                ← GET /api/v1/clusters
│   │   └── ingestion.py               ← POST /api/v1/ingestion/*
│   ├── ingestion/
│   │   ├── base.py                    ← Abstract BaseCollector
│   │   ├── gdelt.py                   ← GDELT DOC 2.0 API
│   │   ├── sec_edgar.py               ← SEC EDGAR submissions API
│   │   ├── official_company.py        ← RSS + HTML scrape
│   │   ├── research.py                ← Research RSS/API feeds
│   │   └── mock_data.py               ← Sample data for dev/test
│   ├── processing/
│   │   ├── normalization.py           ← HTML strip, whitespace, UTC, language
│   │   ├── validation.py              ← Pydantic validation
│   │   ├── hashing.py                 ← SHA-256 content hashing
│   │   ├── deduplication.py           ← 4-level dedup
│   │   └── clustering.py              ← Story cluster assignment
│   ├── database/
│   │   ├── database.py                ← SQLAlchemy engine + session
│   │   ├── models.py                  ← ORM models (5 tables)
│   │   └── repositories.py            ← Data-access layer
│   ├── schemas/
│   │   └── document.py                ← Pydantic schemas
│   ├── services/
│   │   └── pipeline.py                ← M1 orchestrator
│   └── config/
│       ├── settings.py                ← Pydantic settings (env vars)
│       ├── companies.json             ← Company registry
│       └── research_sources.json      ← Research source registry
├── tests/                             ← Full test suite (no live APIs)
├── alembic/                           ← DB migrations
├── scripts/
│   └── run_m1_pipeline.py             ← CLI entry point
├── requirements.txt
├── alembic.ini
└── .env.example
```

---

## 1. Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 14+ |
| pip | latest |

---

## 2. PostgreSQL Setup

```sql
-- Run in psql as superuser
CREATE USER morning_pulse WITH PASSWORD 'your_password';
CREATE DATABASE morning_pulse OWNER morning_pulse;
GRANT ALL PRIVILEGES ON DATABASE morning_pulse TO morning_pulse;
```

---

## 3. Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required
DATABASE_URL=postgresql://morning_pulse:your_password@localhost:5432/morning_pulse

# SEC EDGAR (required for live SEC collection)
# Format: "AppName/Version email@address.com"
SEC_USER_AGENT=MorningPulseAI/1.0 yourname@university.edu
SEC_REQUEST_DELAY=0.5

# Pipeline
GDELT_MAX_RESULTS=100
DEFAULT_LOOKBACK_DAYS=7
USE_MOCK_DATA=false
ENABLE_SEMANTIC_DEDUP=false

LOG_LEVEL=INFO
```

> **Never commit `.env` to version control.**

---

## 4. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

> To skip the large `sentence-transformers` model (needed only for semantic dedup):
> ```bash
> pip install -r requirements.txt --ignore-requires-python
> # or comment out sentence-transformers in requirements.txt if not needed
> ```

---

## 5. Run Database Migrations

```bash
cd backend
alembic upgrade head
```

To check migration status:
```bash
alembic current
alembic history
```

To roll back:
```bash
alembic downgrade -1
```

---

## 6. Start the FastAPI Server

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Description |
|---|---|
| http://localhost:8000/health | Health check |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/redoc | ReDoc |

---

## 7. Run the M1 Pipeline

### Mock mode (no external API calls — for development/demo)

```bash
cd backend
python scripts/run_m1_pipeline.py --mock
```

### Live mode (calls GDELT, SEC, company sites, research feeds)

```bash
python scripts/run_m1_pipeline.py
```

### Options

```
--mock              Use sample data instead of external APIs
--sources           Comma-separated: gdelt, sec, official, research
--lookback 14       Days to look back (default: 7)
--semantic          Enable Level-4 semantic deduplication
--log-level DEBUG   Set logging verbosity
```

### Examples

```bash
# Run only GDELT and SEC in mock mode
python scripts/run_m1_pipeline.py --mock --sources gdelt,sec

# Live run with 14-day lookback and verbose logging
python scripts/run_m1_pipeline.py --lookback 14 --log-level DEBUG
```

---

## 8. Expected Pipeline Output

```
==================================================
MORNING PULSE AI - M1 PIPELINE
==================================================

[GDELT]
  Fetched:    8
  Valid:      7
  Duplicates: 1
  Stored:     7
  Errors:     0

[SEC EDGAR]
  Fetched:    3
  Valid:      3
  Duplicates: 0
  Stored:     3
  Errors:     0

[Official Company]
  Fetched:    3
  Valid:      3
  Duplicates: 0
  Stored:     3
  Errors:     0

[Research/Industry]
  Fetched:    4
  Valid:      4
  Duplicates: 0
  Stored:     4
  Errors:     0

--------------------------------------------------
TOTAL
--------------------------------------------------
  Collected:        18
  Valid:            17
  Exact duplicates: 1
  Story clusters:   1
  Stored documents: 17

M1 PIPELINE COMPLETED SUCCESSFULLY (3.2s)
==================================================
```

---

## 9. API Endpoints

### Health

```bash
curl http://localhost:8000/health
```

### List documents

```bash
# All documents (default limit 50)
curl "http://localhost:8000/api/v1/documents"

# Filter by source type
curl "http://localhost:8000/api/v1/documents?source_type=gdelt"

# Filter by date range
curl "http://localhost:8000/api/v1/documents?start_date=2024-01-01&end_date=2024-01-31&limit=20"
```

### Get single document

```bash
curl "http://localhost:8000/api/v1/documents/{document_uuid}"
```

### Sources and companies

```bash
curl http://localhost:8000/api/v1/sources
curl http://localhost:8000/api/v1/companies
curl http://localhost:8000/api/v1/clusters
```

### Trigger ingestion

```bash
# Full pipeline (live)
curl -X POST http://localhost:8000/api/v1/ingestion/run \
     -H "Content-Type: application/json" \
     -d '{}'

# Mock run
curl -X POST http://localhost:8000/api/v1/ingestion/run \
     -H "Content-Type: application/json" \
     -d '{"use_mock": true}'

# GDELT only
curl -X POST http://localhost:8000/api/v1/ingestion/gdelt \
     -H "Content-Type: application/json" \
     -d '{"use_mock": true}'

# DB stats
curl http://localhost:8000/api/v1/ingestion/stats
```

---

## 10. Running Tests

```bash
cd backend
pytest tests/ -v
```

Tests use **in-memory SQLite** — no PostgreSQL needed to run the test suite.
All external HTTP calls are mocked.

```bash
# Run specific test file
pytest tests/test_normalization.py -v
pytest tests/test_pipeline.py -v

# With coverage (install pytest-cov first)
pytest tests/ --cov=app --cov-report=term-missing
```

---

## 11. Adding New Companies

Edit [`app/config/companies.json`](app/config/companies.json):

```json
{
  "ticker": "GOOGL",
  "company_name": "Alphabet Inc.",
  "cik": "0001652044",
  "website": "https://www.google.com",
  "investor_relations_url": "https://abc.xyz/investor",
  "news_url": "https://blog.google/",
  "rss_feed_url": "https://blog.google/rss/",
  "active": true
}
```

No code changes required.

---

## 12. Adding New Research Sources

Edit [`app/config/research_sources.json`](app/config/research_sources.json):

```json
{
  "source_name": "IEEE Spectrum",
  "source_type": "research_industry",
  "base_url": "https://spectrum.ieee.org",
  "feed_url": "https://spectrum.ieee.org/feeds/feed.rss",
  "api_url": null,
  "category": "engineering",
  "reliability_level": "very_high",
  "active": true
}
```

---

## 13. Deduplication Levels

| Level | Method | Action |
|---|---|---|
| L1 | URL match | Exact duplicate → skip |
| L2 | SHA-256 content hash | Exact duplicate → skip |
| L3 | Jaccard title similarity ≥ 0.85 | Exact duplicate → skip |
| L3 | Jaccard title similarity 0.60–0.85 | Related → story cluster |
| L4 | Sentence Transformers cosine (optional) | Related/exact |

---

## 14. Database Schema

```
sources          ← reliability-rated source registry
companies        ← company registry (from companies.json)
documents        ← normalized market intelligence documents
story_clusters   ← groups of same-event documents
document_clusters← many-to-many link with similarity score
```

---

## 15. External API Limitations

| Source | Auth Required | Notes |
|---|---|---|
| GDELT DOC API | None | Public; article text may be blocked by publishers |
| SEC EDGAR | None | Rate-limit aware; User-Agent required |
| Company RSS/newsrooms | None | Some sites block scrapers; RSS preferred |
| Research RSS feeds | None | Fully public |

---

## 16. Future Milestones (Not Yet Implemented)

| Milestone | Description |
|---|---|
| M2 | Hybrid retrieval (BM25 + dense vectors) |
| M3 | RAG query engine |
| M4 | Evidence verification |
| M5 | Temporal reasoning |
| M6 | Frontend dashboard |

The M1 database schema and document format are designed to feed directly into M2 without changes.
