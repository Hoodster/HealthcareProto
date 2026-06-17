"""MIMIC chartevents itemids and cohort helpers shared by import/export and clinical context."""

from __future__ import annotations

import csv
from pathlib import Path

# Known QT / QTc itemids in MIMIC-III d_items (carevue + metavision).
QTC_ITEMIDS: frozenset[int] = frozenset(
    {
        586,
        587,
        1742,
        1904,
        2421,
        2711,
        5978,
        6205,
        7571,
        224359,
    }
)

CARDIAC_ICD_EXACT: frozenset[str] = frozenset({"42731", "42732", "4271", "2768"})
CARDIAC_ICD_PREFIXES: tuple[str, ...] = ("426", "428")


def is_cardiac_icd9(code: str | None) -> bool:
    if not code:
        return False
    code = code.strip()
    if code in CARDIAC_ICD_EXACT:
        return True
    return any(code.startswith(prefix) for prefix in CARDIAC_ICD_PREFIXES)


def load_qtc_itemids_from_d_items(d_items_csv: Path) -> frozenset[int]:
    """Extend QTC_ITEMIDS with any d_items row whose label/abbreviation contains 'qt'."""
    if not d_items_csv.is_file():
        return QTC_ITEMIDS
    found: set[int] = set(QTC_ITEMIDS)
    with d_items_csv.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            label = (row.get("label") or "").lower()
            abbr = (row.get("abbreviation") or "").lower()
            if "qt" in label or "qt" in abbr:
                try:
                    found.add(int(row["itemid"]))
                except (TypeError, ValueError):
                    continue
    return frozenset(found)


def load_cardiac_admission_keys(data_dir: Path) -> set[tuple[int, int]]:
    """Return (subject_id, hadm_id) pairs for the cardiac cohort filter used in mimic_service."""
    diag_path = data_dir / "DIAGNOSES_ICD.csv"
    if not diag_path.is_file():
        return set()
    keys: set[tuple[int, int]] = set()
    with diag_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            code = row.get("icd9_code")
            if not is_cardiac_icd9(code):
                continue
            try:
                keys.add((int(row["subject_id"]), int(row["hadm_id"])))
            except (TypeError, ValueError, KeyError):
                continue
    return keys
