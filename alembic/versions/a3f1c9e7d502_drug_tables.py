"""drug_tables

Revision ID: a3f1c9e7d502
Revises: f8dab36de248
Create Date: 2026-04-30

Creates app.drugs and app.drug_interactions tables sourced from DrugBank XML.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a3f1c9e7d502'
down_revision: Union[str, Sequence[str], None] = 'f8dab36de248'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_SCHEMA = "app"


def upgrade() -> None:
    op.create_table(
        "drugs",
        sa.Column("drugbank_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("drugbank_id"),
        sa.UniqueConstraint("name"),
        schema=APP_SCHEMA,
    )
    op.create_index("ix_drugs_name", "drugs", ["name"], schema=APP_SCHEMA)

    op.create_table(
        "drug_interactions",
        sa.Column("id", sa.Integer, autoincrement=True, nullable=False),
        sa.Column("drug_a_id", sa.String(20), nullable=False),
        sa.Column("drug_b_id", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["drug_a_id"], [f"{APP_SCHEMA}.drugs.drugbank_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["drug_b_id"], [f"{APP_SCHEMA}.drugs.drugbank_id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("drug_a_id", "drug_b_id", name="uq_drug_interaction_pair"),
        schema=APP_SCHEMA,
    )
    op.create_index("ix_drug_interaction_a", "drug_interactions", ["drug_a_id"], schema=APP_SCHEMA)
    op.create_index("ix_drug_interaction_b", "drug_interactions", ["drug_b_id"], schema=APP_SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_drug_interaction_b", table_name="drug_interactions", schema=APP_SCHEMA)
    op.drop_index("ix_drug_interaction_a", table_name="drug_interactions", schema=APP_SCHEMA)
    op.drop_table("drug_interactions", schema=APP_SCHEMA)

    op.drop_index("ix_drugs_name", table_name="drugs", schema=APP_SCHEMA)
    op.drop_table("drugs", schema=APP_SCHEMA)
