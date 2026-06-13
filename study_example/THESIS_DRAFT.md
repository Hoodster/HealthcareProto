# Szkielet rozdziałów pracy magisterskiej

> Szkielet do uzupełnienia treścią z repozytorium HealthcareProto.  
> Kolejność pisania (profesor): rozdz. 3 → 4 → 5 → pilotaż → 6 → 1 → 7.

---

## 1. Opis problemu

**Temat:** Bezpieczeństwo leków przeciwarytmicznych u pacjentów z migotaniem przedsionków i innymi arytmiami w kontekście chorób układu krążenia.

**Problem badawczy:** Jak skutecznie i w sposób audytowalny oceniać ryzyko terapii antyarytmicznej — porównując reguły ekspertowe, LLM i RAG z wytycznymi?

**Hipoteza robocza:** RAG z wytycznymi klinicznymi dostarcza bardziej uzasadnione sygnały niż goły LLM, przy zachowaniu zgodności z systemem ekspertowym w oczywistych przeciwwskazaniach.

*(Uzupełnij literaturą i kontekstem klinicznym.)*

---

## 2. Źródła wiedzy

| Źródło | Rola w systemie |
|--------|-----------------|
| Wytyczne ESC/PDF | [`artifacts/rag_knowledge.json`](../artifacts/rag_knowledge.json) — indeks RAG |
| MIMIC-III Demo | Kohorta ~100 pac., hospitalizacje, leki, lab, outcome |
| DrugBank | [`app.drug_interactions`](../api/drug_db_store.py) — interakcje par leków |
| Reguły kliniczne | [`expert_system/rules/`](../expert_system/rules/) — progi eGFR, QT-proxy, CYP |

---

## 3. Definicja bezpieczeństwa

Pełna tabela parametrów: [`SAFETY_DEFINITION.md`](SAFETY_DEFINITION.md).

**Kluczowe ograniczenia (do wpisania w pracy):**

- System **nie** mierzy QTc z EKG — tylko proxy farmakologiczne (lista leków wydłużających QT).
- System **nie** ocenia funkcji wątroby.
- Brak labu kreatyniny → domyślne eGFR=90.
- Outcome (zgon) to warstwa A — punkt odniesienia, nie definicja „niebezpiecznej terapii”.

**Skala ryzyka pilotażu:** 0=safe, 1=warning, 2=unsafe — patrz SAFETY_DEFINITION §Skala ryzyka.

---

## 4. Architektura systemu

