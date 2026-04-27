import uuid
import enum
from sqlalchemy import Table, Column, String, Integer, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

class EntityTypeEnum(str, enum.Enum):
    Individual = "Individual"
    Group = "Group"

class GenderEnum(str, enum.Enum):
    Male = "Male"
    Female = "Female"
    Mixed = "Mixed"
    NA = "N/A"

# Tabla de asociación para la relación Muchos a Muchos (N:M)
category_songs = Table(
    "category_songs",
    Base.metadata,
    Column("category_id", UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
    Column("song_id", UUID(as_uuid=True), ForeignKey("songs.id", ondelete="CASCADE"), primary_key=True)
)

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    spotify_playlist_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Relación bidireccional de muchos a muchos con canciones
    songs: Mapped[list["Song"]] = relationship(
        "Song", secondary=category_songs, back_populates="categories"
    )

class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    entity_type: Mapped[EntityTypeEnum] = mapped_column(SQLEnum(EntityTypeEnum), nullable=False)
    gender: Mapped[GenderEnum] = mapped_column(SQLEnum(GenderEnum), nullable=False)
    main_genre: Mapped[str] = mapped_column(String, nullable=True)

    # Relación bidireccional con canciones
    songs: Mapped[list["Song"]] = relationship(
        "Song", back_populates="artist", cascade="all, delete-orphan"
    )

class Song(Base):
    __tablename__ = "songs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String, nullable=False)
    artist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("artists.id"), nullable=False)
    release_year: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    spotify_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    youtube_url_id: Mapped[str] = mapped_column(String, nullable=True)
    preview_start_time_sec: Mapped[float] = mapped_column(Float, nullable=True)

    # Relación bidireccional con artista
    artist: Mapped["Artist"] = relationship("Artist", back_populates="songs")

    # Relación bidireccional de muchos a muchos con categorías
    categories: Mapped[list["Category"]] = relationship(
        "Category", secondary=category_songs, back_populates="songs"
    )
