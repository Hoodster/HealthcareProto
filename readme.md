<p align="center">
  <img
    src="https://mir-s3-cdn-cf.behance.net/project_modules/disp/ef5103232954083.692a23beb7a5d.gif"
    width="1000"
  />
</p>

# HealthcareProto
Backend service for Healthcare Prototype App
## Project Layout

```text
alembic/          Database migrations  
api/              FastAPI app, routes, services, SQLAlchemy models
expert_system/    Rule engine and clinical rules
models/           Pydantic schemas shared across the app
scripts/          Database initialization and utility scripts
```

## Start here - local configuration
1. Create runtime variables from the sample file and edit new `.env` file:

```bash
cp .env.example .env
```
2. Create local environment and install required packages (requires Python installed) <br/>

```bash
python3 -m venv .venv

source .venv/bin/activate
pip3 install -r requirements.txt
alembic upgrade head
```
3. Run app
```bash
python3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload  
```
## or start here - docker configuration
You can either build whole image or split app on separate modules.

```bash
docker compose up -d [ | postgres | backend]
```

## Database
Based on `DB_URL` value app determines target between SQLite (locally) and PostgreSQL (locally + web).

Database schema is managed by **Alembic** for migrations.

### Migrations
When you make changes to models in `api/models.py`, generate and apply a migration:

```bash
# Generate migration from model changes
alembic revision --autogenerate -m "description of changes"

# Apply migration to database
alembic upgrade head

# Check current database revision
alembic current

# Rollback one migration
alembic downgrade -1
```

SQLite database is saved in /.output folder by default. You can change it in `.env`

## Documentation
After local run you can find swagger docs in <br>
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