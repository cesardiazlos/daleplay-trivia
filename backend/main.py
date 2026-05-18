import uuid
import random
import asyncio
from typing import List

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from database import get_db, SessionLocal
from models import Category, Song, Artist
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

def get_distractors(correct_artist: Artist, db_artists: List[Artist], excluded_ids: set, round_artist_ids: set = None) -> List[Artist]:
    if round_artist_ids is None: round_artist_ids = set()
    valid_artists = [a for a in db_artists if a.gender and a.gender.strip().lower() != "desconocido" and a.id != correct_artist.id and a.id not in round_artist_ids]
    fresh = [a for a in valid_artists if a.id not in excluded_ids]
    recycled = [a for a in valid_artists if a.id in excluded_ids]
    chosen = []

    def fill(candidates, condition):
        needed = 3 - len(chosen)
        if needed <= 0: return
        match = [a for a in candidates if a.id not in [c.id for c in chosen] and condition(a)]
        chosen.extend(random.sample(match, min(needed, len(match))))

    # 1. Frescos mismo género
    fill(fresh, lambda a: a.entity_type == correct_artist.entity_type and a.gender == correct_artist.gender and a.main_genre == correct_artist.main_genre)
    # 2. Reciclados mismo género (¡CRÍTICO!)
    fill(recycled, lambda a: a.entity_type == correct_artist.entity_type and a.gender == correct_artist.gender and a.main_genre == correct_artist.main_genre)
    # 3. Frescos mismo tipo/sexo
    fill(fresh, lambda a: a.entity_type == correct_artist.entity_type and a.gender == correct_artist.gender)
    # 4. Reciclados mismo tipo/sexo
    fill(recycled, lambda a: a.entity_type == correct_artist.entity_type and a.gender == correct_artist.gender)
    # 5. Relleno final por sexo
    fill(fresh, lambda a: a.gender == correct_artist.gender)
    fill(recycled, lambda a: a.gender == correct_artist.gender)
    return chosen

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

    # 2. Consultar un pool grande de canciones para filtrar duplicados
    raw_songs = (
        db.query(Song)
        .filter(Song.categories.any(Category.id == category_id))
        .order_by(func.random())
        .limit(60)
        .all()
    )
    
    unique_songs = []
    seen_titles = set()
    for song in raw_songs:
        normalized_title = song.title.strip().lower()
        if normalized_title not in seen_titles:
            seen_titles.add(normalized_title)
            unique_songs.append(song)
            if len(unique_songs) == 10:
                break
                
    songs = unique_songs
    
    # 3. Retornar si hay menos de 10 canciones, la API responderá con las que encuentre.
    if not songs:
        raise HTTPException(status_code=404, detail="No se encontraron canciones para esta categoría.")
        
    # --- CORRECCIÓN LÓGICA DE ALTERNATIVAS (CASCADA DE PRIORIDADES ANTI-SPOILERS) ---
    db_artists = db.query(Artist).all()
    
    round_artist_ids = {s.artist.id for s in songs}
    used_distractor_ids = set()
    
    for song in songs:
        correct_artist = song.artist
        
        # Obtenemos los distractores usando la función helper
        chosen_distractors = get_distractors(
            correct_artist=correct_artist, 
            db_artists=db_artists,
            excluded_ids=round_artist_ids.union(used_distractor_ids),
            round_artist_ids=round_artist_ids
        )
        
        used_distractor_ids.update(d.id for d in chosen_distractors)
                
        # Construir la lista de 4 alternativas (1 correcta + 3 incorrectas)
        options = [correct_artist] + chosen_distractors
        
        # Barajar para que la correcta no siempre esté primero
        random.shuffle(options)
        
        # Inyectamos options en el objeto song
        setattr(song, "options", options)
        
    return songs

