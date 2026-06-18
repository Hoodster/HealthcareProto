"""Tests for chartevents export and revised expert rules."""

from __future__ import annotations

from pathlib import Path

from expert_system import RuleEngine, PatientContext
from expert_system.guideline_checks import (
    check_cyp_inhibitor,
    check_dofetilide_renal_contraindication,
    check_dronedarone_permanent_af,
    check_sotalol_renal_contraindication,
    check_sotalol_qt_contraindication,
    cyp_inhibitor_pairs,
)
from api.mimic_chart_constants import is_cardiac_icd9, load_cardiac_admission_keys


def test_is_cardiac_icd9():
    assert is_cardiac_icd9("42731")
    assert is_cardiac_icd9("4280")
    assert not is_cardiac_icd9("4019")


def test_sotalol_renal_threshold():
    assert check_sotalol_renal_contraindication(PatientContext(egfr=35, medications=["sotalol"]))
    assert not check_sotalol_renal_contraindication(PatientContext(egfr=45, medications=["sotalol"]))


def test_dofetilide_renal_threshold():
    assert check_dofetilide_renal_contraindication(PatientContext(egfr=15, medications=["dofetilide"]))
    assert not check_dofetilide_renal_contraindication(PatientContext(egfr=25, medications=["dofetilide"]))


def test_cyp_inhibitor_requires_pair():
    assert check_cyp_inhibitor(
        PatientContext(egfr=90, medications=["ketoconazole", "dronedarone"])
    )
    assert not check_cyp_inhibitor(
        PatientContext(egfr=90, medications=["ketoconazole", "metoprolol"])
    )
    pairs = cyp_inhibitor_pairs(
        PatientContext(egfr=90, medications=["clarithromycin", "amiodarone"])
    )
    assert ("clarithromycin", "amiodarone") in pairs


def test_dronedarone_permanent_af_proxy():
    assert check_dronedarone_permanent_af(
        PatientContext(egfr=90, medications=["dronedarone"], conditions=["atrial fibrillation"])
    )


def test_sotalol_qtc_rule():
    assert check_sotalol_qt_contraindication(
        PatientContext(egfr=90, medications=["sotalol"], qtc=460)
    )
    engine = RuleEngine()
    patient = PatientContext(egfr=90, medications=["sotalol"], qtc=460)
    decision = engine.evaluate(patient)
    assert "SotalolQTContraindicationRule" in decision.triggered_rules
    assert decision.contraindicated


def test_export_chartevents_script(tmp_path):
    from scripts.export_chartevents import export_chartevents

    data_dir = Path(__file__).resolve().parent.parent / ".sources" / "mimic"
    counts = export_chartevents(data_dir, tmp_path)
    assert (tmp_path / "chartevents_cardiac.csv").is_file()
    assert counts["cardiac"] > 0
