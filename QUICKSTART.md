# HealthcareProto — szybki start

Porównanie **LLM vs RAG** z outcome MIMIC (`hospital_expire_flag`) dla **n** pacjentów kardiologicznych.

## Serwis (Azure)

| | |
|---|---|
| **API** | https://azaphtn4tglr3jlgw.azurewebsites.net |
| **Swagger** | https://azaphtn4tglr3jlgw.azurewebsites.net/hp_proto/api/swagger |
| **Login testowy** | `doctor@local` / `doctor` |

## Wyniki w 1 komendzie

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/run_comparison.py --limit 20 --json artifacts/report.json
```

Pliki:
- **CSV** → `artifacts/comparison_<data>.csv` (tabela per pacjent)
- **JSON** → opcjonalnie `--json artifacts/report.json` (podsumowanie + wiersze)

### Parametry

| Flaga | Domyślnie | Opis |
|-------|-----------|------|
| `--limit N` | 20 | Liczba przypadków (max 200) |
| `--outcome all\|died\|survived` | all | Filtr po zgonie w szpitalu |
| `--output plik.csv` | auto | Ścieżka CSV |
| `--json plik.json` | — | Pełny raport JSON |
| `--timeout 900` | 900 | Timeout HTTP (sekundy) |

Przykłady:

```bash
# Kohorta zgonów w szpitalu
python scripts/run_comparison.py --limit 15 --outcome died

# Lokalna baza (DB_URL w .env) zamiast Azure
python scripts/run_comparison.py --local --limit 10
```

**Czas:** ~10–20 s na przypadek. `--limit 20` ≈ 5–10 min.

## Swagger (ręcznie)

1. `POST /hp_proto/api/auth/login` → skopiuj `access_token`
2. **Authorize** → `Bearer <token>`
3. `GET /hp_proto/api/pipeline/outcome-comparison?limit=20&outcome=all`

## Co oznaczają kolumny

| Kolumna | Znaczenie |
|---------|-----------|
| `mimic_died` | Fakt z MIMIC: zgon w szpitalu |
| `guideline_violations` | Proxy reguł (≥2 leki QT, eGFR&lt;30) |
| `genai_safety_concern` | Sygnał LLM (słowa kluczowe w odpowiedzi) |
| `rag_safety_concern` | Sygnał RAG+LLM+expert |
| `same_concern_genai_rag` | Czy LLM i RAG zgodne (tak/nie) |

Szczegóły metodologiczne: [`study_example/METHODOLOGY.md`](study_example/METHODOLOGY.md).

Wdrożenie Azure: [`AZURE_DEPLOYMENT.md`](AZURE_DEPLOYMENT.md).
