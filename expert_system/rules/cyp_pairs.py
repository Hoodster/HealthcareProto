"""CYP3A / P-gp inhibitor and inducer pairs (inhibitor/inducer drug ↔ affected antiarrhythmic)."""

from __future__ import annotations

# Each entry: (modifier drugs, affected antiarrhythmic substrates)
CYP3A_INHIBITOR_PAIRS: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (
        frozenset({"ketoconazole", "itraconazole", "clarithromycin", "erythromycin"}),
        frozenset({"dronedarone", "amiodarone", "dofetilide", "sotalol"}),
    ),
    (
        frozenset({"diltiazem", "verapamil"}),
        frozenset({"dronedarone", "amiodarone"}),
    ),
    (
        frozenset({"fluconazole"}),
        frozenset({"dronedarone", "amiodarone", "sotalol"}),
    ),
    (
        frozenset({"ritonavir"}),
        frozenset({"dronedarone", "amiodarone", "dofetilide"}),
    ),
    (
        frozenset({"fluoxetine", "paroxetine"}),
        frozenset({"flecainide", "propafenone"}),
    ),
)

CYP3A_INDUCER_PAIRS: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (
        frozenset({"rifampin", "rifampicin", "carbamazepine", "phenobarbital", "phenytoin"}),
        frozenset({"dronedarone", "amiodarone", "dofetilide"}),
    ),
    (
        frozenset({"st john's wort", "st johns wort"}),
        frozenset({"dronedarone", "amiodarone"}),
    ),
)


def matched_cyp_inhibitor_pairs(drugs: set[str]) -> list[tuple[str, str]]:
    """Return (inhibitor, substrate) pairs present in the patient's medication list."""
    hits: list[tuple[str, str]] = []
    for modifiers, substrates in CYP3A_INHIBITOR_PAIRS:
        for mod in sorted(drugs & modifiers):
            for sub in sorted(drugs & substrates):
                if mod != sub:
                    hits.append((mod, sub))
    return hits


def matched_cyp_inducer_pairs(drugs: set[str]) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for modifiers, substrates in CYP3A_INDUCER_PAIRS:
        for mod in sorted(drugs & modifiers):
            for sub in sorted(drugs & substrates):
                if mod != sub:
                    hits.append((mod, sub))
    return hits
