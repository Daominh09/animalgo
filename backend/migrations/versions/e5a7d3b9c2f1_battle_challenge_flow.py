"""battle challenge flow: pending challenges and stored resolution

Owner: Person C — Battle System.

The initial schema modelled a battle as something that already had both sides. The real
flow is asynchronous: a challenger sends one capture and the row waits in `pending` until
the opponent answers with a capture of their own. That needs three things the original
table could not express:

  - a nullable opponent_capture_id, for the window where nobody has answered yet
  - created_at, so a challenge nobody answers can be expired instead of sitting forever
  - the resolution breakdown, so the result screen reads a stored fact rather than
    re-rolling the dice every time it is opened

Existing rows: there are none in any environment (battles was a stub until now), but the
column adds are written to be safe on a populated table anyway -- every new column is
nullable, and dropping NOT NULL never fails.

Revision ID: e5a7d3b9c2f1
Revises: b7c2e5f81d34
Create Date: 2026-09-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5a7d3b9c2f1"
down_revision: Union[str, Sequence[str], None] = "b7c2e5f81d34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("battles", "opponent_capture_id", existing_type=sa.Uuid(), nullable=True)

    # server_default so the column can be NOT NULL without a backfill pass; the ORM
    # supplies its own value on insert, so the default only ever applies to rows written
    # outside the app (seed scripts, manual fixes).
    op.add_column(
        "battles",
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.add_column("battles", sa.Column("resolving_at", sa.DateTime(), nullable=True))
    op.add_column("battles", sa.Column("challenger_total", sa.Integer(), nullable=True))
    op.add_column("battles", sa.Column("opponent_total", sa.Integer(), nullable=True))
    op.add_column("battles", sa.Column("challenger_roll", sa.Integer(), nullable=True))
    op.add_column("battles", sa.Column("opponent_roll", sa.Integer(), nullable=True))
    op.add_column("battles", sa.Column("trait_advantage", sa.String(), nullable=True))
    op.add_column("battles", sa.Column("coins_awarded", sa.Integer(), nullable=True))

    # Every read of a player's battles is "mine, newest first" -- the Battle tab opens on
    # it, and both players poll it after a challenge. Two indexes rather than one because
    # a player is the challenger in some battles and the opponent in others, and those are
    # separate columns; a single composite index could not serve both halves of the OR.
    op.create_index("ix_battles_challenger_created", "battles", ["challenger_id", "created_at"])
    op.create_index("ix_battles_opponent_created", "battles", ["opponent_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_battles_opponent_created", table_name="battles")
    op.drop_index("ix_battles_challenger_created", table_name="battles")

    op.drop_column("battles", "coins_awarded")
    op.drop_column("battles", "trait_advantage")
    op.drop_column("battles", "opponent_roll")
    op.drop_column("battles", "challenger_roll")
    op.drop_column("battles", "opponent_total")
    op.drop_column("battles", "challenger_total")
    op.drop_column("battles", "resolving_at")
    op.drop_column("battles", "created_at")

    # Reinstating NOT NULL would fail on any pending challenge, which is exactly the
    # state this migration introduced. Clear those first so the downgrade is runnable
    # rather than a trap: a pending challenge has no outcome to preserve.
    op.execute("DELETE FROM battles WHERE opponent_capture_id IS NULL")
    op.alter_column("battles", "opponent_capture_id", existing_type=sa.Uuid(), nullable=False)
