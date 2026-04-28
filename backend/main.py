import uuid
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from database import get_db
from models import Category, Song
from schemas import CategoryResponse, SongResponse

# Inicializar la aplicación FastAPI
app = FastAPI(
    title="Dale Play API",
    description="Backend para el juego de trivia musical",
    version="1.0.0"
)

# Configurar CORS permitiendo todos los orígenes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/categories", response_model=List[CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    """
    Retorna la lista de todas las categorías (playlists) disponibles.
    """
    categories = db.query(Category).all()
    return categories

@app.get("/api/categories/{category_id}/play", response_model=List[SongResponse])
def play_category(category_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Recibe el ID de una categoría y retorna una lista aleatoria de 10 canciones
    que pertenezcan a esa categoría para iniciar el juego.
    """
    # 1. Validar que la categoría exista
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    # 2. Consultar las canciones unidas a esta categoría de forma aleatoria
    songs = (
        db.query(Song)
        .filter(Song.categories.any(Category.id == category_id))
        .order_by(func.random())
        .limit(10)
        .all()
    )
    
    # 3. Retornar si hay menos de 10 canciones, la API responderá con las que encuentre.
    if not songs:
        raise HTTPException(status_code=404, detail="No se encontraron canciones para esta categoría.")
        
    return songs
