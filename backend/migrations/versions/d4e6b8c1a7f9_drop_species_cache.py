"""drop species_cache table

Nothing ever read this table -- it was written on every capture and never queried, so
it was a write-only table carrying schema and maintenance cost for no benefit.

Redis (app/services/cache.py) is now the only rarity cache. Per-capture display data
(species name, rarity tier, image URL) is denormalised onto the captures row instead,
which is also what keeps a player's card matching the rarity they were actually paid
for -- species facts can change later, a capture must not.

Trade-off accepted: with no durable copy, a Redis outage means rarity lookups fall back
to the upstream APIs, and if those are also unavailable captures return unknown rarity.

Owner: Person B — Rarity Engine & Collection

Revision ID: d4e6b8c1a7f9
Revises: a1f3c9d2e4b5
Create Date: 2026-08-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e6b8c1a7f9"
down_revision: Union[str, Sequence[str], None] = "a1f3c9d2e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("species_cache")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "species_cache",
        sa.Column("species_id", sa.String(), primary_key=True),
        sa.Column("common_name", sa.String(), nullable=False),
        sa.Column("gbif_occurrence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("iucn_status", sa.String(), nullable=False, server_default="NE"),
        sa.Column("cached_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
