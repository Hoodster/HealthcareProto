from __future__ import annotations
import io
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import get_current_user, HPCurrentUser, HPDbSession
from api.db import get_db_session
from api.models import MedDocument, User
from api.services.patient_service import PatientService
from api.services.document_processing_service import PatientDocumentProcessor
from api.rag_store import index_patient_document
from models.schemas.patient_schema import DocumentProcessOut, PatientHistoryOut
from datetime import datetime


router = APIRouter(prefix="/docs", tags=["documentation"])


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def _extract_text_from_upload(file: UploadFile) -> str:
    filename = file.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    raw = file.file.read()

    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise HTTPException(status_code=501, detail="pypdf not installed — PDF support unavailable")
        reader = PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(p for p in pages if p.strip())
    elif ext in {".txt", ".md", ""}:
        text = raw.decode("utf-8", errors="replace")
    else:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}",
        )

    if not text.strip():
        raise HTTPException(status_code=422, detail="File contains no extractable text")

    return text


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DocumentUploadOut(BaseModel):
    doc_id: int
    filename: str
    document_type: str
    patient_id: str | None = None
    char_count: int
    history_entries_created: int = 0
    rag_chunks_indexed: int = 0


class PatientDocumentOut(BaseModel):
    doc_id: int
    filename: str
    patient_id: str
    char_count: int
    created_at: datetime
    uploaded_by: str

    model_config = {"from_attributes": True}


ChunkingStrategyParam = Literal["sliding_window", "sentence", "paragraph"]


class GuidelineChunkOut(BaseModel):
    chunk_id: str
    chunk_index: int
    content: str


class GuidelineEmbedOut(BaseModel):
    filename: str
    doc_type: str
    strategy: str
    chunk_size: int
    overlap: int
    total_chunks: int
    chunks: list[GuidelineChunkOut]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", dependencies=[Depends(get_current_user)])
