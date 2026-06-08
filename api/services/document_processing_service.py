"""Extract structured patient history entries from uploaded clinical documents."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, get_args

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.constant import EntryKindsEnhanced
from api.models import MedDocument, PatientHistoryEntry, User
from api.services.ai_service import AIModelService
from api.services.patient_service import PatientService

log = logging.getLogger(__name__)

_MAX_DOCUMENT_CHARS = 14_000
_VALID_KINDS = set(get_args(EntryKindsEnhanced))

_EXTRACTION_PROMPT = """
Extract structured clinical history entries from a patient document.

Return ONLY valid JSON with this shape:
{
  "entries": [
    {
      "kind": "<one of the allowed kinds>",
      "note": "<concise clinical note>",
      "occurred_at": "<ISO-8601 datetime or null>"
    }
  ]
}

Allowed kinds:
diagnosis, symptom, episode_af, vital_signs, risk_score,
diagnostic_ecg, diagnostic_holter, diagnostic_echo, diagnostic_imaging,
lab_result, lab_inr, prescription, medication_change, anticoagulation,
procedure_cardioversion, procedure_ablation, operation_protocol,
observation, followup, referral, discharge_summary, adverse_event,
complication, patient_education, lifestyle, consent, external_doc_issued,
health_history, note

Formatting rules for notes (important — downstream parsing depends on this):
- lab_result: include numeric values as "eGFR=45" when present
- prescription / medication_change / anticoagulation: start with generic drug name, e.g. "metoprolol 50 mg daily"
- diagnosis / symptom / episode_af / health_history: plain clinical description

Rules:
- Extract only facts explicitly stated in the document
- Do not invent diagnoses, lab values, medications, or dates
- Prefer several specific entries over one long summary
- Use null for occurred_at when the document has no date for an item
- If nothing clinical can be extracted, return {"entries": []}
"""


class ExtractedHistoryEntry(BaseModel):
    kind: str
    note: str
    occurred_at: datetime | None = None


class DocumentProcessResult(BaseModel):
    doc_id: int
    patient_id: str
    filename: str
    entries_created: int
    entries: list[ExtractedHistoryEntry] = Field(default_factory=list)
    history_ids: list[int] = Field(default_factory=list)


class PatientDocumentProcessor:
    @staticmethod
    def _authorize_document_access(db: Session, doc: MedDocument, user: User) -> None:
        patient = PatientService.get_by_id(db, doc.patient_id)
        if not user.staff and patient.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to process documents for this patient")

    @staticmethod
    def _normalize_text(text: str, filename: str) -> str:
        cleaned = text.strip()
        if len(cleaned) <= _MAX_DOCUMENT_CHARS:
            return cleaned
        log.warning(
            "Document %s truncated from %d to %d characters for extraction",
            filename,
            len(cleaned),
            _MAX_DOCUMENT_CHARS,
        )
        return cleaned[:_MAX_DOCUMENT_CHARS]

    @staticmethod
    def extract_entries(text: str, filename: str) -> list[ExtractedHistoryEntry]:
        """Use LLM to extract structured history entries from document text."""
        normalized = PatientDocumentProcessor._normalize_text(text, filename)
        if not normalized:
            return []

        ai = AIModelService()
        prompt = (
            f"{_EXTRACTION_PROMPT}\n\n"
            f"Document filename: {filename}\n\n"
            f"--- DOCUMENT TEXT ---\n{normalized}\n--- END ---"
        )

        raw = ai.chat(prompt)
        payload = PatientDocumentProcessor._parse_json_payload(raw)
        entries_raw = payload.get("entries", [])
        if not isinstance(entries_raw, list):
            raise HTTPException(status_code=502, detail="Invalid extraction response from AI")

        entries: list[ExtractedHistoryEntry] = []
        for item in entries_raw:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind", "")).strip()
            note = str(item.get("note", "")).strip()
            if not kind or not note:
                continue
            if kind not in _VALID_KINDS:
                kind = "note"
            occurred_at = PatientDocumentProcessor._parse_occurred_at(item.get("occurred_at"))
            entries.append(
                ExtractedHistoryEntry(kind=kind, note=note, occurred_at=occurred_at)
            )
        return entries

    @staticmethod
    def _parse_json_payload(raw: str) -> dict[str, Any]:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise HTTPException(status_code=502, detail="AI did not return valid JSON") from None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=502, detail="AI did not return valid JSON") from exc

    @staticmethod
    def _parse_occurred_at(value: Any) -> datetime | None:
        if value in (None, "", "null"):
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _format_note(doc: MedDocument, note: str) -> str:
        return f"[doc:{doc.id}] {note}"

    @staticmethod
    def process_med_document(
        db: Session,
        doc_id: int,
        user: User,
        *,
        replace_existing_from_doc: bool = False,
    ) -> DocumentProcessResult:
        """
        Extract history entries from a stored MedDocument and persist them.

        When replace_existing_from_doc=True, removes prior entries tagged with [doc:{id}].
        """
        doc = db.get(MedDocument, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if doc.document_type != "patient_docfile":
            raise HTTPException(status_code=422, detail="Only patient_docfile documents can update history")
        if not doc.content_text or not doc.content_text.strip():
            raise HTTPException(status_code=422, detail="Document has no extractable text")

        PatientDocumentProcessor._authorize_document_access(db, doc, user)

        if replace_existing_from_doc:
            PatientDocumentProcessor._delete_entries_for_doc(db, doc.patient_id, doc.id)

        extracted = PatientDocumentProcessor.extract_entries(doc.content_text, doc.filename)
        created: list[PatientHistoryEntry] = []
        history_ids: list[int] = []
        for item in extracted:
            entry = PatientService.add_history_record(
                db,
                doc.patient_id,
                item.kind,
                PatientDocumentProcessor._format_note(doc, item.note),
                item.occurred_at,
            )
            created.append(entry)
            history_ids.append(entry.id)

        return DocumentProcessResult(
            doc_id=doc.id,
            patient_id=doc.patient_id,
            filename=doc.filename,
            entries_created=len(created),
            entries=extracted,
            history_ids=history_ids,
        )

    @staticmethod
    def _delete_entries_for_doc(db: Session, patient_id: str, doc_id: int) -> None:
        prefix = f"[doc:{doc_id}]"
        stmt = select(PatientHistoryEntry).where(
            PatientHistoryEntry.patient_id == patient_id,
            PatientHistoryEntry.note.like(f"{prefix}%"),
        )
        for entry in db.execute(stmt).scalars().all():
            db.delete(entry)
        db.commit()
