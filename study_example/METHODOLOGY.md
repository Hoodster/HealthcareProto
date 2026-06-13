# Metodologia — bezpieczeństwo leków przeciwarytmicznych

Platforma ocenia **bezpieczeństwo leków przeciwarytmicznych** w leczeniu chorób
układu krążenia trzema metodami — **system ekspercki + GenAI + RAG** — i waliduje
sygnał bezpieczeństwa względem retrospektywnego outcome MIMIC.

Ten dokument opisuje **wyłącznie to, co jest zaimplementowane** w repozytorium.  
Nie dodawaj w pracy parametrów, których tu nie ma.

**Leki przeciwarytmiczne (Vaughan-Williams I/III)** — `ANTIARRHYTHMIC_DRUGS` w
[`expert_system/rules/interaction_rules.py`](../expert_system/rules/interaction_rules.py):
quinidine, procainamide, disopyramide, lidocaine, mexiletine, flecainide,
propafenone, amiodarone, dronedarone, sotalol, dofetilide, ibutilide.

---

## 1. Trzy osobne warstwy (nie mieszaj ich w jednej „prawdzie”)

| Warstwa | Źródło | Co oznacza |
|---------|--------|------------|
| **A. Outcome MIMIC** | `mimiciii.admissions.hospital_expire_flag` | `1` = pacjent zmarł w szpitalu podczas tej hospitalizacji; `0` = wypisany żywy. To **jedyny fakt retrospektywny** z bazy. |
| **B. Wytyczne (expert)** | `ExpertSystemResult.rule_tags` z [`rule_tags.py`](../expert_system/rule_tags.py) | Tagi z **odpalonych reguł** eksperta (QT, nerki, HF, CYP…). Predykaty w [`guideline_checks.py`](../expert_system/guideline_checks.py). |
| **C. Sygnał LLM/RAG** | genai / rag (`LLM_PROVIDER=openai|claude`) | Czy dane podejście **uznało** wysokie ryzyko bezpieczeństwa leków (definicja poniżej). |

**Ważne:** System **nie widzi** `hospital_expire_flag` w momencie oceny — widzi tylko leki, eGFR, rozpoznania itd. Porównanie z zgonem to analiza retrospektywna, **nie predykcja śmierci**.

Expert **jest** operacjonalizacją wytycznych — tagi `rule_tags` pochodzą z odpalonych reguł, nie z osobnej warstwy proxy.

---

## 2. Wejście kliniczne z MIMIC (`build_mimic_patient_context`)

| Pole | Skąd | Ograniczenie |
|------|------|--------------|
| `medications` | `prescriptions.drug_name_generic` | lista generyczna, deduplikowana |
| `egfr` | ostatnia kreatynina (itemid 50912) + wzór MDRD | brak labu → domyślnie 90 |
| `conditions` | ICD-9 (częściowo zmapowane) | reszta jako `icd9:...` |
| `age`, `gender` | `patients` + `admissions.admittime` | MIMIC maskuje wiek ≥89 |

Kohorta: pacjenci z ICD-9 **426\*, 428\*, 42731, 42732, 4271, 2768** (`get_heart_patients`).
Flaga `--antiarrhythmic-only` / parametr `antiarrhythmic_only` zawęża analizę do
pacjentów z faktyczną **ekspozycją antyarytmiczną** (`on_antiarrhythmic = true`).

---

## 3. Reguły bezpieczeństwa antyarytmików (system ekspercki)

Źródło: [`expert_system/rules/`](../expert_system/rules/), silnik
`RuleEngine._load_default_rules()`.

