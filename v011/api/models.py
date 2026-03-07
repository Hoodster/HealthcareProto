from __future__ import annotations

from datetime import datetime as dt, timezone, date
from typing import Literal
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from v011.api.db import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, default=lambda: str(uuid4()), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    api_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

class Patient(Base):
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

EntryKindsEnchanced = Literal[
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
    __tablename__ = "patient_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    kind: Mapped[EntryKinds] = mapped_column(String(64), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[dt | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

    patient: Mapped[Patient] = relationship(back_populates="history_entries")


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participants: Mapped[str] = mapped_column(String(255), nullable=False)  # comma-separated user IDs
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), index=True, nullable=True)
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

    chat: Mapped[Chat] = relationship(back_populates="messages")
    
class MedDocument(Base):
    __tablename__ = "med_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    
    filename: Mapped[str] = mapped_column(String(80), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. 'EKG', 'Echo', 'Lab Result'
    content_encrypted: Mapped[bytes] = mapped_column(Text, nullable=False)  # Store encrypted content
    created_at: Mapped[dt] = mapped_column(DateTime, default=lambda: dt.now(timezone.utc), nullable=False)

    patient: Mapped[Patient] = relationship(back_populates="med_documents")
