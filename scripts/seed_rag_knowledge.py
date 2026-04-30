"""
Seed the RAG knowledge base from PDF/txt/md sources.

Usage:
    python scripts/seed_rag_knowledge.py [--sources .sources] [--out artifacts/rag_knowledge.json]
                                         [--strategy sliding_window] [--chunk-size 500] [--overlap 50]

The script:
1. Reads all .pdf / .txt / .md files under --sources
2. Chunks each document with HealthcareDocumentProcessor
3. Embeds every chunk with OpenAIEmbedder (text-embedding-3-small)
4. Saves the full knowledge base to --out as JSON (can be loaded at app startup)

The output JSON format is a list of serialised DocumentChunks:
[
  {
    "chunk_id": "...",
    "doc_id": "...",
    "chunk_index": 0,
    "content": "...",
    "metadata": {...},
    "embedding": [0.123, ...]   ← 1536-dim vector
  },
  ...
]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from uuid import uuid4

# ---------------------------------------------------------------------------
# Make sure the project root is on sys.path when called directly
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

from retrieved_augmentation.abstract import (
    ChunkingStrategy,
    Document,
    DocumentChunk,
)
from retrieved_augmentation.document_processor import HealthcareDocumentProcessor
from retrieved_augmentation.embedder import OpenAIEmbedder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategy map
# ---------------------------------------------------------------------------
_STRATEGY_MAP: dict[str, ChunkingStrategy] = {
    "sliding_window": ChunkingStrategy.SLIDING_WINDOW,
    "sentence": ChunkingStrategy.SENTENCE,
    "paragraph": ChunkingStrategy.PARAGRAPH,
}


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("pypdf is required for PDF extraction: pip install pypdf")

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: {suffix}")


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------

def seed(
    sources_dir: Path,
    out_path: Path,
    strategy: ChunkingStrategy,
    chunk_size: int,
    overlap: int,
) -> None:
    # Collect source files
    supported = {".pdf", ".txt", ".md"}
    files = sorted(
        p for p in sources_dir.rglob("*") if p.suffix.lower() in supported
    )
    if not files:
        log.warning("No .pdf / .txt / .md files found in %s — nothing to embed.", sources_dir)
        return

    log.info("Found %d source file(s) in %s", len(files), sources_dir)

    processor = HealthcareDocumentProcessor(
        default_chunk_size=chunk_size,
        default_overlap=overlap,
    )
    embedder = OpenAIEmbedder(model="text-embedding-3-small")

    all_chunks: list[DocumentChunk] = []

    for file_path in files:
        log.info("Processing: %s", file_path.name)
        try:
            text = _extract_text(file_path)
        except Exception as exc:
            log.warning("  Skipping %s — extraction failed: %s", file_path.name, exc)
            continue

        if not text.strip():
            log.warning("  Skipping %s — empty after extraction", file_path.name)
            continue

        doc = Document(
            content=text,
            metadata={
                "filename": file_path.name,
                "source_path": str(file_path.relative_to(sources_dir)),
                "doc_type": "guideline",
            },
            doc_type="guideline",
        )

        cleaned = processor.clean(doc.content)
        base_metadata = processor.extract_metadata(doc)
        doc_id = str(uuid4())

        text_chunks = processor.chunk(
            cleaned,
            strategy=strategy,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        if not text_chunks:
            log.warning("  Skipping %s — produced no chunks", file_path.name)
            continue

        chunks: list[DocumentChunk] = [
            DocumentChunk(
                content=chunk_text,
                metadata={**base_metadata, **doc.metadata},
                chunk_id=f"{doc_id}_chunk_{idx}",
                doc_id=doc_id,
                chunk_index=idx,
            )
            for idx, chunk_text in enumerate(text_chunks)
        ]

        log.info("  Embedding %d chunks…", len(chunks))
        texts_to_embed = [c.content for c in chunks]
        embeddings = embedder.embed_batch(texts_to_embed)

        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        all_chunks.extend(chunks)
        log.info("  Done — %d chunks added (running total: %d)", len(chunks), len(all_chunks))

    if not all_chunks:
        log.error("No chunks produced — knowledge base not written.")
        sys.exit(1)

    # Serialise
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "chunk_id": c.chunk_id,
            "doc_id": c.doc_id,
            "chunk_index": c.chunk_index,
            "content": c.content,
            "metadata": c.metadata,
            "embedding": c.embedding,
        }
        for c in all_chunks
    ]

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    log.info(
        "Knowledge base saved to %s  (%d chunks from %d file(s))",
        out_path,
        len(all_chunks),
        len(files),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the RAG knowledge base from PDF/txt/md source files."
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=_PROJECT_ROOT / ".sources",
        help="Directory containing source documents (default: .sources/)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_PROJECT_ROOT / "artifacts" / "rag_knowledge.json",
        help="Output path for the knowledge base JSON (default: artifacts/rag_knowledge.json)",
    )
    parser.add_argument(
        "--strategy",
        choices=list(_STRATEGY_MAP.keys()),
        default="sliding_window",
        help="Chunking strategy (default: sliding_window)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Target chunk size in characters (default: 500)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=50,
        help="Overlap between consecutive chunks for sliding_window (default: 50)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if not args.sources.is_dir():
        log.error("Sources directory does not exist: %s", args.sources)
        log.error("Create it and add your PDF/txt/md guidelines there.")
        sys.exit(1)

    seed(
        sources_dir=args.sources,
        out_path=args.out,
        strategy=_STRATEGY_MAP[args.strategy],
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
