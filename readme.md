<p align="center">
  <img
    src="https://mir-s3-cdn-cf.behance.net/project_modules/disp/ef5103232954083.692a23beb7a5d.gif"
    width="1000"
  />
</p>

# HealthcareProto

Backend CDS: expert system + LLM + RAG dla bezpieczeństwa leków u pacjentów kardiologicznych (MIMIC).

## Szybki start — wyniki dla n przypadków

→ **[QUICKSTART.md](QUICKSTART.md)** ← jedna komenda, CSV + JSON

```bash
pip install -r requirements.txt
python scripts/run_comparison.py --limit 20
```

Serwis: https://azaphtn4tglr3jlgw.azurewebsites.net/hp_proto/api/swagger

## Struktura

```text
api/              FastAPI, pipeline, outcome comparison
expert_system/    Reguły (eGFR, interakcje leków QT)
scripts/          run_comparison.py — główny skrypt wyników
study_example/    Metodologia pod pracę magisterską
```

## Dev lokalny

```bash
cp .env.example .env   # DB_URL, API_OPENAI
alembic upgrade head
uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload
```

Swagger: http://localhost:8000/hp_proto/api/swagger

## Więcej

| Dokument | Zawartość |
|----------|-----------|
| [QUICKSTART.md](QUICKSTART.md) | Jak pobrać wyniki (API / skrypt) |
| [study_example/METHODOLOGY.md](study_example/METHODOLOGY.md) | Definicje metryk do pracy |
| [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md) | Redeploy, MIMIC seed, migracje |
