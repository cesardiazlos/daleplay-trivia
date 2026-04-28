import sys
import yt_dlp
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Song, Artist

def search_youtube_id(query: str) -> str:
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # ytsearch1: busca el primer resultado en YouTube
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if 'entries' in info and len(info['entries']) > 0:
                return info['entries'][0]['id']
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
            query = f"{song.title} {artist_name} official audio"
            print(f"[?] Buscando: \"{song.title} - {artist_name}\"")
            
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
