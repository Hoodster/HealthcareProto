# Szablon ręcznej walidacji klinicznej (N=20–30)

Opcjonalna warstwa D — poza kodem. Wybierz wiersze z `artifacts/pilot_100.csv` z rozbieżnościami (`agreement` = partial/disagreement).

## Rubryka oceny (0–3)

| Ocena | Znaczenie |
|-------|-----------|
| 0 | Terapia antyarytmiczna **bezpieczna** — brak istotnych obaw |
| 1 | **Niskie** ryzyko — monitorowanie wystarczające |
| 2 | **Istotne** ryzyko — wymaga interwencji / modyfikacji leczenia |
| 3 | **Przeciwwskazane** / wysokie ryzyko natychmiastowe |

## Arkusz (skopiuj do Excel / Google Sheets)

| subject_id | hadm_id | expert_risk | llm_risk | rag_risk | ocena_ręczna_0_3 | zgadza_się_z | uzasadnienie (1–2 zdania) |
|------------|---------|-------------|----------|----------|------------------|--------------|---------------------------|
| | | | | | | expert / llm / rag / żaden | |

## Kryteria wyboru przypadków

1. Expert=2, LLM/RAG=0
2. RAG &gt; LLM (więcej flag / wyższy risk)
3. LLM=2 bez podstawy w expert/RAG
4. Expert=0, RAG=2 z cytatem wytycznych
5. Outcome=died bez concern u żadnego modelu
6. Outcome=survived z concern=2 u ≥2 modeli

## Raportowanie w pracy

> „Na podzbiorze N=__ przypadków z rozbieżnościami ocenionych przez [rola, np. farmaceuta/kardiolog w trakcie szkolenia], ręczna ocena wykazała…”

Nie traktuj tego jako gold standard — to **jakościowa** walidacja do dyskusji.
