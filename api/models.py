from __future__ import annotations

from datetime import datetime as dt, timezone, date
from typing import Literal
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base

APP_SCHEMA_NAME = "app"
MIMIC_SCHEMA_NAME = "mimiciii"

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'schema': APP_SCHEMA_NAME}

    id: Mapped[str] = mapped_column(String, default=lambda: str(uuid4()), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    api_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

class StaffProfile(Base):
    __tablename__ = "staff_profiles"
    __table_args__ = {'schema': APP_SCHEMA_NAME}

    id: Mapped[str] = mapped_column(String, default=lambda: str(uuid4()), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey(f"{APP_SCHEMA_NAME}.users.id"), index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

class Patient(Base):
    """Patient profile (§2 ust.1 - dokumentacja indywidualna)"""
    __tablename__ = "app_patients"
    __table_args__ = (
        UniqueConstraint("user_id", "first_name", "last_name", "dob", name="uq_patient_user_identity"),
        {'schema': APP_SCHEMA_NAME}
    )

    id: Mapped[str] = mapped_column(String, default=lambda: str(uuid4()), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey(f"{APP_SCHEMA_NAME}.users.id"), index=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

    files: Mapped[list["PatientFile"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    history_entries: Mapped[list["PatientHistoryEntry"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    med_documents: Mapped[list["MedDocument"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )

class PatientFile(Base):
    __tablename__ = "patient_files"
    __table_args__ = (
        Index('ix_patient_file_created', 'patient_id', 'created_at'),
        {'schema': APP_SCHEMA_NAME}
    )

    id: Mapped[str] = mapped_column(String, default=lambda: str(uuid4()), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey(f"{APP_SCHEMA_NAME}.app_patients.id"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

    patient: Mapped[Patient] = relationship(back_populates="files")

# Entry kinds for medical history (§2 ust.3, §2 ust.4)
EntryKindsEnhanced = Literal[
    # Clinical Documentation (§2 ust.3 - dokumentacja wewnętrzna)
    'diagnosis',                    # Rozpoznanie
    'symptom',                      # Objaw
    'episode_af',                   # Epizod migotania przedsionków
    'vital_signs',                  # Parametry życiowe (HR, BP, temp)

    # Risk Assessment
    'risk_score',                   # Skale ryzyka (CHA₂DS₂-VASc, HAS-BLED)

    # Diagnostics (§2 ust.3 pkt 20 - wyniki badań)
    'diagnostic_ecg',               # EKG
    'diagnostic_holter',            # Holter EKG
    'diagnostic_echo',              # Echokardiografia
    'diagnostic_imaging',           # Inne obrazowanie (CT, MRI, RTG)
    'lab_result',                   # Wyniki laboratoryjne
    'lab_inr',                      # INR (częste dla warfaryny)

    # Treatments & Medications
    'prescription',                 # Recepta/zlecenie leku
    'medication_change',            # Zmiana leczenia
    'anticoagulation',              # Leczenie przeciwzakrzepowe

    # Procedures (§2 ust.3 pkt 17,21 - procedury)
    'procedure_cardioversion',      # Kardiowersja
    'procedure_ablation',           # Ablacja
    'operation_protocol',           # Protokół operacyjny

    # Observations & Monitoring
    'observation',                  # Obserwacja pacjenta
    'followup',                     # Wizyta kontrolna

    # External Documentation (§2 ust.4 - dokumentacja zewnętrzna)
    'referral',                     # Skierowanie
    'discharge_summary',            # Karta informacyjna z leczenia

    # Adverse Events
    'adverse_event',                # Zdarzenie niepożądane
    'complication',                 # Powikłanie

    # Patient Education & Lifestyle
    'patient_education',            # Edukacja pacjenta
    'lifestyle',                    # Czynniki ryzyka/styl życia

    # Administrative (§2 ust.5 - wymogi administracyjne)
    'consent',                      # Zgoda
    'external_doc_issued',          # Wpis o wydaniu dok. zewnętrznej

    # General
    'health_history',               # Historia zdrowia
    'note',                         # Notatka ogólna
]

EntryKinds = Literal['prescription',
               'operation_protocol',
               'observation',
                'diagnosis',
               'health_history',
               'visit']
class PatientHistoryEntry(Base):
    """Patient medical history (§2 ust.3 pkt 1,2 - historia zdrowia i choroby)"""
    __tablename__ = "patient_history"
    __table_args__ = (
        Index('ix_patient_kind', 'patient_id', 'kind'),
        Index('ix_patient_occurred', 'patient_id', 'occurred_at'),
        {'schema': APP_SCHEMA_NAME}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey(f"{APP_SCHEMA_NAME}.app_patients.id"), index=True, nullable=False)
    kind: Mapped[EntryKinds] = mapped_column(String(64), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[dt | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

    patient: Mapped[Patient] = relationship(back_populates="history_entries")


class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = {'schema': APP_SCHEMA_NAME}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey(f"{APP_SCHEMA_NAME}.users.id"), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

    messages: Mapped[list["Message"]] = relationship(back_populates="chat", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {'schema': APP_SCHEMA_NAME}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey(f"{APP_SCHEMA_NAME}.chats.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)
    sender_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chat: Mapped[Chat] = relationship(back_populates="messages")

class MedDocument(Base):
    """Secure medical documents (§1 ust.1, §1 ust.6 - dokumentacja elektroniczna)"""
    __tablename__ = "med_documents"
    __table_args__ = (
        Index('ix_patient_doc_type', 'patient_id', 'document_type'),
        Index('ix_patient_doc_created', 'patient_id', 'created_at'),
        {'schema': APP_SCHEMA_NAME}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey(f"{APP_SCHEMA_NAME}.users.id"), index=True, nullable=False)
    patient_id: Mapped[str] = mapped_column(ForeignKey(f"{APP_SCHEMA_NAME}.app_patients.id"), index=True, nullable=False)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Store encrypted content or blob reference
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_blob_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Audit trail (§1 ust.6 pkt 3,4 - identyfikacja i timestamp)
    uploaded_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)
    modified_at: Mapped[dt | None] = mapped_column(DateTime, nullable=True)

    patient: Mapped[Patient] = relationship(back_populates="med_documents")

# ============================================================================
# MIMIC-III Database Models (Read-Only Research Data)
# ============================================================================
# These models map to the MIMIC-III research database tables.
# Schema: 'public' (default PostgreSQL schema for MIMIC-III)
# Do NOT modify these tables - they contain research data.

class MimicPatient(Base):
    """MIMIC-III Patients table (read-only)"""
    __tablename__ = "patients"
    __table_args__ = {'schema': MIMIC_SCHEMA_NAME}

    subject_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gender: Mapped[str | None] = mapped_column(String(1), nullable=True)
    dob: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    dod: Mapped[dt | None] = mapped_column(DateTime, nullable=True)  # Date of death
    dod_hosp: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    dod_ssn: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    expire_flag: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    admissions: Mapped[list["MimicAdmission"]] = relationship(back_populates="patient")
    icustays: Mapped[list["MimicICUStay"]] = relationship(back_populates="patient")
    diagnoses: Mapped[list["MimicDiagnosisICD"]] = relationship(back_populates="patient")


class MimicAdmission(Base):
    """MIMIC-III Admissions table (read-only)"""
    __tablename__ = "admissions"
    __table_args__ = {'schema': MIMIC_SCHEMA_NAME}

    hadm_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey(f"{MIMIC_SCHEMA_NAME}.patients.subject_id"), index=True, nullable=False)
    admittime: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    dischtime: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    deathtime: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    admission_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    admission_location: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discharge_location: Mapped[str | None] = mapped_column(String(50), nullable=True)
    insurance: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    religion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    marital_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String(200), nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hospital_expire_flag: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_chartevents_data: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    patient: Mapped[MimicPatient] = relationship(back_populates="admissions")
    icustays: Mapped[list[MimicICUStay]] = relationship(back_populates="admission")
    diagnoses: Mapped[list[MimicDiagnosisICD]] = relationship(back_populates="admission")


class MimicICUStay(Base):
    """MIMIC-III ICU Stays table (read-only)"""
    __tablename__ = "icustays"
    __table_args__ = {'schema': MIMIC_SCHEMA_NAME}

    icustay_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey(f"{MIMIC_SCHEMA_NAME}.patients.subject_id"), index=True, nullable=False)
    hadm_id: Mapped[int] = mapped_column(ForeignKey(f"{MIMIC_SCHEMA_NAME}.admissions.hadm_id"), index=True, nullable=True)
    intime: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    outtime: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    los: Mapped[float | None] = mapped_column(Integer, nullable=True)  # Length of stay
    first_careunit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_careunit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    first_wardid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_wardid: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    patient: Mapped[MimicPatient] = relationship(back_populates="icustays")
    admission: Mapped[MimicAdmission] = relationship(back_populates="icustays")


class MimicDiagnosisICD(Base):
    """MIMIC-III Diagnoses (ICD-9 codes) table (read-only)"""
    __tablename__ = "diagnoses_icd"
    __table_args__ = (
        Index('ix_mimic_diag_subject', 'subject_id'),
        Index('ix_mimic_diag_hadm', 'hadm_id'),
        Index('ix_mimic_diag_icd9', 'icd9_code'),
        {'schema': MIMIC_SCHEMA_NAME}
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey(f"{MIMIC_SCHEMA_NAME}.patients.subject_id"), index=True, nullable=False)
    hadm_id: Mapped[int] = mapped_column(ForeignKey(f"{MIMIC_SCHEMA_NAME}.admissions.hadm_id"), index=True, nullable=False)
    seq_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    icd9_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Relationships
    patient: Mapped[MimicPatient] = relationship(back_populates="diagnoses")
    admission: Mapped[MimicAdmission] = relationship(back_populates="diagnoses")
    icd_definition: Mapped["MimicICDDiagnosisDefinition"] = relationship(
        foreign_keys="MimicDiagnosisICD.icd9_code",
        primaryjoin="MimicDiagnosisICD.icd9_code == MimicICDDiagnosisDefinition.icd9_code",
        viewonly=True
    )


class MimicICDDiagnosisDefinition(Base):
    """MIMIC-III ICD-9 Diagnosis Definitions (read-only)"""
    __tablename__ = "d_icd_diagnoses"
    __table_args__ = {'schema': MIMIC_SCHEMA_NAME}

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    icd9_code: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    short_title: Mapped[str | None] = mapped_column(String(50), nullable=True)
    long_title: Mapped[str | None] = mapped_column(String(300), nullable=True)


class MimicPrescription(Base):
    """MIMIC-III Prescriptions table (read-only)"""
    __tablename__ = "prescriptions"
    __table_args__ = (
        Index('ix_mimic_rx_subject', 'subject_id'),
        Index('ix_mimic_rx_hadm', 'hadm_id'),
        {'schema': MIMIC_SCHEMA_NAME}
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey(f"{MIMIC_SCHEMA_NAME}.patients.subject_id"), index=True, nullable=False)
    hadm_id: Mapped[int] = mapped_column(ForeignKey(f"{MIMIC_SCHEMA_NAME}.admissions.hadm_id"), index=True, nullable=False)
    icustay_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    startdate: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    enddate: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    drug_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    drug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    drug_name_poe: Mapped[str | None] = mapped_column(String(100), nullable=True)
    drug_name_generic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    formulary_drug_cd: Mapped[str | None] = mapped_column(String(120), nullable=True)
    route: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dose_val_rx: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dose_unit_rx: Mapped[str | None] = mapped_column(String(120), nullable=True)
    form_val_disp: Mapped[str | None] = mapped_column(String(120), nullable=True)
    form_unit_disp: Mapped[str | None] = mapped_column(String(120), nullable=True)


class MimicLabEvent(Base):
    """MIMIC-III Lab Events table (read-only) - Warning: Large table"""
    __tablename__ = "labevents"
    __table_args__ = (
        Index('ix_mimic_lab_subject', 'subject_id'),
        Index('ix_mimic_lab_hadm', 'hadm_id'),
        Index('ix_mimic_lab_itemid', 'itemid'),
        {'schema': MIMIC_SCHEMA_NAME}
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey(f"{MIMIC_SCHEMA_NAME}.patients.subject_id"), index=True, nullable=False)
    hadm_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    itemid: Mapped[int] = mapped_column(ForeignKey(f"{MIMIC_SCHEMA_NAME}.d_labitems.itemid"), index=True, nullable=False)
    charttime: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    valuenum: Mapped[float | None] = mapped_column(Float, nullable=True)
    valueuom: Mapped[str | None] = mapped_column(String(20), nullable=True)
    flag: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationship
    lab_item: Mapped["MimicLabItem"] = relationship(back_populates="events")


class MimicLabItem(Base):
    """MIMIC-III Lab Item Definitions (read-only)"""
    __tablename__ = "d_labitems"
    __table_args__ = {'schema': MIMIC_SCHEMA_NAME}

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    itemid: Mapped[int] = mapped_column(Integer, index=True, nullable=False, unique=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fluid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    loinc_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationship
    events: Mapped[list[MimicLabEvent]] = relationship(back_populates="lab_item")
