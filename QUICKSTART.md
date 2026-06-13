# HealthcareProto — szybki start

Ocena **bezpieczeństwa leków przeciwarytmicznych**: **system ekspercki vs GenAI vs RAG**,
walidacja względem outcome MIMIC (`hospital_expire_flag`) dla **n** pacjentów kardiologicznych.

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

# Tylko pacjenci na antyarytmiku (sedno tematu) — CSV + raport Markdown
python scripts/run_comparison.py --limit 30 --antiarrhythmic-only --markdown artifacts/safety.md
```

Pliki:
- **CSV** → `artifacts/comparison_<data>.csv` (tabela per pacjent + źródła RAG)
- **Markdown** → `--markdown artifacts/safety.md` (metryki + tabela przypadków, pod pracę)
- **JSON** → opcjonalnie `--json artifacts/report.json` (podsumowanie + wiersze)

### Parametry

| Flaga | Domyślnie | Opis |
|-------|-----------|------|
| `--limit N` | 20 | Łączna liczba przypadków do zebrania |
| `--chunk N` | 8 | Wierszy na jedno żądanie API (małe = pod limitem bramy ~230 s) |
| `--offset N` | 0 | Indeks pacjenta startowego (paginacja) |
| `--antiarrhythmic-only` | off | Tylko pacjenci z ekspozycją antyarytmiczną |
| `--outcome all\|died\|survived` | all | Filtr po zgonie w szpitalu |
| `--output plik.csv` | auto | Ścieżka CSV |
| `--markdown plik.md` | — | Raport Markdown (opis + przypadki) |
| `--json plik.json` | — | Pełny raport JSON |
| `--local` | off | Czyta z lokalnej DB (DB_URL w .env) zamiast API |
| `--timeout 900` | 900 | Timeout pojedynczego żądania HTTP (sekundy) |

Przykłady:

```bash
# Kohorta zgonów w szpitalu
python scripts/run_comparison.py --limit 15 --outcome died

# Lokalna baza (DB_URL w .env) zamiast Azure
python scripts/run_comparison.py --local --limit 10

# Weryfikacja, że RAG pobiera źródła
python scripts/test_rag.py
```

**Czas:** ~10–20 s na przypadek. Duże `--limit` jest pobierane stronami po `--chunk`
przypadków (każde żądanie kończy się pod limitem bramy ~230 s), więc skalowanie nie
trafia w błąd 504 — np. `--limit 50 --chunk 8`.

## Swagger (ręcznie)

1. `POST /hp_proto/api/auth/login` → skopiuj `access_token`
2. **Authorize** → `Bearer <token>`
3. Batch: `GET /hp_proto/api/pipeline/outcome-comparison?limit=8&offset=0&antiarrhythmic_only=true`
   — odpowiedź zwraca `next_offset`; podaj go jako `?offset=` po kolejną stronę.
4. Monitoring per pacjent: `GET /hp_proto/api/pipeline/antiarrhythmic-safety/{subject_id}/{hadm_id}`

## Co oznaczają kolumny

| Kolumna | Znaczenie |
|---------|-----------|
| `mimic_died` | Fakt z MIMIC: zgon w szpitalu |
| `antiarrhythmic_drugs` / `on_antiarrhythmic` | Ekspozycja antyarytmiczna |
| `expert_rule_tags` | Tagi wytyczne z odpalonych reguł eksperta (QT, nerki, HF, CYP…) |
| `expert_safety_concern` | Sygnał systemu eksperckiego (reguły) |
| `genai_safety_concern` | Sygnał LLM (strukturalny werdykt `SAFETY_VERDICT` per pacjent) |
| `rag_safety_concern` | Sygnał RAG+LLM+expert (werdykt `SAFETY_VERDICT`) |
| `rag_sources` / `rag_sources_used` | Dokumenty faktycznie przetworzone przez RAG |
| `same_concern_genai_rag` | Czy LLM i RAG zgodne (tak/nie) |

Bez metryk klasyfikacji (brak złotego standardu w MIMIC): raport pokazuje % obaw
ogółem oraz wśród zmarłych/przeżywających (`summary.*_concern_*_pct`), zgodność
podejść i **studia przypadków rozbieżności** z odpowiedziami AI.

Szczegóły metodologiczne: [`study_example/METHODOLOGY.md`](study_example/METHODOLOGY.md).

Wdrożenie Azure: [`AZURE_DEPLOYMENT.md`](AZURE_DEPLOYMENT.md).
