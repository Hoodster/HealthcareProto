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
scripts/          Scripts
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
Based on `DB_URL` value app determines target between SQLLite (locally) and postgreSQL (locally + web)
For migrations project uses **alembic**.

### Migrations
To get newest schema to existing database or to adjust after code change run

```bash
alembic revision --autogenerate -m "message" # skip for update only
alembic upgrade head
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