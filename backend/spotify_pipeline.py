import os
import uuid
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from database import SessionLocal
from models import Artist, Song, Category, EntityTypeEnum, GenderEnum

# Cargar variables de entorno (SPOTIPY_CLIENT_ID y SPOTIPY_CLIENT_SECRET)
load_dotenv()

def load_playlist_to_db(playlist_id: str, category_name: str):
    """
    Extrae metadatos de las canciones de una playlist de Spotify y las carga
    en AWS RDS evitando registros duplicados. Implementa relación N:M con Categorías
    y búsqueda de género real de los artistas.
    """
    # Autenticación con Spotify usando credenciales del .env
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri="http://127.0.0.1:8000/callback",
    scope="playlist-read-private playlist-read-collaborative"
    ))
    
    # Abrir sesión de base de datos
    db = SessionLocal()
    
    try:
        # 1. BUSCAR O CREAR CATEGORÍA (Por Nombre en lugar de ID)
        category = db.query(Category).filter(Category.name == category_name).first()
        if not category:
            category = Category(
                name=category_name,
                spotify_playlist_id=playlist_id
            )
            db.add(category)
            db.commit()
            db.refresh(category)
            
        # Extraer los tracks de la playlist de forma paginada y segura
        results = sp.playlist_tracks(playlist_id)
        tracks = results.get('items', [])
        
        while results['next']:
            results = sp.next(results)
            tracks.extend(results.get('items', []))
            
        # --- NUEVO: Mostrar total de canciones ---
        total_tracks = len(tracks)
        print(f"🎶 ¡Spotify respondió! Se encontraron {total_tracks} canciones. Iniciando extracción de datos...")
            
        # Usamos enumerate(tracks, start=1) para tener el número de la canción actual
        for index, item in enumerate(tracks, start=1):
            
            # Lógica segura de extracción (Cubre tracks y videos/items locales)
            track = item.get('track') or item.get('item')
            if not track:
                print(f"[{index}/{total_tracks}] ⚠️ Elemento vacío saltado.")
                continue
                
            # Generar ID seguro por si es nulo
            spotify_id = track.get('id')
            if not spotify_id:
                spotify_id = f"custom_vid_{uuid.uuid4().hex[:12]}"
                
            title = track.get('name')
            if not title:
                continue
                
            # --- NUEVO: Imprimir el progreso ---
            print(f"[{index}/{total_tracks}] Procesando: {title}...")

            
            # Procesar el año de lanzamiento
            album = track.get('album', {})
            release_date = album.get('release_date', '')
            release_year = int(release_date.split('-')[0]) if release_date else 0
            
            # Extraer información básica del artista
            artists_data = track.get('artists', [])
            if not artists_data:
                continue
            primary_artist_name = artists_data[0].get('name')
            artist_spotify_id = artists_data[0].get('id')
            
            # 2. UPSERT de Artistas (Evitar duplicados) e Inyección de Género
            artist = db.query(Artist).filter(Artist.name == primary_artist_name).first()
            if not artist:
                main_genre = "Desconocido"
                
                # Optimización API: Buscar género solo si el artista no existe en DB
                if artist_spotify_id:
                    artist_info = sp.artist(artist_spotify_id)
                    genres = artist_info.get('genres', [])
                    if genres:
                        main_genre = genres[0]
                
                artist = Artist(
                    name=primary_artist_name,
                    entity_type=EntityTypeEnum.Individual, # Default genérico
                    gender=GenderEnum.NA,                  # Default genérico
                    main_genre=main_genre
                )
                db.add(artist)
                db.commit() # Guardamos para generar el UUID del artista
                db.refresh(artist)
                
            # 3. UPSERT de Canciones (Evitar duplicados mediante spotify_id)
            song = db.query(Song).filter(Song.spotify_id == spotify_id).first()
            if not song:
                song = Song(
                    title=title,
                    artist_id=artist.id,
                    release_year=release_year,
                    spotify_id=spotify_id
                )
                db.add(song)
                db.commit() # Guardamos tempranamente para obtener el id del song y asociar
                db.refresh(song)
            
            # 4. Asociación N:M (Song <-> Category)
            # Evitar repetición de la misma categoría en la lista de la canción
            if category not in song.categories:
                song.categories.append(category)
                
        # Confirmar todas las asociaciones N:M
        db.commit()
        print(f"Carga de playlist '{category_name}' completada exitosamente.")
        
    except Exception as e:
        db.rollback()
        print(f"Error procesando el pipeline de extracción: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Pon aquí el ID de tu primera playlist y el nombre que quieres que tenga en el juego
    test_id = "6lRDcv9f2GvKN6prHAdby5" 
    test_name = "Divos Hispano" # (O el nombre que le quieras dar)
    
    print(f"Iniciando pipeline para la categoría: {test_name}")
    load_playlist_to_db(test_id, test_name)