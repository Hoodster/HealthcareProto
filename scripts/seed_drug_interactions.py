"""
Seed app.drugs and app.drug_interactions from DrugBank XML.

Usage:
    python scripts/seed_drug_interactions.py [--xml .sources/drugbank.xml] [--batch 500]

The script is idempotent: it uses INSERT … ON CONFLICT DO NOTHING so it can be
re-run safely.  Run *after* the Alembic migration a3f1c9e7d502_drug_tables.py.

Steps:
  1. Stream-parse drugbank.xml with iterparse (memory-efficient for large files)
  2. Collect all <drug> entries → app.drugs
  3. Collect all <drug-interaction> pairs → app.drug_interactions
     (only records where BOTH sides already exist in app.drugs)
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from api.config import get_database_connection_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

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

NS = "http://www.drugbank.ca"


def _tag(local: str) -> str:
    return f"{{{NS}}}{local}"

def _parse_drugs(xml_path: Path) -> tuple[dict[str, dict], list[dict]]:
    """
    Stream-parse drugbank.xml.

    Returns:
        drugs      – {drugbank_id: {drugbank_id, name, description}}
        raw_interactions – [{drug_a_id, drug_b_id, description}]
            drug_b_id here is the *raw* DrugBank ID from the interaction element;
            the caller is responsible for filtering to only known drugs.
    """
    drugs: dict[str, dict] = {}
    raw_interactions: list[dict] = []

    context = ET.iterparse(str(xml_path), events=("start", "end"))
    current_drug_id: str | None = None
    current_drug_name: str | None = None
    current_drug_desc: str | None = None
    in_top_drug = False
    depth = 0

    for event, elem in context:
        local = elem.tag.replace(f"{{{NS}}}", "")

        if event == "start":
            if local == "drug":
                depth += 1
                if depth == 1:
                    in_top_drug = True
                    current_drug_id = None
                    current_drug_name = None
                    current_drug_desc = None

        elif event == "end":
            if not in_top_drug:
                elem.clear()
                continue

            if local == "drug":
                depth -= 1
                if depth == 0:
                    # Top-level drug element closed
                    if current_drug_id and current_drug_name:
                        drugs[current_drug_id] = {
                            "drugbank_id": current_drug_id,
                            "name": current_drug_name,
                            "description": current_drug_desc,
                        }

                        # Harvest interactions from the parsed subtree
                        drug_interactions_el = elem.find(_tag("drug-interactions"))
                        if drug_interactions_el is not None:
                            for di in drug_interactions_el.findall(_tag("drug-interaction")):
                                b_id_el = di.find(_tag("drugbank-id"))
                                desc_el = di.find(_tag("description"))
                                if b_id_el is not None and b_id_el.text:
                                    raw_interactions.append(
                                        {
                                            "drug_a_id": current_drug_id,
                                            "drug_b_id": b_id_el.text.strip(),
                                            "description": (desc_el.text or "").strip() or None
                                            if desc_el is not None
                                            else None,
                                        }
                                    )

                    in_top_drug = False
                    elem.clear()

            elif depth == 1:
                # Direct children of a top-level <drug>
                if local == "drugbank-id" and elem.get("primary") == "true":
                    current_drug_id = (elem.text or "").strip() or None
                elif local == "name" and current_drug_name is None:
                    current_drug_name = (elem.text or "").strip() or None
                elif local == "description" and current_drug_desc is None:
                    current_drug_desc = (elem.text or "").strip() or None

    return drugs, raw_interactions

def _execute_with_retry(session: Session, stmt, params, *, label: str) -> None:
    for attempt in range(1, 4):
        try:
            session.execute(stmt, params)
            session.commit()
            return
        except Exception as exc:
            session.rollback()
            if attempt == 3:
                raise
            log.warning("%s failed (attempt %d/3): %s — retrying", label, attempt, exc)
            time.sleep(5 * attempt)


def _seed_drugs(session: Session, drugs: dict[str, dict], batch_size: int) -> int:
    inserted = 0
    items = list(drugs.values())
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        _execute_with_retry(
            session,
            text(
                """
                INSERT INTO app.drugs (drugbank_id, name, description)
                VALUES (:drugbank_id, :name, :description)
                ON CONFLICT DO NOTHING
                """
            ),
            batch,
            label="drugs batch",
        )
        inserted += len(batch)
        log.info("  drugs: inserted batch %d/%d", min(i + batch_size, len(items)), len(items))
    return inserted


def _seed_interactions(
    session: Session,
    raw_interactions: list[dict],
    known_ids: set[str],
    batch_size: int,
) -> tuple[int, int]:
    valid = [
        r for r in raw_interactions
        if r["drug_a_id"] in known_ids and r["drug_b_id"] in known_ids
    ]
    skipped = len(raw_interactions) - len(valid)
    if skipped:
        log.info("  Skipped %d interactions referencing unknown drug IDs", skipped)

    inserted = 0
    for i in range(0, len(valid), batch_size):
        batch = valid[i : i + batch_size]
        _execute_with_retry(
            session,
            text(
                """
                INSERT INTO app.drug_interactions (drug_a_id, drug_b_id, description)
                VALUES (:drug_a_id, :drug_b_id, :description)
                ON CONFLICT ON CONSTRAINT uq_drug_interaction_pair DO NOTHING
                """
            ),
            batch,
            label="interactions batch",
        )
        inserted += len(batch)
        log.info(
            "  interactions: inserted batch %d/%d",
            min(i + batch_size, len(valid)),
            len(valid),
        )
    return inserted, skipped


def seed(xml_path: Path, batch_size: int, cache_path: Path | None) -> None:
    if cache_path and cache_path.is_file():
        log.info("Loading cached parse from %s …", cache_path)
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        drugs = cached["drugs"]
        raw_interactions = cached["raw_interactions"]
        log.info("Loaded %d drugs, %d raw interactions", len(drugs), len(raw_interactions))
    else:
        if not xml_path.is_file():
            log.error("DrugBank XML not found: %s", xml_path)
            sys.exit(1)

        log.info("Parsing %s …", xml_path)
        drugs, raw_interactions = _parse_drugs(xml_path)
        log.info("Parsed %d drugs, %d raw interactions", len(drugs), len(raw_interactions))

        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps({"drugs": drugs, "raw_interactions": raw_interactions}),
                encoding="utf-8",
            )
            log.info("Wrote parse cache to %s", cache_path)

    engine = _make_engine()
    with Session(engine) as session:
        log.info("Seeding app.drugs …")
        _seed_drugs(session, drugs, batch_size)

        log.info("Seeding app.drug_interactions …")
        known_ids = set(drugs.keys())
        inserted, skipped = _seed_interactions(session, raw_interactions, known_ids, batch_size)

    log.info(
        "Done. drugs=%d  interactions_inserted=%d  interactions_skipped=%d",
        len(drugs),
        inserted,
        skipped,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed app.drugs and app.drug_interactions from DrugBank XML."
    )
    parser.add_argument(
        "--xml",
        type=Path,
        default=_PROJECT_ROOT / ".sources" / "drugbank.xml",
        help="Path to drugbank.xml (default: .sources/drugbank.xml)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=500,
        help="INSERT batch size (default: 500)",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=_PROJECT_ROOT / ".output" / "drugbank_parsed.json",
        help="Cache parsed DrugBank JSON to skip re-parsing on retry",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    seed(xml_path=args.xml, batch_size=args.batch, cache_path=args.cache)
