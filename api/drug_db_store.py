"""
Drug interaction store — loaded once at application startup.

Queries app.drugs and app.drug_interactions from the database and builds
an in-memory lookup used by the expert system rule engine.

Usage:
    from api.drug_db_store import init_drug_db_store, get_drug_interactions

    # at startup:
    init_drug_db_store()

    # at rule evaluation time:
    interactions = get_drug_interactions(["amiodarone", "metoprolol"])
    # → list of (drug_a_name, drug_b_name, description)
"""

from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

# name (lowercase, stripped) → drugbank_id
_name_to_id: dict[str, str] = {}

# frozenset({drug_a_id, drug_b_id}) → description
_interaction_map: dict[frozenset, str] = {}

_initialized = False


def _normalize(name: str) -> str:
    """Lowercase + strip common suffixes/whitespace for fuzzy matching."""
    name = name.lower().strip()
    # remove trailing dose/form noise like "10mg", "oral", "tablet"
    name = re.sub(r"\s+\d[\d.]*\s*(mg|mcg|g|ml|iu|units?).*$", "", name)
    name = re.sub(r"\s+(tablet|capsule|oral|injection|solution|hcl|hydrochloride).*$", "", name)
    return name.strip()


def init_drug_db_store() -> None:
    """
    Load all drugs and interactions from the database into memory.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _name_to_id, _interaction_map, _initialized

    if _initialized:
        return

    try:
        from api.db import SessionLocal
        from api.models import Drug, DrugInteraction
        from sqlalchemy import select

        db = SessionLocal()
        try:
            # Load drugs: name → drugbank_id
            drugs = db.execute(select(Drug)).scalars().all()
            name_map: dict[str, str] = {}
            for drug in drugs:
                name_map[_normalize(drug.name)] = drug.drugbank_id
            _name_to_id = name_map

            # Load interactions: frozenset({a_id, b_id}) → description
            interactions = db.execute(select(DrugInteraction)).scalars().all()
            imap: dict[frozenset, str] = {}
            for inter in interactions:
                key = frozenset({inter.drug_a_id, inter.drug_b_id})
                imap[key] = inter.description or ""
            _interaction_map = imap

        finally:
            db.close()

        _initialized = True
        log.info(
            "Drug DB store loaded: %d drugs, %d interaction pairs.",
            len(_name_to_id),
            len(_interaction_map),
        )

    except Exception as exc:
        log.warning("Drug DB store init failed (%s) — DB drug interactions disabled.", exc)


def get_drug_interactions(
    medications: list[str],
) -> list[tuple[str, str, str]]:
    """
    Return all known interactions between the given medications.

    Args:
        medications: List of drug names (generic, any case/format).

    Returns:
        List of (drug_a_name, drug_b_name, description) tuples for every
        pair of patient medications that has an entry in drug_interactions.
        Empty list when the store is not loaded or no interactions found.
    """
    if not _initialized or not _name_to_id or not _interaction_map:
        return []

    # Build normalized name → original name + id mapping for patient meds
    patient_meds: list[tuple[str, str]] = []  # (normalized_name, drugbank_id)
    norm_to_original: dict[str, str] = {}
    for med in medications:
        norm = _normalize(med)
        dbid = _name_to_id.get(norm)
        if dbid:
            patient_meds.append((norm, dbid))
            norm_to_original[norm] = med

    if len(patient_meds) < 2:
        return []

    results: list[tuple[str, str, str]] = []
    seen: set[frozenset] = set()

    for i, (name_a, id_a) in enumerate(patient_meds):
        for name_b, id_b in patient_meds[i + 1:]:
            key = frozenset({id_a, id_b})
            if key in seen:
                continue
            seen.add(key)
            if key in _interaction_map:
                results.append((
                    norm_to_original[name_a],
                    norm_to_original[name_b],
                    _interaction_map[key],
                ))

    return results


def is_initialized() -> bool:
    return _initialized
