import uuid
from pydantic import BaseModel, ConfigDict
from typing import Optional

class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str

    # Pydantic v2: Configuración para leer atributos de SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

class ArtistResponse(BaseModel):
    name: str
    main_genre: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class SongResponse(BaseModel):
    id: uuid.UUID
    title: str
    release_year: int
    spotify_id: str
    artist: ArtistResponse
    youtube_url_id: Optional[str] = None
    preview_start_time_sec: Optional[int] = 45

    model_config = ConfigDict(from_attributes=True)