| Reguła | Co wykrywa |
|--------|-----------|
| `SevereRenalImpairmentRule` / `Moderate` / `Mild` | progi eGFR |
| `QTProlongingDrugInteractionRule` | ≥2 leki QT lub combo antyarytmik QT + inny lek QT — **critical** |
| `CYPInhibitorInteractionRule` / `CYPInducerInteractionRule` | inhibitory / induktory CYP |
| `BetaBlockerInteractionRule` | β-bloker + antyarytmik — **moderate** |
| `DatabaseDrugInteractionRule` | pary leków DrugBank — **high** |
| `RenalContraindicatedAntiarrhythmicRule` | sotalol/dofetilide + eGFR&lt;30 — **contraindicated** |
| `AntiplateletQtRiskRule` | antyagregacja + lek QT |
| `AmiodaroneMonitoringRule` | alert monitoringu amiodaronu |
| `ClassICStructuralHeartRule` | flecainide/propafenone + HF/IHD — **contraindicated** |
| `DronedaroneHeartFailureRule` | dronedarone + HF — **contraindicated** |
| `NonDhpCcbHeartFailureRule` | diltiazem/werapamil + HF |
| `DigoxinRenalAgeRule` | digoxin + eGFR&lt;30 lub wiek≥75 |
| `AvBlockBradycardiaRiskRule` | AV block (ICD) + bradykardia-risk drugs |

Reguły rate-control (`digoxin`, `diltiazem`, `verapamil`) działają na liście leków pacjenta, ale **nie** rozszerzają filtra kohorty `--antiarrhythmic-only`.

Predykaty reguł: [`guideline_checks.py`](../expert_system/guideline_checks.py). Mapowanie reguła→tag: [`rule_tags.py`](../expert_system/rule_tags.py).

### Definicja „sygnału bezpieczeństwa” per podejście

Źródło: `PipelineService._compute_metrics()`.

| Podejście | `detected_high_risk = true` gdy… |
|-----------|----------------------------------|
| **expert** | `contraindicated` LUB alert severity `critical` / `high` |
| **genai** (LLM) | LLM zwraca `SAFETY_VERDICT: HIGH_RISK` (strukturalny werdykt per pacjent) |
| **rag** (RAG+LLM+expert) | LLM (widząc wytyczne RAG + alerty eksperta) zwraca `SAFETY_VERDICT: HIGH_RISK` |

**Werdykt zamiast słów kluczowych:** prompt wymaga, by LLM zakończył odpowiedź jedną
linią `SAFETY_VERDICT: HIGH_RISK|LOW_RISK` — to ocena per pacjent, nie wykrycie
przypadkowego słowa. Parser: `_extract_safety_verdict()` (fallback do słów kluczowych
`_extract_risks_from_text()` tylko gdy werdykt nie został zwrócony).
Lista `detected_risks` (słowa kluczowe) służy już **tylko** jako informacyjny opis
czynników, nie jako sygnał decyzyjny.

---

## 4. Co porównujesz w badaniu (expert vs GenAI vs RAG)

Skrypt `scripts/run_comparison.py` generuje tabelę (CSV) i raport (Markdown) z kolumnami:

- `mimic_died` — outcome z MIMIC (warstwa A)
- `antiarrhythmic_drugs` / `on_antiarrhythmic` — ekspozycja antyarytmiczna
- `qt_drug_count`, `expert_rule_tags` — tagi wytyczne z odpalonych reguł eksperta
- `expert_safety_concern` / `genai_safety_concern` / `rag_safety_concern` — sygnał (warstwa C)
- `rag_sources` / `rag_sources_used` — **dokumenty faktycznie przetworzone przez RAG** (filename + score)
- `genai_response_excerpt` / `rag_response_excerpt` — fragment odpowiedzi do ręcznej weryfikacji
- `same_concern_genai_rag` — czy GenAI i RAG dały ten sam sygnał

### Dlaczego NIE liczymy precyzji/czułości/F1

MIMIC **nie zawiera złotego standardu** etykiety „zagrożenie bezpieczeństwa
antyarytmiku”. API pipeline (`evaluate-mimic`) zwraca **sygnały bezpieczeństwa**
(`detected_high_risk`, `risk_level` 0–2) i **etykiety referencyjne** warstw A/B
(`reference_labels`) — **bez** F1, precision, recall.

Każdy możliwy target klasyfikacji byłby wadliwy:

