# Definicja bezpieczeństwa leków przeciwarytmicznych

Dokument opisuje **wyłącznie to, co jest zaimplementowane** w repozytorium HealthcareProto (stan na `release/v0.2.1`).  
Nie należy w pracy magisterskiej twierdzić o parametrach, których system nie ocenia.

**Zakres danych:** wdrożony zestaw to **MIMIC-III Clinical Database Demo** (~100 pacjentów, ~129 hospitalizacji) — patrz [`AZURE_DEPLOYMENT.md`](../AZURE_DEPLOYMENT.md). Pełny MIMIC wymaga osobnego importu (Credentialed Access).

---

## Trzy warstwy oceny (nie mieszaj w jednej „prawdzie”)

| Warstwa | Źródło | Znaczenie |
|---------|--------|-----------|
| **A. Outcome MIMIC** | `admissions.hospital_expire_flag`, `icustays`, LOS | Fakty retrospektywne — punkt odniesienia, **nie** definicja bezpieczeństwa leków |
| **B. Wytyczne (expert)** | `ExpertSystemResult.rule_tags` — tagi z odpalonych reguł | Operacjonalizacja wytycznych w kodzie — **nie** diagnoza lekarza |
| **C. Sygnał LLM/RAG** | genai / rag (OpenAI lub Claude) | Czy dane podejście uznało istotne ryzyko bezpieczeństwa (werdykt + alerty) |

System **nie widzi** `hospital_expire_flag` w momencie oceny pacjenta.

Expert **jest** operacjonalizacją wytycznych — tagi `rule_tags` pochodzą z odpalonych reguł (`RULE_TO_TAG` w [`rule_tags.py`](../expert_system/rule_tags.py)), predykaty w [`guideline_checks.py`](../expert_system/guideline_checks.py).

---

## Tabela parametrów bezpieczeństwa

| Kategoria | Parametr | Źródło danych | Reguła / próg w systemie | Dostępne w bazie? | Używane w pipeline? | Uwagi |
|-----------|----------|---------------|--------------------------|-------------------|---------------------|-------|
| Nerki | eGFR | MIMIC `labevents` kreatynina (itemid **50912**) → MDRD | &lt;30 severe; 30–60 moderate; 60–90 mild | **Tak** | **Tak** | Brak labu → domyślnie **eGFR=90** |
| Nerki | Antyarytmik + niewydolność | eGFR + leki | `RenalContraindicatedAntiarrhythmicRule` | Tak | Tak | sotalol, dofetilide → contraindicated przy eGFR &lt; 30 |
| Serce / EKG | **QTc (ms)** | EKG / chartevents | brak reguł QTc | **Nie w seedzie** | **Nie** | `chartevents` nie importowany; `PatientContext` bez `qtc` |
| Serce / EKG | Ryzyko QT (proxy lekowe) | `prescriptions` | `QTProlongingDrugInteractionRule` (≥2 leki QT lub combo AAD+QT) | Tak | Tak | **Proxy — nie pomiar EKG** |
| Serce | Bradykardia (interakcja) | leki + antyarytmik | `BetaBlockerInteractionRule` (β-bloker + AAD) | Tak | Tak | |
| Serce | AV block + bradykardia | ICD 426* + leki | `AvBlockBradycardiaRiskRule` | Tak | Tak | |
| Interakcje | CYP induktory | lista leków | `CYPInducerInteractionRule` | Tak | Tak | |
| Interakcje | Antyagregacja + QT | leki | `AntiplateletQtRiskRule` | Tak | Tak | proxy krwawienia, nie OAC |
| Choroby | Class IC + HF/IHD | ICD + leki | `ClassICStructuralHeartRule` | Tak | Tak | flecainide, propafenone |
| Choroby | Dronedaron + HF | ICD 428* | `DronedaroneHeartFailureRule` | Tak | Tak | contraindicated |
| Choroby | CCB + HF | diltiazem/werapamil | `NonDhpCcbHeartFailureRule` | Tak | Tak | rate-control |
| Choroby | Digoxin + nerki/wiek | eGFR, age | `DigoxinRenalAgeRule` | Tak | Tak | rate-control |
| Monitoring | Amiodaron | leki | `AmiodaroneMonitoringRule` | Tak | Tak | alert edukacyjny |
| Interakcje | CYP inhibitory | lista leków | `CYPInhibitorInteractionRule` | Tak | Tak | |
| Interakcje | Pary leków (DrugBank) | `app.drug_interactions` | `DatabaseDrugInteractionRule` | Tak (po seed) | Tak | `seed_drug_interactions.py` |
| Interakcje | Antyarytmik (WW I/III) | prescriptions | `ANTIARRHYTHMIC_DRUGS` | Tak | Tak | filtr `--antiarrhythmic-only` |
| Choroby | AF / CHF / blok / IHD | `diagnoses_icd` ICD-9 | reguły `condition_rules.py` + LLM | Tak | Tak | mapowanie 414*, 424*, 428*, 426* |
| Wątroba | ALT / AST | `labevents` | brak reguł labowych | Częściowo (tabela) | **Nie** | amiodaron tylko alert monitoringu |
| Outcome | Zgon hospitalizacyjny | `hospital_expire_flag` | warstwa A | Tak | Tak (retrospektywnie) | nie jedyna definicja bezpieczeństwa |
| Outcome | Pobyt ICU | `icustays` | kolumna `icu_admitted` | Tak | Tak | join po `hadm_id` |
| Outcome | Długość pobytu | `admittime` / `dischtime` | kolumna `los_days` | Tak | Tak | w dniach |