@app.get("/api/categories/{category_id}/rewind", response_model=List[SongResponse])
def play_rewind(category_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retorna exactamente 4 canciones de una categoría, garantizando que cada una 
    tenga un año de lanzamiento distinto para el modo Rewind Musical.
    """
    # 1. Validar categoría
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    # 2. Consultar canciones de la categoría asegurando que tengan año definido
    raw_songs = (
        db.query(Song)
        .filter(Song.categories.any(Category.id == category_id))
        .filter(Song.release_year != None)
        .all()
    )

    # 3. Agrupar por año para evitar empates temporales
    songs_by_year = {}
    for song in raw_songs:
        year = getattr(song, 'release_year', None)
        if year:
            if year not in songs_by_year:
                songs_by_year[year] = []
            songs_by_year[year].append(song)
    
    unique_years = list(songs_by_year.keys())
    
    # 4. Validar que haya al menos 4 años distintos
    if len(unique_years) < 4:
        raise HTTPException(
            status_code=400, 
            detail="La categoría no tiene suficientes canciones con años distintos para jugar Rewind (mínimo 4)."
        )
        
    # 5. Seleccionar 4 años distintos al azar y 1 canción por cada año
    selected_years = random.sample(unique_years, 4)
    rewind_tracks = [random.choice(songs_by_year[year]) for year in selected_years]
    
    # 6. Desordenar para que la TV las muestre mezcladas
    random.shuffle(rewind_tracks)
    
    # 7. Mockear el atributo 'options' para cumplir con el esquema SongResponse (No se usan distractores aquí)
    for song in rewind_tracks:
        setattr(song, "options", [])
        
    return rewind_tracks

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
        is_reconnect = pin in self.rooms
        if not is_reconnect:
            self.rooms[pin] = {"host": None, "players": {}, "state": {"current_song_index": 0, "round_answers": set(), "estado_juego": "lobby", "last_guessing_event": None}}
        self.rooms[pin]["host"] = websocket
        # Si es reconexión, enviar la lista de jugadores actuales al Host
        if is_reconnect:
            active_players = [name for name, p in self.rooms[pin]["players"].items() if p.get("status") == "active"]
            if active_players:
                await websocket.send_json({"type": "player_joined", "player_name": active_players[-1], "players_list": active_players})

    def disconnect_host(self, pin: str):
        if pin in self.rooms:
            # No destruir la sala inmediatamente: dar 15s de gracia para reconexión
            self.rooms[pin]["host"] = None
            asyncio.create_task(self._host_grace_period(pin))

    async def _host_grace_period(self, pin: str):
        await asyncio.sleep(15)
        if pin in self.rooms and self.rooms[pin]["host"] is None:
            # El host no se reconectó en 15 segundos, destruir la sala
            del self.rooms[pin]

    async def connect_player(self, websocket: WebSocket, pin: str, player_name: str):
        if pin not in self.rooms:
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": "Sala no existente"})
            await websocket.close(code=4000) # Código personalizado para sala no encontrada
            return False

        if player_name in self.rooms[pin]["players"]:
            player_data = self.rooms[pin]["players"][player_name]
            if player_data["status"] == "active":
                await websocket.accept()
                await websocket.send_json({"type": "error", "message": "name_taken"})
                await websocket.close(code=1008, reason="Name taken")
                return False
            else:
                # Reconexión
                await websocket.accept()
                player_data["ws"] = websocket
                player_data["status"] = "active"
                
                # Send current state to sync UI
                state = self.rooms[pin]["state"]
                if state.get("estado_juego") == "jugando" and state.get("last_guessing_event"):
                    await websocket.send_json(state["last_guessing_event"])
                
                # Notify host
                active_players = [p for p, d in self.rooms[pin]["players"].items() if d["status"] == "active"]
                await self.send_to_host(pin, {
                    "type": "player_joined",
                    "player_name": player_name,
                    "players_list": active_players
                })
                return True
        else:
            await websocket.accept()
            self.rooms[pin]["players"][player_name] = {
                "ws": websocket,
                "score": 0,
                "status": "active",
                "is_ready": False
            }
            
            # Late joiners
            state = self.rooms[pin]["state"]
            if state.get("estado_juego") == "jugando" and state.get("last_guessing_event"):
                await websocket.send_json(state["last_guessing_event"])

            await websocket.send_json({"type": "join_success"})

            # Notify host
            active_players = [p for p, d in self.rooms[pin]["players"].items() if d["status"] == "active"]
            await self.send_to_host(pin, {
                "type": "player_joined",
                "player_name": player_name,
                "players_list": active_players
            })
            return True

    async def disconnect_player(self, pin: str, player_name: str):
        if pin in self.rooms and player_name in self.rooms[pin]["players"]:
            self.rooms[pin]["players"][player_name]["status"] = "inactive"
            active_players = [p for p, d in self.rooms[pin]["players"].items() if d["status"] == "active"]
            await self.send_to_host(pin, {
                "type": "player_left",
                "player_name": player_name,
                "players_list": active_players
            })

    async def send_to_host(self, pin: str, message: dict):
        if pin in self.rooms and self.rooms[pin]["host"]:
            await self.rooms[pin]["host"].send_json(message)

    async def send_to_players(self, pin: str, message: dict):
        if pin in self.rooms:
            for player_name, player_data in self.rooms[pin]["players"].items():
                if player_data["status"] == "active":
                    try:
                        await player_data["ws"].send_json(message)
                    except Exception:
                        pass

manager = ConnectionManager()

@app.websocket("/ws/host/{pin}")
async def websocket_host(websocket: WebSocket, pin: str):
    await manager.connect_host(websocket, pin)
    try:
        while True:
            data = await websocket.receive_json()

            # Ciclo de Vida: crear_sala
            if data.get("type") == "crear_sala":
                if pin in manager.rooms:
                    manager.rooms[pin]["state"]["estado_juego"] = "lobby"
                continue

            # Ciclo de Vida: cerrar_sala
            if data.get("type") == "cerrar_sala":
                await manager.send_to_players(pin, {"type": "sala_cerrada"})
                manager.disconnect_host(pin)
                continue

            # El Host informa qué categoría se está jugando (enviado al inicio de partida)
            if data.get("type") == "set_category":
                cat_id = data.get("category_id")
                if pin in manager.rooms and cat_id:
                    manager.rooms[pin]["state"]["category_id"] = cat_id
                continue

            if data.get("type") == "volver_a_lobby":
                if pin in manager.rooms:
                    manager.rooms[pin]["state"]["estado_juego"] = "lobby"
                    manager.rooms[pin]["state"]["round_answers"] = set()
                    await manager.send_to_players(pin, {"type": "reset_to_lobby"})
                continue

            if data.get("type") == "youtube_error":
                track_id = data.get("track_id")
                played_ids = data.get("played_ids", [])
                
                try:
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

                            # Query base: canciones con video válido y que no se hayan jugado
                            excluded_ids = played_ids + [track_id]
                            replacement_query = db.query(Song).filter(
                                Song.youtube_url_id != None,
                                Song.id.notin_(excluded_ids)
                            )
                            if room_cat_id:
                                replacement_query = replacement_query.filter(
                                    Song.categories.any(Category.id == room_cat_id)
                                )

                            replacement = replacement_query.order_by(func.random()).first()
                            if not replacement:
                                # Fallback crítico: si no hay frescas, repetimos una válida de la categoría para no congelar el juego
                                fallback_query = db.query(Song).filter(Song.youtube_url_id != None)
                                if room_cat_id:
                                    fallback_query = fallback_query.filter(Song.categories.any(Category.id == room_cat_id))
                                replacement = fallback_query.order_by(func.random()).first()

                            if replacement:
                                # 3 distractores usando la nueva Cascada de Prioridades
                                db_artists = db.query(Artist).all()
                                distractors = get_distractors(replacement.artist, db_artists, set())
                                
                                options = [replacement.artist] + distractors
                                random.shuffle(options)
                                
                                # Formateamos solo id y name de los Artistas (Esquema correcto)
                                formatted_options = [{"id": str(opt.id) if getattr(opt, 'id', None) else str(uuid.uuid4()), "name": opt.name} for opt in options]

                                # Encapsulamos la canción completa con sus opciones formateadas
                                replacement_dict = SongResponse.model_validate(replacement).model_dump(mode='json')
                                replacement_dict["options"] = formatted_options
                                
                                # Nota para el Frontend: ahora enviamos "song" que es el objeto completo
                                payload = {"type": "replacement_round", "song": replacement_dict}
                                
                                await websocket.send_json(payload)
                                # Sincronizar a los celulares también
                                await manager.send_to_players(pin, payload)
                    finally:
                        db.close()
                except Exception as e:
                    print(f"Error crítico en reemplazo de YouTube: {e}")
            else:
                # El Host reenvía el estado o comandos a los jugadores
                await manager.send_to_players(pin, data)

                # Si el Host arranca una nueva ronda o cambia estado
                if data.get("type") == "state_change":
                    if pin in manager.rooms:
                        status = data.get("status")
                        if status == "guessing":
                            manager.rooms[pin]["state"]["round_answers"] = set()
                            manager.rooms[pin]["state"]["estado_juego"] = "jugando"
                            manager.rooms[pin]["state"]["last_guessing_event"] = data
                            # Reset is_ready
                            for p in manager.rooms[pin]["players"].values():
                                p["is_ready"] = False
                        elif status in ["revealing", "finished"]:
                            manager.rooms[pin]["state"]["estado_juego"] = "post_ronda"
                            manager.rooms[pin]["state"]["last_guessing_event"] = data
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

            # Jugador listo para siguiente ronda
            if data.get("type") == "player_ready" and pin in manager.rooms:
                if player_name in manager.rooms[pin]["players"]:
                    manager.rooms[pin]["players"][player_name]["is_ready"] = True
                    # Check if all active players are ready
                    active_players = [d for d in manager.rooms[pin]["players"].values() if d["status"] == "active"]
                    ready_players = [d for d in active_players if d["is_ready"]]
                    await manager.send_to_host(pin, {
                        "type": "ready_status",
                        "ready": len(ready_players),
                        "total": len(active_players)
                    })

            # Jugador abandona
            if data.get("type") == "leave_room" and pin in manager.rooms:
                if player_name in manager.rooms[pin]["players"]:
                    manager.rooms[pin]["players"][player_name]["status"] = "inactive"
                    active_players = [p for p, d in manager.rooms[pin]["players"].items() if d["status"] == "active"]
                    await manager.send_to_host(pin, {
                        "type": "player_left",
                        "player_name": player_name,
                        "players_list": active_players
                    })
                    await websocket.close()
                    break

            # Tracking de respuestas para efecto Kahoot
            if data.get("type") == "player_answered" and pin in manager.rooms:
                room = manager.rooms[pin]
                room["state"]["round_answers"].add(player_name)
                # Check only active players for all_answered
                active_players = [p for p, d in room["players"].items() if d["status"] == "active"]
                total_players = len(active_players)
                total_answers = len([p for p in room["state"]["round_answers"] if p in active_players])
                if total_players > 0 and total_answers >= total_players:
                    await manager.send_to_host(pin, {"type": "todos_respondieron"})
    except WebSocketDisconnect:
        await manager.disconnect_player(pin, player_name)
