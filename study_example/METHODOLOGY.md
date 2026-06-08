# Metodologia porównań — co jest zdefiniowane w kodzie

Ten dokument opisuje **wyłącznie to, co jest zaimplementowane** w repozytorium.  
Nie dodawaj w pracy parametrów, których tu nie ma.

---

## 1. Trzy osobne warstwy (nie mieszaj ich w jednej „prawdzie”)

| Warstwa | Źródło | Co oznacza |
|---------|--------|------------|
| **A. Outcome MIMIC** | `mimiciii.admissions.hospital_expire_flag` | `1` = pacjent zmarł w szpitalu podczas tej hospitalizacji; `0` = wypisany żywy. To **jedyny fakt retrospektywny** z bazy. |
| **B. Proxy wytycznych** | `PipelineService._compute_ground_truth()` | Reguły: ≥2 leki QT, eGFR &lt; 30. To **nie jest diagnoza lekarza** — operacjonalizacja do benchmarku. |
| **C. Sygnał systemu** | expert / genai / rag_full | Czy dane podejście **uznało** wysokie ryzyko bezpieczeństwa leków (definicja poniżej). |

**Ważne:** System **nie widzi** `hospital_expire_flag` w momencie oceny — widzi tylko leki, eGFR, rozpoznania itd. Porównanie z zgonem to analiza retrospektywna, **nie predykcja śmierci**.

---

## 2. Wejście kliniczne z MIMIC (`build_mimic_patient_context`)

| Pole | Skąd | Ograniczenie |
|------|------|--------------|
| `medications` | `prescriptions.drug_name_generic` | lista generyczna, deduplikowana |
| `egfr` | ostatnia kreatynina (itemid 50912) + wzór MDRD | brak labu → domyślnie 90 |
| `conditions` | ICD-9 (częściowo zmapowane) | reszta jako `icd9:...` |
| `age`, `gender` | `patients` + `admissions.admittime` | MIMIC maskuje wiek ≥89 |

Kohorta: pacjenci z ICD-9 **426\*, 428\*, 42731, 42732, 4271** (`get_heart_patients`).

---

## 3. Definicja „sygnału bezpieczeństwa” per podejście

Źródło: `PipelineService._compute_metrics()`.

| Podejście | `detected_high_risk = true` gdy… |
|-----------|----------------------------------|
| **expert** | `contraindicated` LUB alert severity `critical` / `high` |
| **genai** (LLM) | w odpowiedzi wykryto słowa kluczowe: `qt_prolongation`, `contraindication`, `drug_interaction` |
| **rag_full** (RAG+LLM+expert) | są alerty experta LUB te same słowa kluczowe w odpowiedzi LLM |

Słowa kluczowe LLM: `_extract_risks_from_text()` — lista stała w kodzie, **nie** ocena kliniczna.

---

## 4. Co porównujesz w badaniu (LLM vs RAG)

Skrypt `scripts/run_comparison.py` generuje tabelę z kolumnami:

- `mimic_died` — outcome z MIMIC (warstwa A)
- `guideline_violations` — proxy (warstwa B), **osobno**
- `genai_safety_concern` / `rag_safety_concern` — sygnał (warstwa C)
- `genai_response_excerpt` / `rag_response_excerpt` — fragment odpowiedzi do ręcznej weryfikacji
- `same_concern_genai_rag` — czy oba podejścia dały ten sam sygnał tak/nie

**Sensowne pytania badawcze (bez „wynalezionych” metryk):**

1. W kohortcie **zgon w szpitalu**: jaki % przypadków LLM vs RAG oznaczył `safety_concern`?
2. W kohortcie **przeżyli**: jaki % fałszywych alarmów (concern przy `mimic_died=0`)?
3. Gdzie RAG **różni się** od LLM (same_concern = false) — case studies z CSV.

---

## 5. Czego **nie** pisać w pracy

- Nie nazywaj `is_high_risk` „prawdziwym ryzykiem klinicznym” — to OR(proxy wytycznych, zgon).
- Nie pisz, że system przewiduje śmierć — porównujesz **sygnał bezpieczeństwa leków** z **outcome** retrospektywnie.

---

## 6. Uruchomienie

```bash
python scripts/run_comparison.py --limit 30
python scripts/run_comparison.py --limit 20 --outcome died --output artifacts/death_cohort.csv
```

Pełna instrukcja: [QUICKSTART.md](../QUICKSTART.md)
