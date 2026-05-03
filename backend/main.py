import uuid
from typing import List

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from database import get_db, SessionLocal
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

@app.patch("/api/songs/{song_id}/invalidate")
def invalidate_song(song_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Anula el youtube_url_id de una canción si el reproductor reporta un error de incrustación.
    """
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Canción no encontrada.")
    
    song.youtube_url_id = None
    db.commit()
    return {"status": "success", "message": "Video invalidado para futura corrección."}

# ==========================================
# GESTOR DE CONEXIONES WEBSOCKET
# ==========================================
class ConnectionManager:
    def __init__(self):
        # Estructura: { "pin": { "host": WebSocket, "players": {"player_name": WebSocket}, "state": {} } }
        self.rooms: dict = {}

    async def connect_host(self, websocket: WebSocket, pin: str):
        await websocket.accept()
        if pin not in self.rooms:
            self.rooms[pin] = {"host": None, "players": {}, "state": {"current_song_index": 0}}
        self.rooms[pin]["host"] = websocket

    def disconnect_host(self, pin: str):
        if pin in self.rooms:
            # Si el host se desconecta, destruimos la sala
            del self.rooms[pin]

    async def connect_player(self, websocket: WebSocket, pin: str, player_name: str):
        await websocket.accept()
        if pin not in self.rooms:
            # Si no existe la sala, cerramos la conexión
            await websocket.close(code=1008, reason="Room does not exist")
            return False
        
        self.rooms[pin]["players"][player_name] = websocket
        # Notificamos al host que un jugador se unió
        await self.send_to_host(pin, {
            "type": "player_joined",
            "player_name": player_name,
            "players_list": list(self.rooms[pin]["players"].keys())
        })
        return True

    async def disconnect_player(self, pin: str, player_name: str):
        if pin in self.rooms and player_name in self.rooms[pin]["players"]:
            del self.rooms[pin]["players"][player_name]
            # Notificamos al host que el jugador se desconectó
            await self.send_to_host(pin, {
                "type": "player_left",
                "player_name": player_name,
                "players_list": list(self.rooms[pin]["players"].keys())
            })

    async def send_to_host(self, pin: str, message: dict):
        if pin in self.rooms and self.rooms[pin]["host"]:
            await self.rooms[pin]["host"].send_json(message)

    async def send_to_players(self, pin: str, message: dict):
        if pin in self.rooms:
            for player_ws in list(self.rooms[pin]["players"].values()):
                try:
                    await player_ws.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

@app.websocket("/ws/host/{pin}")
async def websocket_host(websocket: WebSocket, pin: str):
    await manager.connect_host(websocket, pin)
    try:
        while True:
            data = await websocket.receive_json()

            # El Host informa qué categoría se está jugando (enviado al inicio de partida)
            if data.get("type") == "set_category":
                cat_id = data.get("category_id")
                if pin in manager.rooms and cat_id:
                    manager.rooms[pin]["state"]["category_id"] = cat_id
                continue

            if data.get("type") == "youtube_error":
                track_id = data.get("track_id")
                db = SessionLocal()
                try:
                    song = db.query(Song).filter(Song.id == track_id).first()
                    if song:
                        song.youtube_url_id = None
                        db.commit()

                        # Obtener la categoría de la sala para filtrar reemplazos en-genre
                        room_cat_id = None
                        if pin in manager.rooms:
                            room_cat_id = manager.rooms[pin]["state"].get("category_id")

                        # Query base: canciones con video válido
                        replacement_query = db.query(Song).filter(Song.youtube_url_id != None)
                        if room_cat_id:
                            replacement_query = replacement_query.filter(
                                Song.categories.any(Category.id == room_cat_id)
                            )

                        replacement = replacement_query.order_by(func.random()).first()
                        if replacement:
                            # 3 distractores del mismo género
                            distractor_query = db.query(Song).filter(
                                Song.id != replacement.id,
                                Song.artist_id != replacement.artist_id
                            )
                            if room_cat_id:
                                distractor_query = distractor_query.filter(
                                    Song.categories.any(Category.id == room_cat_id)
                                )
                            others = distractor_query.order_by(func.random()).limit(3).all()

                            options = [SongResponse.model_validate(replacement).model_dump(mode='json')] + \
                                      [SongResponse.model_validate(o).model_dump(mode='json') for o in others]
                            payload = {"type": "replacement_round", "options": options}
                            await websocket.send_json(payload)
                            # Sincronizar a los celulares también
                            await manager.send_to_players(pin, payload)
                finally:
                    db.close()
            else:
                # El Host reenvía el estado o comandos a los jugadores
                await manager.send_to_players(pin, data)
    except WebSocketDisconnect:
        manager.disconnect_host(pin)

@app.websocket("/ws/player/{pin}/{player_name}")
async def websocket_player(websocket: WebSocket, pin: str, player_name: str):
    connected = await manager.connect_player(websocket, pin, player_name)
    if not connected:
        return
    
    try:
        while True:
            data = await websocket.receive_json()
            # Inyectamos el nombre del jugador para que el Host sepa de quién es la respuesta
            data["player_name"] = player_name
            await manager.send_to_host(pin, data)
    except WebSocketDisconnect:
        await manager.disconnect_player(pin, player_name)