---

## Tagi wytyczne eksperta (`rule_tags`)

Źródło: odpalone reguły → [`expert_rule_tags()`](../expert_system/rule_tags.py).

| Tag | Warunek (skrót) |
|-----|-----------------|
| `QT_INTERACTION` | ≥2 leki z listy QT |
| `QT_AAD_COMBO` | antyarytmik QT + inny lek QT |
| `SEVERE_RENAL_IMPAIRMENT` | eGFR &lt; 30 |
| `MODERATE_RENAL_IMPAIRMENT` | 30 ≤ eGFR &lt; 60 |
| `MILD_RENAL_IMPAIRMENT` | 60 ≤ eGFR &lt; 90 |
| `RENAL_CONTRAINDICATED_AAD` | sotalol/dofetilide + eGFR&lt;30 |
| `CYP_INHIBITOR_INTERACTION` | inhibitor CYP |
| `CYP_INDUCER_INTERACTION` | induktor CYP |
| `BETA_BLOCKER_INTERACTION` | β-bloker + antyarytmik |
| `AV_BLOCK_BRADY_RISK` | ICD AV block + bradykardia-risk |
| `CLASS_IC_STRUCTURAL_HF` | flecainide/propafenone + HF/IHD |
| `DRONEDARONE_HF` | dronedarone + HF |
| `CCB_HF` | diltiazem/werapamil + HF |
| `DIGOXIN_RENAL_AGE` | digoxin + (eGFR&lt;30 lub wiek≥75) |
| `AMIODARONE_MONITORING` | amiodarone |
| `ANTIPLATELET_QT_RISK` | antyagregacja + lek QT |
| `DRUGBANK_INTERACTION` | ≥1 para z DrugBank |

---

## Skala ryzyka (pilotaż i raporty)

| Poziom | Kod | Expert | LLM / RAG |
|--------|-----|--------|-----------|
| 0 — safe | `0` / `safe` | brak alertów critical/high, nie contraindicated | `SAFETY_VERDICT: LOW_RISK` |
| 1 — warning | `1` / `warning` | alert moderate/high (bez contraindication) | `HIGH_RISK` bez contraindication |
| 2 — unsafe | `2` / `unsafe` | `contraindicated` lub alert **critical** | `HIGH_RISK` + istotne alerty expert |

Mapowanie: [`api/services/risk_levels.py`](../api/services/risk_levels.py).

---

## Sygnał decyzyjny per podejście (warstwa C)

| Podejście | `detected_high_risk = true` gdy… |
|-----------|----------------------------------|
| **expert** | `contraindicated` LUB alert severity `critical` / `high` |
| **genai** | `SAFETY_VERDICT: HIGH_RISK` (fallback: słowa kluczowe ryzyka) |
| **rag** | `SAFETY_VERDICT: HIGH_RISK` z kontekstem wytycznych (nie echo alertów expert) |

Szczegóły: [`study_example/METHODOLOGY.md`](METHODOLOGY.md).

---

## Czego system nie robi

- Nie mierzy QTc z EKG.
- Nie ocenia funkcji wątroby (ALT/AST).
- Nie przewiduje zgonu — porównanie z outcome to analiza retrospektywna.
- Nie ocenia **antykoagulacji** (DOAC, warfaryna, CHA₂DS₂-VASc) — poza scope antyarytmików.
- Nie liczy F1 / precision / recall względem złotego standardu (brak etykiety referencyjnej w MIMIC).
