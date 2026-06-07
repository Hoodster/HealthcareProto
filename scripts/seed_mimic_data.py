"""
Seed mimiciii.* tables from MIMIC-III demo CSV files.

Targets the Alembic-defined schema (api.models.Mimic*), not the full
.create_tables.sql layout used by init_mimic_db.py.

Usage:
    export DB_URL="postgresql+psycopg2://..."
    python scripts/seed_mimic_data.py [--data-dir .sources/mimic] [--batch 1000]

Idempotent: truncates mimiciii tables (in FK-safe order) before import.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

from sqlalchemy import Float, Integer, create_engine, text
from sqlalchemy.orm import Session

from api.config import get_database_connection_url
from api.models import (
    MIMIC_SCHEMA_NAME,
    MimicAdmission,
    MimicDiagnosisICD,
    MimicICDDiagnosisDefinition,
    MimicICUStay,
    MimicLabEvent,
    MimicLabItem,
    MimicPatient,
    MimicPrescription,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# CSV filename → SQLAlchemy model, import order respects foreign keys
TABLES: list[tuple[str, type]] = [
    ("D_ICD_DIAGNOSES", MimicICDDiagnosisDefinition),
    ("D_LABITEMS", MimicLabItem),
    ("PATIENTS", MimicPatient),
    ("ADMISSIONS", MimicAdmission),
    ("ICUSTAYS", MimicICUStay),
    ("DIAGNOSES_ICD", MimicDiagnosisICD),
    ("LABEVENTS", MimicLabEvent),
    ("PRESCRIPTIONS", MimicPrescription),
]

TRUNCATE_ORDER = [model for _, model in reversed(TABLES)]

_PG_CONNECT_ARGS = {
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
    "connect_timeout": 60,
}


def _make_engine():
    return create_engine(
        get_database_connection_url(),
        future=True,
        pool_pre_ping=True,
        connect_args=_PG_CONNECT_ARGS,
    )


def _model_columns(model: type) -> set[str]:
    return {c.name for c in model.__table__.columns}


def _coerce_value(col, val: str):
    if isinstance(col.type, Integer):
        return int(round(float(val)))
    if isinstance(col.type, Float):
        return float(val)
    return val


def _row_from_csv(row: dict[str, str | None], model: type) -> dict:
    table = model.__table__
    out: dict = {}
    for key, val in row.items():
        col = table.columns.get(key)
        if col is None:
            continue
        if val in ("", None):
            out[key] = None
        else:
            try:
                out[key] = _coerce_value(col, val)
            except (TypeError, ValueError):
                out[key] = val
    return out


def _truncate_tables(session: Session) -> None:
    tables = ", ".join(
        f"{MIMIC_SCHEMA_NAME}.{m.__tablename__}" for m in TRUNCATE_ORDER
    )
    session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    session.commit()
    log.info("Truncated mimiciii tables")


def _csv_cell(val) -> str:
    if val is None:
        return ""
    return str(val)


def _import_csv(
    session: Session,
    csv_path: Path,
    model: type,
    batch_size: int,
) -> int:
    if not csv_path.is_file():
        log.warning("Missing CSV: %s — skipped", csv_path)
        return 0

    table = model.__table__
    col_names = [c.name for c in table.columns]
    col_sql = ", ".join(col_names)
    copy_sql = (
        f"COPY {MIMIC_SCHEMA_NAME}.{table.name} ({col_sql}) "
        f"FROM STDIN WITH (FORMAT CSV, NULL '')"
    )

    raw_conn = session.connection().connection
    inserted = 0
    chunk: list[list[str]] = []

    def _flush(cur) -> None:
        nonlocal inserted
        if not chunk:
            return
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerows(chunk)
        buf.seek(0)
        count = len(chunk)
        for attempt in range(1, 4):
            try:
                cur.copy_expert(copy_sql, buf)
                raw_conn.commit()
                inserted += count
                chunk.clear()
                return
            except Exception as exc:
                raw_conn.rollback()
                if attempt == 3:
                    raise
                log.warning("  COPY failed (attempt %d/3): %s — retrying", attempt, exc)
                time.sleep(5 * attempt)
                buf.seek(0)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cur = raw_conn.cursor()
        try:
            for raw in reader:
                row = _row_from_csv(raw, model)
                if not row:
                    continue
                chunk.append([_csv_cell(row.get(name)) for name in col_names])
                if len(chunk) >= batch_size:
                    _flush(cur)
            _flush(cur)
        finally:
            cur.close()

    log.info("  %s: %d rows", table.name, inserted)
    return inserted


def seed(data_dir: Path, batch_size: int, *, truncate: bool, only: list[str] | None) -> None:
    engine = _make_engine()
    if engine.url.drivername.startswith("sqlite"):
        log.error("DB_URL points to SQLite — set Azure PostgreSQL connection string")
        sys.exit(1)

    selected = TABLES
    if only:
        only_upper = {name.upper() for name in only}
        selected = [(n, m) for n, m in TABLES if n in only_upper]
        if not selected:
            log.error("No matching tables in --only: %s", only)
            sys.exit(1)

    log.info("Target database: %s", engine.url.database)
    log.info("Data directory: %s", data_dir)

    with Session(engine) as session:
        if truncate:
            if only:
                tables = ", ".join(
                    f"{MIMIC_SCHEMA_NAME}.{m.__tablename__}" for _, m in reversed(selected)
                )
                session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
                session.commit()
                log.info("Truncated selected mimiciii tables")
            else:
                _truncate_tables(session)

        total = 0
        for csv_name, model in selected:
            csv_path = data_dir / f"{csv_name}.csv"
            log.info("Importing %s …", csv_name)
            total += _import_csv(session, csv_path, model, batch_size)

    log.info("Done. Total rows imported: %d", total)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed mimiciii schema from MIMIC CSV files.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=_PROJECT_ROOT / ".sources" / "mimic",
        help="Directory containing MIMIC CSV files",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=5000,
        help="COPY batch size (default: 5000)",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Do not truncate tables before import",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="TABLE",
        help="Import only these CSV tables (e.g. LABEVENTS PRESCRIPTIONS)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    seed(
        data_dir=args.data_dir,
        batch_size=args.batch,
        truncate=not args.no_truncate,
        only=args.only,
    )
