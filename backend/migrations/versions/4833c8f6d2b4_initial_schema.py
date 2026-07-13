"""initial schema

Revision ID: 4833c8f6d2b4
Revises:
Create Date: 2026-07-12 18:48:13.703187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4833c8f6d2b4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),  # matches Supabase auth.users.id
        sa.Column("display_name", sa.String(), nullable=False, server_default=""),
        sa.Column("wallet_balance", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "species_cache",
        sa.Column("species_id", sa.String(), primary_key=True),
        sa.Column("common_name", sa.String(), nullable=False),
        sa.Column("gbif_occurrence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("region", sa.String(), nullable=False),
        sa.Column("iucn_status", sa.String(), nullable=False, server_default="NE"),
        sa.Column("cached_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "shop_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("effect", sa.String(), nullable=False, server_default=""),
    )

    op.create_table(
        "captures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("species_id", sa.String(), nullable=True),
        sa.Column("image_url", sa.String(), nullable=False),
        sa.Column("rarity_tier", sa.String(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("confirmed_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "battles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("challenger_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("opponent_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("challenger_capture_id", sa.Uuid(), sa.ForeignKey("captures.id"), nullable=False),
        sa.Column("opponent_capture_id", sa.Uuid(), sa.ForeignKey("captures.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("winner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("battles")
    op.drop_table("transactions")
    op.drop_table("captures")
    op.drop_table("shop_items")
    op.drop_table("species_cache")
    op.drop_table("users")
