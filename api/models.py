from __future__ import annotations

from datetime import datetime as dt, timezone, date
from typing import Literal
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, default=lambda: str(uuid4()), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    api_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

class StaffProfile(Base):
    __tablename__ = "staff_profiles"

    id: Mapped[str] = mapped_column(String, default=lambda: str(uuid4()), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)
    
class Patient(Base):
    """Patient profile (§2 ust.1 - dokumentacja indywidualna)"""
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String, default=lambda: str(uuid4()), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
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

    __table_args__ = (
        UniqueConstraint("user_id", "first_name", "last_name", "dob", name="uq_patient_user_identity"),
    )
    

class PatientFile(Base):
    __tablename__ = "patient_files"

    id: Mapped[str] = mapped_column(String, default=lambda: str(uuid4()), primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

    patient: Mapped[Patient] = relationship(back_populates="files")

    __table_args__ = (
        Index('ix_patient_file_created', 'patient_id', 'created_at'),
    )

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
               'health_history']
class PatientHistoryEntry(Base):
    """Patient medical history (§2 ust.3 pkt 1,2 - historia zdrowia i choroby)"""
    __tablename__ = "patient_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    kind: Mapped[EntryKinds] = mapped_column(String(64), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[dt | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

    patient: Mapped[Patient] = relationship(back_populates="history_entries")

    __table_args__ = (
        Index('ix_patient_kind', 'patient_id', 'kind'),
        Index('ix_patient_occurred', 'patient_id', 'occurred_at'),
    )


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

    messages: Mapped[list["Message"]] = relationship(back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)
    sender_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chat: Mapped[Chat] = relationship(back_populates="messages")
    
class MedDocument(Base):
    """Secure medical documents (§1 ust.1, §1 ust.6 - dokumentacja elektroniczna)"""
    __tablename__ = "med_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    
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

    __table_args__ = (
        Index('ix_patient_doc_type', 'patient_id', 'document_type'),
        Index('ix_patient_doc_created', 'patient_id', 'created_at'),
    )
