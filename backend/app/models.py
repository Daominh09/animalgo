import uuid
from datetime import datetime

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)  # matches Supabase auth.users.id
    display_name: Mapped[str] = mapped_column(String, default="")
    wallet_balance: Mapped[int] = mapped_column(Integer, default=0)


class Capture(Base):
    __tablename__ = "captures"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    species_id: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str] = mapped_column(String)
    rarity_tier: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SpeciesCache(Base):
    """Durable per-species rarity reference cache (Postgres). Redis is the hot cache in
    front of this (app/services/cache.py); this table is the record written on the
    capture path so rarity data survives a Redis flush and stays auditable.

    The app targets US-based players only, so occurrence counts are always US and there
    is no region column — species_id alone is the primary key.
    """

    __tablename__ = "species_cache"
    species_id: Mapped[str] = mapped_column(String, primary_key=True)
    common_name: Mapped[str] = mapped_column(String)
    gbif_occurrence_count: Mapped[int] = mapped_column(Integer, default=0)  # US occurrences
    iucn_status: Mapped[str] = mapped_column(String, default="NE")
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Battle(Base):
    __tablename__ = "battles"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    challenger_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    opponent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    challenger_capture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("captures.id"))
    opponent_capture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("captures.id"))
    status: Mapped[str] = mapped_column(String, default="pending")
    winner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ShopItem(Base):
    __tablename__ = "shop_items"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    cost: Mapped[int] = mapped_column(Integer)
    effect: Mapped[str] = mapped_column(String, default="")


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
