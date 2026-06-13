

# HealthcareProto

**Informatyczna platforma monitorowania i oceny bezpieczeństwa leków
przeciwarytmicznych** w leczeniu chorób układu krążenia — z wykorzystaniem
algorytmów AI (GenAI + RAG) i systemu eksperckiego. Walidacja względem outcome MIMIC.

Trzy podejścia oceniają bezpieczeństwo antyarytmików (QT, interakcje CYP, bradykardia,
przeciwwskazania nerkowe): **system ekspercki**, **GenAI** (LLM), **RAG** (LLM + wytyczne + expert).

## Szybki start — wyniki dla n przypadków

→ **[QUICKSTART.md](QUICKSTART.md)** ← jedna komenda, CSV + Markdown + JSON

```bash
pip install -r requirements.txt
# Ocena bezpieczeństwa antyarytmików (opis + studia przypadków + źródła RAG)
python scripts/run_comparison.py --limit 30 --antiarrhythmic-only --markdown artifacts/safety.md
```

Monitoring per pacjent: `GET /hp_proto/api/pipeline/antiarrhythmic-safety/{subject_id}/{hadm_id}`

Serwis: [https://azaphtn4tglr3jlgw.azurewebsites.net/hp_proto/api/swagger](https://azaphtn4tglr3jlgw.azurewebsites.net/hp_proto/api/swagger)

## Instrukcja

Zalecana ścieżka — od gotowego wyniku do kodu:

1. **Zobacz gotowy raport** → `[artifacts/safety.md](artifacts/safety.md)`. Czyta się go
  w trzech sekcjach:
  - **Sekcja 1** — jak często każde podejście (expert / GenAI / RAG) zgłasza obawę
  i jak to się ma do zgonu (% obaw ogółem vs wśród zmarłych vs przeżywających).
  - **Sekcja 2** — zgodność GenAI vs RAG (oba / tylko jeden / żadne).
  - **Sekcja 3** — studia przypadków, gdzie podejścia się **różnią**, z fragmentami
  odpowiedzi AI i źródłem RAG. To tu widać „co AI zrobiło inaczej".
2. **Wygeneruj świeże wyniki** dla dowolnego N → `python scripts/run_comparison.py --limit 30 --markdown artifacts/safety.md`.
  Duże N pobierane jest stronami (`--chunk`), więc nie trafia w timeout bramy.
   Szczegóły komend i flag: `[QUICKSTART.md](QUICKSTART.md)`.
3. **Sprawdź definicje** (czym jest „sygnał bezpieczeństwa", dlaczego bez F1/PPV) →
  `[study_example/METHODOLOGY.md](study_example/METHODOLOGY.md)` i
  `[study_example/SAFETY_DEFINITION.md](study_example/SAFETY_DEFINITION.md)`.
  Architektura: `[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)`.
4. **Przejrzyj jednego pacjenta** interaktywnie w Swaggerze →
  `GET /hp_proto/api/pipeline/antiarrhythmic-safety/{subject_id}/{hadm_id}`
   (zwraca `safety_score`, alerty eksperta, werdykty GenAI/RAG i użyte źródła RAG).
5. **Wejdź w kod** wg sekcji *Struktura* poniżej (reguły eksperta, pipeline, RAG).

**Integracja frontu:** → **[FRONTEND_API.md](FRONTEND_API.md)** (auth, chat LLM/RAG, przypisanie MIMIC, comparison, typy TS)

## Struktura

```text
api/              FastAPI, pipeline, outcome comparison, monitoring endpoint
expert_system/    Reguły bezpieczeństwa antyarytmików (QT, CYP, β-bloker, DrugBank, nerki)
scripts/          run_comparison.py, run_pilot.py (pilotaż pracy magisterskiej)
study_example/    Metodologia, definicja bezpieczeństwa, szkielet rozdziałów (THESIS_DRAFT)
docs/             ARCHITECTURE.md — opis systemu dla promotora
```

## Dev lokalny

```bash
cp .env.example .env   # DB_URL, API_OPENAI
alembic upgrade head
uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload
```

Swagger: [http://localhost:8000/hp_proto/api/swagger](http://localhost:8000/hp_proto/api/swagger)

## Więcej


| Dokument                                                     | Zawartość                        |
| ------------------------------------------------------------ | -------------------------------- |
| [QUICKSTART.md](QUICKSTART.md)                               | Jak pobrać wyniki (API / skrypt) |
| [FRONTEND_API.md](FRONTEND_API.md)                           | Instrukcja integracji frontu     |
| [study_example/METHODOLOGY.md](study_example/METHODOLOGY.md) | Definicje metryk do pracy        |
| [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md)                   | Redeploy, MIMIC seed, migracje   |


