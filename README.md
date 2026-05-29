# Breathe ESG — Carbon Data Ingestion App

A full-stack app that pulls emission data from three sources (SAP, Utility, Travel), normalises it into one schema, and lets analysts review and approve each record before it goes to auditors.

## Quick Start (local)

### Backend
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
# API available at http://localhost:8000/api/
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# App available at http://localhost:5173/
```

### Load sample data
Upload the files from `backend/sample_data/` via the UI or:
```bash
curl -X POST http://localhost:8000/api/upload/ \
  -F "source=sap" \
  -F "file=@backend/sample_data/sap_export.csv"
```

## Architecture

```
frontend (React + Vite + Tailwind + TanStack Table)
     │  HTTP/JSON
     ▼
backend (Django + DRF)
     │
     ├── /api/upload/     ← file ingestion → parser → bulk insert
     ├── /api/records/    ← list, filter, approve, reject
     └── /api/stats/      ← dashboard summary
     │
     ▼
SQLite (dev) / PostgreSQL (prod)
EmissionRecord (unified table)
HistoricalEmissionRecord (audit log)
```

## The three parsers

| Source | File | Challenges handled |
|--------|------|--------------------|
| SAP | CSV | German column names, gallons→litres |
| Utility | CSV or PDF | Non-calendar billing periods, PDF regex extraction |
| Travel | CSV | IATA codes → haversine distance, economy/business EF |

## API endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/upload/` | Upload a file (source + file) |
| GET | `/api/records/` | List records (filter: source, status, scope, search) |
| PATCH | `/api/records/{id}/` | Edit a record |
| POST | `/api/records/{id}/approve/` | Approve a record |
| POST | `/api/records/{id}/reject/` | Reject a record |
| POST | `/api/records/bulk_approve/` | Approve multiple records |
| GET | `/api/stats/` | Dashboard summary stats |

## Docs
- [Data Model](docs/MODEL.md)
- [Architecture Decisions](docs/DECISIONS.md)
- [Tradeoffs](docs/TRADEOFFS.md)
- [Sources](docs/SOURCES.md)

## Deploy (Render)

1. Push to GitHub
2. Create a new Web Service on Render pointing to this repo
3. Build command: `pip install -r backend/requirements.txt && cd backend && python manage.py collectstatic --no-input && python manage.py migrate`
4. Start command: `cd backend && gunicorn core.wsgi:application`
5. Add a PostgreSQL database and set `DATABASE_URL` env var
6. For frontend: create a Static Site, build `cd frontend && npm install && npm run build`, publish `frontend/dist`