- **zgon** — „safety concern” ≠ „pacjent umrze” (pacjent z ryzykownym lekiem może
  przeżyć, bo lekarz zareagował); PPV/F1 byłyby z definicji zaniżone i mylące;
- **tagi wytyczne eksperta** — system LLM/RAG porównujemy z expertem, więc walidacja
  expert vs expert byłaby błędnym kołem (~100% z definicji).

Dlatego raport stosuje **trzy analizy bez „prawdy”**:

**(1) Selektywność + opisowa asocjacja ze zgonem** (`OutcomeComparisonSummary`):
% przypadków, w których podejście zgłasza obawę — ogółem oraz osobno wśród
**zmarłych** i **przeżywających**. Niższy „% ogółem” = większa selektywność;
różnica zmarli–przeżywający = opisowy (nie przyczynowy) związek z outcome.

**(2) Zgodność / rozbieżności** między expert / GenAI / RAG
(`genai_rag_agreement_pct`, `disagreement_count`) — gdzie AI odbiega od reguł.

**(3) Studia przypadków** — wiersze z rozbieżnym sygnałem, z fragmentami odpowiedzi
GenAI/RAG i źródłami RAG, do jakościowej oceny *dlaczego* podejścia się różnią.

---

## 5. RAG przetwarza źródła (dowód)

Baza wiedzy: `artifacts/rag_knowledge.json` (wytyczne z `.sources/*.pdf`, np. ESC 2019
Supraventricular Tachycardia), budowana przez `scripts/seed_rag_knowledge.py`.
`api/rag_store.retrieve_context_with_sources()` zwraca tekst **oraz** listę
`rag_sources` (filename, doc_type, score). Zapytanie jest budowane per pacjent
(`build_rag_query` — leki, choroby, eGFR), więc **score różni się między pacjentami**.
Korpus wytycznych jest niewielki (kilka PDF), więc **nazwy plików się powtarzają**;
różnicowanie zachodzi na poziomie chunków i score (raport pokazuje top źródło + score).
Weryfikacja: `python scripts/test_rag.py`.

---

## 6. Monitoring per pacjent

Endpoint: `GET /hp_proto/api/pipeline/antiarrhythmic-safety/{subject_id}/{hadm_id}`
(`PipelineService.assess_antiarrhythmic_safety`). Zwraca `AntiarrhythmicSafetyReport`:
ekspozycję antyarytmiczną, alerty eksperta, sygnał+odpowiedź GenAI, sygnał+odpowiedź+`rag_sources`
RAG, `safety_score` (100 − `risk_score`), zgodność podejść i `recommendation`.

---

## 7. Przykład (worked example)

Pacjent na **amiodaronie + sotalolu** z eGFR 22:

- **Expert**: `RenalContraindicatedAntiarrhythmicRule` → sotalol **contraindicated** (eGFR < 30);
  `QTProlongingDrugInteractionRule` → additive QT (critical); `risk_score = 100` → `safety_score = 0`.
- **GenAI**: w odpowiedzi `qt_prolongation` + `renal_impairment` → `safety_concern = true`.
- **RAG**: te same sygnały + `rag_sources` z wytycznych (np. `2019_SupraventricularTachycardia.pdf`).
- **Zgodność**: `approaches_agree = true`; `recommendation`: zamień antyarytmik / unikaj.

Wygeneruj realnym przebiegiem:

```bash
python scripts/run_comparison.py --local --limit 30 --antiarrhythmic-only --markdown artifacts/safety.md
```

## 9. Uruchomienie

```bash
# Cała kohorta kardiologiczna
python scripts/run_comparison.py --limit 30 --markdown artifacts/safety.md
# Tylko pacjenci na antyarytmiku (sedno tematu)
python scripts/run_comparison.py --limit 30 --antiarrhythmic-only --markdown artifacts/safety.md
# Kohorta zgonów
python scripts/run_comparison.py --limit 20 --outcome died --output artifacts/death_cohort.csv
```

Pełna instrukcja: [QUICKSTART.md](../QUICKSTART.md)
