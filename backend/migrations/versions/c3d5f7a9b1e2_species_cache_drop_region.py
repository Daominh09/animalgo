"""species_cache: drop region column (US-only)

The app targets US-based players only, so occurrence counts are always US and the
region column is dead weight. Drop it; species_id alone stays the primary key.

Owner: Person B — Rarity Engine & Collection

Revision ID: c3d5f7a9b1e2
Revises: 4833c8f6d2b4
Create Date: 2026-07-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d5f7a9b1e2"
down_revision: Union[str, Sequence[str], None] = "4833c8f6d2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("species_cache", "region")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("species_cache", sa.Column("region", sa.String(), nullable=False, server_default=""))
