# Architecture Decisions

## D1: SQLite for dev, PostgreSQL for production
Use SQLite locally; switch to PostgreSQL via DATABASE_URL env var on deploy. dj-database-url makes this a one-line config change. SQLite lets reviewers clone and run without a Postgres server.

## D2: pandas for CSV, pdfplumber for PDFs
pandas handles encoding issues (utf-8-sig BOM from SAP exports), auto-detects separators, and makes column mapping trivial. pdfplumber preserves text positioning better than PyPDF2, important for tabular utility bill data.

## D3: Haversine for flight distances
Calculate great-circle distance from IATA codes locally, no third-party API. No API key, no rate limits, no cost, works offline. Accuracy within ~1% of actual flight paths for emission purposes.

## D4: Emission factors stored per record
Apply DEFRA 2023 factors at import time and store both co2e_kg and emission_factor_used on each record. Creates an immutable audit trail — if DEFRA updates factors, historical records retain the factor correct at the time.

## D5: django-simple-history for audit trail
Use HistoricalRecords on EmissionRecord. Auto-creates a shadow table with every field change, the user who made it, and the timestamp. Zero extra code. Auditors can query the full history of any record.

## D6: One unified table (not one per source)
All three sources flow into EmissionRecord. Nullable fields handle source-specific data (distance_km is NULL for non-travel rows). The tradeoff — nullable columns — is worth the benefit of a single approval workflow and single audit schema.
