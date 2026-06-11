"""patient_mimic_link

Revision ID: b4e2a1c8f903
Revises: a3f1c9e7d502
Create Date: 2026-06-10

Adds optional MIMIC-III link columns to patient_profiles.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b4e2a1c8f903"
down_revision: Union[str, Sequence[str], None] = "a3f1c9e7d502"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_SCHEMA = "app"


def upgrade() -> None:
    op.add_column(
        "patient_profiles",
        sa.Column("mimic_subject_id", sa.Integer(), nullable=True),
        schema=APP_SCHEMA,
    )
    op.add_column(
        "patient_profiles",
        sa.Column("mimic_hadm_id", sa.Integer(), nullable=True),
        schema=APP_SCHEMA,
    )
    op.create_index(
        op.f("ix_app_patient_profiles_mimic_subject_id"),
        "patient_profiles",
        ["mimic_subject_id"],
        unique=False,
        schema=APP_SCHEMA,
    )
    op.create_index(
        op.f("ix_app_patient_profiles_mimic_hadm_id"),
        "patient_profiles",
        ["mimic_hadm_id"],
        unique=False,
        schema=APP_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_app_patient_profiles_mimic_hadm_id"),
        table_name="patient_profiles",
        schema=APP_SCHEMA,
    )
    op.drop_index(
        op.f("ix_app_patient_profiles_mimic_subject_id"),
        table_name="patient_profiles",
        schema=APP_SCHEMA,
    )
    op.drop_column("patient_profiles", "mimic_hadm_id", schema=APP_SCHEMA)
    op.drop_column("patient_profiles", "mimic_subject_id", schema=APP_SCHEMA)