Pełny opis: [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

**Skrót:**

1. Dane wejściowe: MIMIC + opcjonalnie dokumenty pacjenta + wytyczne PDF.
2. Warstwa danych: PostgreSQL (`mimiciii` + `app`).
3. Moduł ekspercki: reguły statyczne, progi, flagi.
4. Moduł LLM: analiza bez retrievalu, werdykt `SAFETY_VERDICT`.
5. Moduł RAG: LLM + wytyczne + alerty expert.
6. Porównywarka: zgodność / rozbieżność, asocjacja z outcome.
7. Frontend (osobne repo): chat, comparison — [`FRONTEND_API.md`](../FRONTEND_API.md).
8. Azure: App Service, PostgreSQL, Key Vault, OpenAI; RAG → Azure AI Search (prod).

---

## 5. Metodyka eksperymentu

Szczegóły: [`METHODOLOGY.md`](METHODOLOGY.md).

### Kohorta

- Źródło: MIMIC-III Demo, filtr kardiologiczny (`get_heart_patients`).
- Opcjonalnie: `--antiarrhythmic-only` (ekspozycja na antyarytmik).
- **Faktyczne N:** **3** (MIMIC-III Demo: 58 pac. kardiologicznych, tylko 3 z ekspozycją antyarytmiczną przy `--antiarrhythmic-only`; docelowo N=100 wymaga pełnego MIMIC).

### Warianty modeli

| Wariant | Opis |
|---------|------|
| Expert | `RuleEngine` — deterministyczne reguły (wspólny dla obu providerów) |
| LLM (GenAI) | OpenAI **lub** Claude bez RAG (`--llm-provider`) |
| RAG | ten sam provider + retrieval wytycznych (embeddingi OpenAI, indeks wspólny) |

Expert liczony **raz** per pacjent (identyczny w obu przebiegach). RAG retrieval wspólny; zmienia się tylko model generujący werdykt.

### Metryki (bez F1)

| Eksperyment | OpenAI | Claude | Co mierzymy |
|-------------|--------|--------|-------------|
| **E1** Zgodność modeli | §6.1a | §6.1b | full / partial / disagreement %; średnie flagi |
| **E2** RAG vs LLM | §6.2a | §6.2b | rag-only, genai-only concern |
| **E3** Outcome vs sygnał | §6.3a | §6.3b | concern % w grupach outcome |
| **Porównanie providerów** | §6.5 | | Δ agreement z expertem; OpenAI≠Claude |

### Uruchomienie

```bash
python scripts/run_pilot.py --local --limit 100 --antiarrhythmic-only \
  --llm-provider openai -o artifacts/pilot_100_openai.csv

python scripts/run_pilot.py --local --limit 100 --antiarrhythmic-only \
  --llm-provider claude -o artifacts/pilot_100_claude.csv

python scripts/compare_pilot_providers.py \
  --openai artifacts/pilot_100_openai.csv \
  --claude artifacts/pilot_100_claude.csv \
  -o artifacts/pilot_comparison.md

python scripts/select_case_studies.py \
  --input artifacts/pilot_100_openai.csv \
  --claude-input artifacts/pilot_100_claude.csv \
  --output artifacts/case_studies.md
```

---

## 6. Wyniki pilotażowe (N=100, kohorta antyarytmiczna)

Po uruchomieniu pilotażu liczby trafiają do [`artifacts/pilot_comparison.md`](../artifacts/pilot_comparison.md).

**Uwaga kohorty:** w MIMIC-III Demo tylko **N=3** hospitalizacje spełniają `--antiarrhythmic-only` (58 pac. kardiologicznych łącznie). Przebieg Claude **nie zakończył się** — brak kredytów Anthropic API (`artifacts/pilot_claude.log`); po doładowaniu konta uruchom ponownie drugi przebieg.

### 6.1 E1 — zgodność expert / LLM / RAG

#### 6.1a OpenAI (gpt-4o)

| Metryka | Wartość |
|---------|---------|
| N pacjentów | 3 |
| Full agreement | 66.7 % |
| Partial agreement | 33.3 % |
| Disagreement | 0.0 % |
| Śr. flag expert / LLM / RAG | 6.67 / 4.67 / 3.33 |

#### 6.1b Claude (claude-sonnet-4-20250514)

| Metryka | Wartość |
|---------|---------|
| N pacjentów | 0 *(błąd API: brak kredytów Anthropic — do uzupełnienia)* |
| Full agreement | — |
| Partial agreement | — |
| Disagreement | — |
| Śr. flag expert / LLM / RAG | — |

### 6.2 E2 — RAG vs LLM

#### 6.2a OpenAI

| Metryka | Wartość |
|---------|---------|
| RAG-only concern | 0 |
| GenAI-only concern | 0 |

#### 6.2b Claude

| Metryka | Wartość |
|---------|---------|
| RAG-only concern | — *(brak przebiegu)* |
| GenAI-only concern | — |

### 6.3 E3 — outcome vs sygnał

#### 6.3a OpenAI — concern % (risk≥1)

| Grupa | Expert | LLM | RAG |
|-------|--------|-----|-----|
| Zmarli | 0.0 | 0.0 | 0.0 |
| Przeżywający | 100.0 | 100.0 | 100.0 |

*(W tej kohocie demo brak zgonów w szpitalu.)*

#### 6.3b Claude

| Grupa | Expert | LLM | RAG |
|-------|--------|-----|-----|
| Zmarli | — | — | — |
| Przeżywający | — | — | — |

### 6.4 Case studies

Pełna lista: [`artifacts/case_studies.md`](../artifacts/case_studies.md).

Wszystkie 3 przypadki mają ICU; expert tagi obejmują m.in. `SEVERE_RENAL_IMPAIRMENT`, `QT_INTERACTION`, `DIGOXIN_RENAL_AGE`. Jeden przypadek (10061) — partial agreement: expert=1 vs LLM/RAG=2.

### 6.5 Porównanie providerów LLM

| Metryka | OpenAI | Claude | Δ |
|---------|--------|--------|---|
| LLM risk = expert % | 66.7 | — | — |
| RAG risk = expert % | 66.7 | — | — |
| Wiersze LLM OpenAI≠Claude | — | | *(wymaga przebiegu Claude)* |

Źródło: [`artifacts/pilot_comparison.md`](../artifacts/pilot_comparison.md).

---

## 7. Dyskusja ograniczeń

### 7.1 Dane

- **Demo MIMIC (~100 pac.)** — mała kohorta; wnioski opisowe, nie populacyjne.
- **Brak QTc/EKG** — ocena QT oparta na liście leków, nie na pomiarze (`chartevents` nie importowany).
- **Brak oceny wątroby** — ALT/AST nie w pipeline.
- **Domyślne eGFR=90** gdy brak kreatyniny.

### 7.2 Metodologia

- Brak klinicznego gold standardu — API **nie zwraca** F1/precision/recall.
- Expert = operacjonalizacja wytycznych (`rule_tags` z odpalonych reguł); `reference_labels` = tylko warstwa A (outcome MIMIC).
- Zgon ≠ błąd leczenia — asocjacja retrospektywna, nie predykcja.
- **Antykoagulacja (DOAC, CHA₂DS₂-VASc)** — poza scope; opisana w dyskusji jako future work.

### 7.3 Techniczne

- **Koszty LLM** — pilotaż = 2× provider × (GenAI + RAG) na pacjenta + embeddingi RAG (OpenAI).
- **Reguły statyczne** — expert nie uczy się z danych.
- **RAG:** `RAG_BACKEND=memory` (dev) lub `azure_search` (prod).

### 7.4 Walidacja ręczna (opcjonalnie)

Szablon: [`MANUAL_VALIDATION_TEMPLATE.md`](MANUAL_VALIDATION_TEMPLATE.md).

---

## Załączniki w repozytorium

| Plik | Zawartość |
|------|-----------|
| `artifacts/pilot_100_openai.csv` | pilotaż OpenAI |
| `artifacts/pilot_100_claude.csv` | pilotaż Claude |
| `artifacts/pilot_comparison.md` | E1–E3 × provider |
| `artifacts/case_studies.md` | studia przypadków |
| `artifacts/safety.md` | raport comparison (Markdown) |