def upload_document(
    file: UploadFile,
    user: HPCurrentUser,
    db: HPDbSession,
    document_type: Literal["patient_docfile", "guideline"] = Query(..., description="Type of document being uploaded"),
    patient_id: str | None = Query(default=None, description="Required when document_type=patient_docfile"),
    # Guideline chunking options (ignored for patient_docfile)
    strategy: ChunkingStrategyParam = Query("sliding_window", description="Chunking strategy: sliding_window | sentence | paragraph"),
    chunk_size: int = Query(default=500, ge=100, le=4000, description="Target chunk size in characters"),
    overlap: int = Query(default=50, ge=0, le=500, description="Overlap between consecutive chunks (sliding_window only)"),
    update_history: bool = Query(
        default=True,
        description="Extract structured history entries into patient_history",
    ),
    index_rag: bool = Query(
        default=True,
        description="Chunk and index document for patient-specific RAG retrieval",
    ),
    replace_history_from_doc: bool = Query(
        default=False,
        description="When re-processing, remove prior entries tagged with this document id",
    ),
):
    """
    Upload a document (.pdf / .txt / .md).

    - **patient_docfile**: stores text in `med_documents`, indexes for RAG, and by default
      updates `patient_history` (diagnoses, labs, medications).
    - **guideline**: chunks the text (sliding window) and returns the chunk list.
      No DB write — use the chunks to seed a vector store.
    """
    text = _extract_text_from_upload(file)

    if document_type == "patient_docfile":
        if not patient_id:
            raise HTTPException(status_code=422, detail="patient_id is required for patient_docfile uploads")

        # Validate patient exists (raises 404 if not)
        PatientService.get_by_id(db, patient_id)

        # Only the patient themselves or staff may upload
        patient = PatientService.get_by_id(db, patient_id)
        if not user.staff and patient.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to upload documents for this patient")

        doc = MedDocument(
            user_id=user.id,
            patient_id=patient_id,
            filename=file.filename or "upload",
            document_type="patient_docfile",
            content_text=text,
            uploaded_by=user.full_name,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        history_entries_created = 0
        if update_history:
            result = PatientDocumentProcessor.process_med_document(
                db,
                doc.id,
                user,
                replace_existing_from_doc=replace_history_from_doc,
            )
            history_entries_created = result.entries_created

        rag_chunks_indexed = 0
        if index_rag:
            rag_chunks_indexed = index_patient_document(
                text,
                patient_id=patient_id,
                med_doc_id=doc.id,
                filename=doc.filename,
            )

        return DocumentUploadOut(
            doc_id=doc.id,
            filename=doc.filename,
            document_type=doc.document_type,
            patient_id=doc.patient_id,
            char_count=len(text),
            history_entries_created=history_entries_created,
            rag_chunks_indexed=rag_chunks_indexed,
        )

    # document_type == "guideline"
    from uuid import uuid4
    from retrieved_augmentation.abstract import Document, DocumentChunk, ChunkingStrategy
    from retrieved_augmentation.document_processor import HealthcareDocumentProcessor

    _STRATEGY_MAP: dict[str, ChunkingStrategy] = {
        "sliding_window": ChunkingStrategy.SLIDING_WINDOW,
        "sentence": ChunkingStrategy.SENTENCE,
        "paragraph": ChunkingStrategy.PARAGRAPH,
    }
    chosen_strategy = _STRATEGY_MAP[strategy]

    processor = HealthcareDocumentProcessor(
        default_chunk_size=chunk_size,
        default_overlap=overlap,
    )
    doc = Document(
        content=text,
        metadata={"filename": file.filename, "doc_type": "guideline"},
        doc_type="guideline",
    )

    # Clean text then chunk with the requested strategy
    cleaned = processor.clean(doc.content)
    base_metadata = processor.extract_metadata(doc)
    doc_id = str(uuid4())
    text_chunks = processor.chunk(cleaned, strategy=chosen_strategy, chunk_size=chunk_size, overlap=overlap)

    if not text_chunks:
        raise HTTPException(status_code=422, detail="Document produced no chunks after processing")

    chunks = [
        DocumentChunk(
            content=chunk_text,
            metadata={**base_metadata, **doc.metadata},
            chunk_id=f"{doc_id}_chunk_{idx}",
            doc_id=doc_id,
            chunk_index=idx,
        )
        for idx, chunk_text in enumerate(text_chunks)
    ]

    return GuidelineEmbedOut(
        filename=file.filename or "",
        doc_type="guideline",
        strategy=strategy,
        chunk_size=chunk_size,
        overlap=overlap,
        total_chunks=len(chunks),
        chunks=[
            GuidelineChunkOut(
                chunk_id=c.chunk_id,
                chunk_index=c.chunk_index,
                content=c.content,
            )
            for c in chunks
        ],
    )


def _authorize_patient_docs(patient_id: str, user: User, db: Session) -> None:
    patient = PatientService.get_by_id(db, patient_id)
    if not user.staff and patient.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access documents for this patient")


@router.get("/patient/{patient_id}", response_model=list[PatientDocumentOut])
def list_patient_documents(
    patient_id: str,
    user: HPCurrentUser,
    db: HPDbSession,
):
    """List uploaded documents for a patient."""
    _authorize_patient_docs(patient_id, user, db)
    stmt = (
        select(MedDocument)
        .where(
            MedDocument.patient_id == patient_id,
            MedDocument.document_type == "patient_docfile",
        )
        .order_by(MedDocument.created_at.desc())
    )
    docs = list(db.execute(stmt).scalars().all())
    return [
        PatientDocumentOut(
            doc_id=d.id,
            filename=d.filename,
            patient_id=d.patient_id,
            char_count=len(d.content_text or ""),
            created_at=d.created_at,
            uploaded_by=d.uploaded_by,
        )
        for d in docs
    ]


@router.get("/{doc_id}", response_model=PatientDocumentOut)
def get_patient_document(
    doc_id: int,
    user: HPCurrentUser,
    db: HPDbSession,
):
    """Get metadata for an uploaded patient document."""
    doc = db.get(MedDocument, doc_id)
    if doc is None or doc.document_type != "patient_docfile":
        raise HTTPException(status_code=404, detail="Document not found")
    _authorize_patient_docs(doc.patient_id, user, db)
    return PatientDocumentOut(
        doc_id=doc.id,
        filename=doc.filename,
        patient_id=doc.patient_id,
        char_count=len(doc.content_text or ""),
        created_at=doc.created_at,
        uploaded_by=doc.uploaded_by,
    )


@router.post("/{doc_id}/process-history", response_model=DocumentProcessOut)
def process_document_history(
    doc_id: int,
    user: HPCurrentUser,
    db: HPDbSession,
    replace_history_from_doc: bool = Query(
        default=False,
        description="Remove prior history entries extracted from this document before re-processing",
    ),
    reindex_rag: bool = Query(default=True, description="Re-index document chunks for RAG"),
):
    """
    Extract structured clinical entries from an uploaded patient document
    and append them to `patient_history`. Optionally re-index for RAG.
    """
    doc = db.get(MedDocument, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    result = PatientDocumentProcessor.process_med_document(
        db,
        doc_id,
        user,
        replace_existing_from_doc=replace_history_from_doc,
    )
    if reindex_rag and doc.content_text:
        index_patient_document(
            doc.content_text,
            patient_id=doc.patient_id,
            med_doc_id=doc.id,
            filename=doc.filename,
        )
    history = PatientService.list_history(db, result.patient_id)
    created = [entry for entry in history if entry.id in result.history_ids]
    return DocumentProcessOut(
        doc_id=result.doc_id,
        patient_id=result.patient_id,
        filename=result.filename,
        entries_created=result.entries_created,
        entries=[PatientHistoryOut.model_validate(e) for e in created],
    )
