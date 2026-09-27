# Augur DRHP IPO Intelligence API

A high-performance IPO exploration and Augur-compatible data layer. It provides a FastAPI backend for automatic directory scanning, real-time indexing, search, filtering, and deep financial analytics for Indian IPOs (DRHP).

## Features

- **Automated Directory Scanning**: Automatically parses and indexes IPO JSON files in real-time.
- **Deep Financial Analytics**: Calculates metrics such as percentage of fresh issue, profit margins, and revenue growth.
- **Augur Compatibility**: Exposes endpoints and data schemas designed to integrate easily with the Augur ecosystem and its PostgreSQL database.
- **Advanced Search & Filtering**: Includes search by name, industry, issue size bounds, profitability, and more.
- **Comparison Engine**: Built-in endpoint to compare up to 5 IPOs side-by-side.

## Setup & Installation

### Prerequisites
- Python 3.8+
- Optional: Virtual Environment

### Installation

1. Clone or download this repository.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

You can easily start the application using the provided shell script:

```bash
./start.sh
```

Alternatively, you can run the server manually:

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

The server will start at: `http://localhost:8000`

## API Endpoints

- `GET /` - Serves the index HTML or API status.
- `GET /health` - Health status and metadata.
- `GET /docs` - Swagger UI for complete interactive API documentation.
- `POST /api/v1/sync` - Re-scans the directory to discover added or updated JSON files.
- `GET /api/v1/stats` - Summary metrics across all indexed DRHP prospectuses.
- `GET /api/v1/ipos` - Search, filter, and paginate through IPO prospectuses.
- `GET /api/v1/ipos/{ipo_id}` - Retrieve complete DRHP detail, financial statements, and mapping for a single IPO.
- `GET /api/v1/compare?ids=...` - Compare up to 5 IPOs side-by-side.
- `GET /api/v1/augur/export` - Export all current IPOs formatted for Augur's PostgreSQL `ipos` table.
- `POST /api/v1/ipos/create` - Programmatically create a new IPO JSON file dynamically.
- `POST /api/v1/ipos/upload-file` - Upload a `.json` file directly into the server directory.

## Database Ingestion & Cloud Deployment

Instead of relying solely on flat JSON files, you can persist and query records using [ingest.py](file:///Users/priyanshu/Downloads/output/ingest.py):

### 1. Local SQLite (Zero Setup)
```bash
python ingest.py
```
This generates an indexed SQLite database `ipos.db` ready for fast local queries.

### 2. Cloud PostgreSQL (Supabase / Neon)
Pass your PostgreSQL connection string:
```bash
export DATABASE_URL="postgresql://user:password@ep-host.region.neon.tech/neondb?sslmode=require"
python ingest.py
```

## Project Structure

- `server.py`: The core FastAPI application containing routing, logic, and parsing functions.
- `ingest.py`: Database ingestion script supporting SQLite and PostgreSQL (Supabase/Neon).
- `data/drhp/`: Clean directory storing normalized DRHP JSON prospectuses (`{company-slug}.json`).
- `start.sh`: A shell script to simplify application startup.
- `requirements.txt`: Python dependencies required to run the server.
- `static/`: Frontend dashboard UI served by the application.
