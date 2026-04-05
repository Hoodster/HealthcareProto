# HealthcareProto

## Project Layout

```text
api/              FastAPI app, routes, services, SQLAlchemy models
expert_system/    Rule engine and clinical rules
models/           Pydantic schemas shared across the app
scripts/          Scripts
```

## Configuration
Create it from the sample file:

```bash
cp .env.example .env
```

## Quick Start

### Full docker

This starts PostgreSQL and the backend together.

```bash
docker compose up --build
```

API docs:

```text
http://localhost:8000/hp_proto/api/swagger
```

### DB + backend

Start PostgreSQL only:

```bash
docker compose up -d postgres
```

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

### Run
```bash
python3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload
```
## Documentation
http://localhost:8000/hp_proto/api/swagger
## MIMIC-III Demo Import

If you want to load MIMIC demo data into PostgreSQL:

1. Put the CSV files under `.sources/mimic/`.
2. Ensure `.sources/mimic/.create_tables.sql` exists.
3. Configure the PostgreSQL connection in `.env`.
4. Run:

```bash
python3 scripts/init_mimic_db.py
```

The script creates and populates the `mimiciii` schema.

## Expert System

```bash
python3 -m expert_system.test_cases
```
