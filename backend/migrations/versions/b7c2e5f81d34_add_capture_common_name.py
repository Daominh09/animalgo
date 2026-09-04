"""add common_name to captures

Revision ID: b7c2e5f81d34
Revises: d4e6b8c1a7f9
Create Date: 2026-08-05

The capture row stored only species_id -- the scientific name -- so a Collection card
could only read "Passer domesticus". Players want "House Sparrow".

The vision step already returns both names and the common one was simply discarded. It
is denormalised onto the capture rather than looked up later, for the same reason the
rarity tier is: a card should keep showing what the player was told at the time, even if
the species reference data changes afterwards.

Nullable, because rows written before this existed have no common name, and because
vision can legitimately identify only a family (Troglodytidae) with no common name to
give. The UI falls back to the scientific name.
"""

import sqlalchemy as sa
from alembic import op

revision = "b7c2e5f81d34"
down_revision = "d4e6b8c1a7f9"
branch_labels = None
depends_on = None


def _has_column() -> bool:
    return (
        op.get_bind()
        .execute(
            sa.text(
                "select 1 from information_schema.columns "
                "where table_name = 'captures' and column_name = 'common_name'"
            )
        )
        .first()
        is not None
    )


def upgrade() -> None:
    # Guarded rather than a bare add_column. The shared database is currently stamped
    # with a revision that exists in nobody's branch (an uncommitted migration that
    # added `user_items`), so alembic cannot walk its own chain there and the column may
    # have to be added by hand to unblock work. This makes the migration correct whether
    # or not that happened, instead of failing with "column already exists" later.
    if not _has_column():
        op.add_column("captures", sa.Column("common_name", sa.String(), nullable=True))


def downgrade() -> None:
    if _has_column():
        op.drop_column("captures", "common_name")
