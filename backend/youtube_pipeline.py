import sys
import yt_dlp
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Song, Artist

def search_youtube_id(query: str) -> str:
    # Usar extract_flat=False y ignoreerrors=True para que yt-dlp 
    # intente extraer los detalles y descarte los videos bloqueados
    ydl_opts = {
        'quiet': True,
        'extract_flat': False,
        'ignoreerrors': True,
        'no_warnings': True  # <-- Agrega esta línea
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # ytsearch5: busca los primeros 5 resultados en YouTube
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if 'entries' in info and info['entries']:
                for entry in info['entries']:
                    if entry and entry.get('id'):
                        # El primer video que no haya lanzado error durante la extracción de metadatos
                        return entry['id']
        except Exception as e:
            print(f"[-] Error interno de búsqueda para '{query}': {e}")
            pass
    return None

def run_pipeline():
    db: Session = SessionLocal()
    
    try:
        # Filtro: Consultar exclusivamente las canciones que tengan youtube_url_id IS NULL
        songs = db.query(Song).filter(Song.youtube_url_id.is_(None)).all()
        
        if not songs:
            print("[*] No hay canciones con youtube_url_id nulo. ¡Todo está actualizado!")
            return

        print(f"[*] Iniciando ETL Paso 2 (YouTube). Canciones a procesar: {len(songs)}")

        for song in songs:
            # Buscar el artista asociado (debido a lazy loading o si no está en join)
            artist_name = song.artist.name if song.artist else "Desconocido"
            
            # Cadena exacta de búsqueda solicitada
            query = f"{song.title} {artist_name} oficial OR lyric video"
            print(f"[?] Buscando: \"{query}\"")
            
            youtube_id = search_youtube_id(query)
            
            if youtube_id:
                # Actualizar las columnas solicitadas
                song.youtube_url_id = youtube_id
                song.preview_start_time_sec = 45.0
                
                # Commit individual para guardar el progreso incluso si el script falla más adelante
                db.commit()
                print(f"[+] Encontrado ID: {youtube_id} -> Guardado con start_time: 45s.\n")
            else:
                print(f"[-] Error: No encontrado para '{song.title} - {artist_name}'\n")
                
    except Exception as e:
        print(f"[-] Error fatal en el pipeline: {e}")
    finally:
        db.close()
        print("[*] Proceso ETL de YouTube finalizado.")

if __name__ == "__main__":
    run_pipeline()
