"""Drug interaction service backed by the NLM RxNorm Interaction API (free, no auth)."""
from __future__ import annotations

import logging
from typing import Literal, Optional

import httpx

logger = logging.getLogger(__name__)

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"

# RxNorm search modes (search parameter):
#   0 – Exact:              atom must exactly match the name (case-insensitive)
#   1 – Normalized:         ignores word order, punctuation, salt forms, expands abbreviations
#   2 – Exact or Normalized: tries exact first, falls back to normalized
#   9 – Approximate:        fuzzy match, returns best-guess RxCUI(s)
RxNormSearchMode = Literal[0, 1, 2, 9]
_DEFAULT_SEARCH_MODE: RxNormSearchMode = 2  # exact-or-normalized is the most useful default

# In-process cache: (drug_name, search_mode) → rxcui string
_rxcui_cache: dict[tuple[str, int], str | None] = {}
# In-process cache: frozenset of rxcuis → interaction list
_interaction_cache: dict[frozenset, list[dict]] = {}


class DrugService:
    """Utilities for drug normalisation and interaction checking via RxNorm."""

    @staticmethod
    def get_rxcui(
        drug_name: str,
        search: RxNormSearchMode = _DEFAULT_SEARCH_MODE,
    ) -> Optional[str]:
        """Return the RxCUI (concept unique identifier) for a drug name, or None.

        Args:
            drug_name: The drug name to look up (any vocabulary in RxNorm).
            search:    Precision level for matching:
                         0 – Exact (case-insensitive atom match)
                         1 – Normalized (ignores order, punctuation, salts,
                                         expands abbreviations, e.g. "hctz" →
                                         "hydrochlorothiazide")
                         2 – Exact-or-Normalized (tries exact first, then
                                                   normalized; default)
                         9 – Approximate (fuzzy best-guess, ranked by quality)
        """
        key = drug_name.strip().lower()
        cache_key = (key, search)
        if cache_key in _rxcui_cache:
            return _rxcui_cache[cache_key]

        try:
            url = f"{RXNORM_BASE}/rxcui.json"
            resp = httpx.get(url, params={"name": key, "search": str(search)}, timeout=8.0)
            resp.raise_for_status()
            data = resp.json()
            rxcui = (
                data.get("idGroup", {})
                .get("rxnormId", [None])[0]
            )
            _rxcui_cache[cache_key] = rxcui
            return rxcui
        except Exception as exc:
            logger.warning("RxNorm rxcui lookup failed for '%s': %s", drug_name, exc)
            _rxcui_cache[cache_key] = None
            return None

    @staticmethod
    def check_interactions(
        medications: list[str],
        search: RxNormSearchMode = _DEFAULT_SEARCH_MODE,  # noqa: ARG004 – kept for API compatibility
    ) -> list[dict]:
        """
        Return a list of detected drug–drug interactions for the given medication list.

        Each item has keys: drug_1, drug_2, severity, description.

        Implemented via local cross-referencing against the same drug-category sets
        used by the expert system (QT_PROLONGING_DRUGS, CYP_INHIBITORS, BETA_BLOCKERS).
        The RxNorm /interaction/ REST endpoint was retired by NLM and returns 404.

        Args:
            medications: List of drug name strings.
            search:      Kept for signature compatibility; not used for local lookup.
        """
        from expert_system.rules.interaction_rules import (
            QT_PROLONGING_DRUGS,
            CYP_INHIBITORS,
            BETA_BLOCKERS,
        )
        from itertools import combinations

        if len(medications) < 2:
            return []

        drugs = [m.strip().lower() for m in medications]
        cache_key = frozenset(drugs)
        if cache_key in _interaction_cache:
            return _interaction_cache[cache_key]

        interactions: list[dict] = []

        # --- QT-prolonging drug pairs (additive torsade risk) --------------------
        qt_drugs = [d for d in drugs if d in QT_PROLONGING_DRUGS]
        for a, b in combinations(qt_drugs, 2):
            interactions.append({
                "drug_1": a,
                "drug_2": b,
                "severity": "high",
                "description": (
                    f"Both {a} and {b} prolong the QT interval. "
                    "Combination carries additive risk of torsade de pointes."
                ),
            })

        # --- CYP inhibitor affecting co-medications ------------------------------
        cyp_drugs = [d for d in drugs if d in CYP_INHIBITORS]
        non_cyp = [d for d in drugs if d not in CYP_INHIBITORS]
        for cyp, other in ((c, o) for c in cyp_drugs for o in non_cyp):
            interactions.append({
                "drug_1": cyp,
                "drug_2": other,
                "severity": "moderate",
                "description": (
                    f"{cyp} inhibits CYP enzymes and may increase plasma levels of {other}, "
                    "raising the risk of toxicity."
                ),
            })

        # --- Beta-blocker + antiarrhythmic (additive bradycardia) ----------------
        beta_drugs = [d for d in drugs if d in BETA_BLOCKERS]
        antiarrhythmics = [d for d in drugs if d in QT_PROLONGING_DRUGS and d not in BETA_BLOCKERS]
        paired: set[frozenset] = {frozenset([r["drug_1"], r["drug_2"]]) for r in interactions}
        for beta, aa in ((b, a) for b in beta_drugs for a in antiarrhythmics):
            pair_key = frozenset([beta, aa])
            if pair_key not in paired:
                interactions.append({
                    "drug_1": beta,
                    "drug_2": aa,
                    "severity": "moderate",
                    "description": (
                        f"Beta-blocker {beta} combined with antiarrhythmic {aa}: "
                        "additive risk of bradycardia and AV conduction delay."
                    ),
                })
                paired.add(pair_key)

        _interaction_cache[cache_key] = interactions
        return interactions

