import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from database import SessionLocal
from models import Artist, Song, EntityTypeEnum, GenderEnum

# Cargar variables de entorno (SPOTIPY_CLIENT_ID y SPOTIPY_CLIENT_SECRET)
load_dotenv()

def load_playlist_to_db(playlist_url: str):
    """
    Extrae metadatos de las canciones de una playlist de Spotify y las carga
    en AWS RDS evitando registros duplicados.
    """
    # Autenticación con Spotify usando credenciales del .env
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())
    
    # Abrir sesión de base de datos
    db = SessionLocal()
    
    try:
        # Extraer los tracks de la playlist
        results = sp.playlist_tracks(playlist_url)
        tracks = results['items']
        
        # Manejo de paginación si la playlist tiene más de 100 canciones
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
            
        for item in tracks:
            track = item.get('track')
            if not track:
                continue
                
            spotify_id = track.get('id')
            title = track.get('name')
            
            # Procesar el año de lanzamiento (viene en formato YYYY-MM-DD, YYYY-MM o YYYY)
            album = track.get('album', {})
            release_date = album.get('release_date', '')
            release_year = int(release_date.split('-')[0]) if release_date else 0
            
            # Tomar el primer artista como el principal
            artists_data = track.get('artists', [])
            if not artists_data:
                continue
            primary_artist_name = artists_data[0].get('name')
            
            # 1. UPSERT de Artistas (Evitar duplicados)
            artist = db.query(Artist).filter(Artist.name == primary_artist_name).first()
            if not artist:
                artist = Artist(
                    name=primary_artist_name,
                    entity_type=EntityTypeEnum.Individual, # Valor genérico por defecto
                    gender=GenderEnum.NA,                  # Valor genérico por defecto
                    main_genre=None
                )
                db.add(artist)
                db.commit() # Guardamos para generar el UUID del artista
                db.refresh(artist)
                
            # 2. UPSERT de Canciones (Evitar duplicados mediante spotify_id)
            song = db.query(Song).filter(Song.spotify_id == spotify_id).first()
            if not song:
                song = Song(
                    title=title,
                    artist_id=artist.id,
                    release_year=release_year,
                    spotify_id=spotify_id
                )
                db.add(song)
                
        # Confirmar todas las inserciones de canciones pendientes en lote
        db.commit()
        print("Carga de playlist completada exitosamente sin duplicados.")
        
    except Exception as e:
        db.rollback()
        print(f"Error procesando el pipeline de extracción: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # URL de prueba o pasada por variable de entorno
    test_playlist = os.getenv("SPOTIFY_PLAYLIST_URL", "https://open.spotify.com/playlist/1iHVS7ScZH3fkOcpcM4aEi?si=QT5Brg1tSXmQytPpK0lfDA")
    print(f"Iniciando pipeline para: {test_playlist}")
    load_playlist_to_db(test_playlist)
