"""chartevents and d_items tables

Revision ID: c1d4e8f902ab
Revises: b4e2a1c8f903
Create Date: 2026-06-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d4e8f902ab"
down_revision: Union[str, Sequence[str], None] = "b4e2a1c8f903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "d_items",
        sa.Column("row_id", sa.Integer(), nullable=False),
        sa.Column("itemid", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("abbreviation", sa.String(length=100), nullable=True),
        sa.Column("dbsource", sa.String(length=20), nullable=True),
        sa.Column("linksto", sa.String(length=50), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("unitname", sa.String(length=100), nullable=True),
        sa.Column("param_type", sa.String(length=30), nullable=True),
        sa.Column("conceptid", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("itemid"),
        schema="mimiciii",
    )
    op.create_index(
        op.f("ix_mimiciii_d_items_itemid"),
        "d_items",
        ["itemid"],
        unique=False,
        schema="mimiciii",
    )

    op.create_table(
        "chartevents",
        sa.Column("row_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("hadm_id", sa.Integer(), nullable=True),
        sa.Column("icustay_id", sa.Integer(), nullable=True),
        sa.Column("itemid", sa.Integer(), nullable=False),
        sa.Column("charttime", sa.DateTime(), nullable=True),
        sa.Column("storetime", sa.DateTime(), nullable=True),
        sa.Column("cgid", sa.Integer(), nullable=True),
        sa.Column("value", sa.String(length=255), nullable=True),
        sa.Column("valuenum", sa.Float(), nullable=True),
        sa.Column("valueuom", sa.String(length=50), nullable=True),
        sa.Column("warning", sa.Integer(), nullable=True),
        sa.Column("error", sa.Integer(), nullable=True),
        sa.Column("resultstatus", sa.String(length=50), nullable=True),
        sa.Column("stopped", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["subject_id"], ["mimiciii.patients.subject_id"]),
        sa.PrimaryKeyConstraint("row_id"),
        schema="mimiciii",
    )
    op.create_index("ix_mimic_chart_hadm", "chartevents", ["hadm_id"], unique=False, schema="mimiciii")
    op.create_index("ix_mimic_chart_itemid", "chartevents", ["itemid"], unique=False, schema="mimiciii")
    op.create_index("ix_mimic_chart_subject", "chartevents", ["subject_id"], unique=False, schema="mimiciii")
    op.create_index(
        op.f("ix_mimiciii_chartevents_itemid"),
        "chartevents",
        ["itemid"],
        unique=False,
        schema="mimiciii",
    )
    op.create_index(
        op.f("ix_mimiciii_chartevents_subject_id"),
        "chartevents",
        ["subject_id"],
        unique=False,
        schema="mimiciii",
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mimiciii_chartevents_subject_id"), table_name="chartevents", schema="mimiciii")
    op.drop_index(op.f("ix_mimiciii_chartevents_itemid"), table_name="chartevents", schema="mimiciii")
    op.drop_index("ix_mimic_chart_subject", table_name="chartevents", schema="mimiciii")
    op.drop_index("ix_mimic_chart_itemid", table_name="chartevents", schema="mimiciii")
    op.drop_index("ix_mimic_chart_hadm", table_name="chartevents", schema="mimiciii")
    op.drop_table("chartevents", schema="mimiciii")
    op.drop_index(op.f("ix_mimiciii_d_items_itemid"), table_name="d_items", schema="mimiciii")
    op.drop_table("d_items", schema="mimiciii")
