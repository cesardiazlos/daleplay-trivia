import os
import sys
import json
import uuid
import time
import argparse
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

# Nuevos imports de Gemini
from google import genai
from google.genai import types

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Category, Artist, Song, EntityTypeEnum

# Cargar variables de entorno
load_dotenv()

# Configurar API de Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("No se encontró GEMINI_API_KEY en el archivo .env")

# Inicialización con el nuevo SDK
client = genai.Client(api_key=GEMINI_API_KEY)

# Configurar cliente de Spotify
try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())
except Exception as e:
    print(f"[-] Error al autenticar con Spotify: {e}")
    sys.exit(1)

def get_existing_songs(category_name: str) -> list:
    """Extrae las canciones que ya existen en la categoría para pasárselas a Gemini como exclusión."""
    db: Session = SessionLocal()
    excludes = []
    try:
        category = db.query(Category).filter(Category.name == category_name).first()
        if category:
            for song in category.songs:
                artist_name = song.artist.name if song.artist else "Desconocido"
                excludes.append(f"- {artist_name}: {song.title}")
    except Exception as e:
        print(f"[-] Error al leer la base de datos para exclusiones: {e}")
    finally:
        db.close()
    return excludes

def generate_songs_with_gemini(concept: str, qty: int, existing_excludes: list = None):
    print(f"[*] Solicitando a Gemini la generación de {qty} canciones NUEVAS...")
    
    all_songs = []
    batch_size = 50
    remaining = qty
    
    # Lista normal para el prompt (texto completo)
    current_excludes = list(existing_excludes) if existing_excludes else []
    
    # --- NUEVA LÓGICA DE LIMPIEZA ANTI-DUPLICADOS ---
    def simplify(text):
        # Pasa a minúsculas y corta en el primer '(', '[' o '-' para eliminar el texto extra de Spotify
        import re
        return re.split(r'\(|\[|\-', str(text).lower())[0].strip()

    # Pre-procesamos la lista de la BD para tener llaves base y limpias
    current_excludes_clean = set()
    for ex in current_excludes:
        parts = ex.replace("- ", "", 1).split(":", 1)
        if len(parts) == 2:
            a_clean = simplify(parts[0])
            s_clean = simplify(parts[1])
            current_excludes_clean.add(f"{a_clean}|{s_clean}")
            
    consecutive_zeros = 0
    
    while remaining > 0:
        current_qty = min(remaining + 10, batch_size) 
        forbidden_list_text = "\n".join(current_excludes) if current_excludes else "Ninguna por ahora."
        
        PROMPT_TEMPLATE = f"""
Eres un curador musical implacable y de alto rigor. Debes generar una lista de {current_qty} canciones DIFERENTES que cumplan ESTRICTAMENTE con este concepto:
"{concept}"

REGLAS DE ORO:
- CERO TOLERANCIA A LAS ALUCINACIONES: Si el concepto exige un tipo de grupo (ej. hermanos), está ESTRICTAMENTE PROHIBIDO incluir solistas o bandas genéricas solo para rellenar.
- AÑO ORIGINAL OBLIGATORIO: Debes incluir el año ORIGINAL de lanzamiento de la canción. No uses el año de reediciones, remasterizaciones ni álbumes de grandes éxitos. Solo el año en que la canción vio la luz por primera vez.
- Debes devolver ÚNICAMENTE un arreglo JSON puro, sin markdown, sin texto antes ni después.

CANCIONES PROHIBIDAS (Ya existen en tu base de datos. IGNORA ESTAS CANCIONES POR COMPLETO Y BUSCA OTRAS):
{forbidden_list_text}

NUEVA ESTRUCTURA DEL JSON:
[{{
  "song": "Nombre", 
  "artist": "Nombre", 
  "release_year": YYYY,
  "justification": "Explica en 1 oración corta por qué este artista cumple EXACTAMENTE con el concepto exigido", 
  "entity_type": "Individual" o "Grupo", 
  "gender": "Masculino" o "Femenino" o "Mixto" o "Desconocido", 
  "main_genre": "Género musical principal"
}}]

Reglas para los campos:
- 'release_year' debe ser el año numérico (ej: 1985).
- 'entity_type' debe ser exactamente "Individual" o "Grupo".
- 'gender' debe ser exactamente "Masculino", "Femenino", "Mixto" o "Desconocido".
"""
        
        try:
            response = client.models.generate_content(
                model='gemini-3.1-flash-lite-preview',
                contents=PROMPT_TEMPLATE,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.6 # Aumentado ligeramente para forzar más exploración
                )
            )
            
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
                
            data = json.loads(raw_text.strip())
            
            if isinstance(data, list):
                novel_count = 0
                for item in data:
                    song_name = item.get('song', '')
                    artist_name = item.get('artist', '')
                    
                    # Limpiamos los datos que devuelve la IA
                    gemini_a_clean = simplify(artist_name)
                    gemini_s_clean = simplify(song_name)
                    
                    # Búsqueda Flexible
                    is_duplicate = False
                    for ex_clean in current_excludes_clean:
                        ex_a, ex_s = ex_clean.split("|")
                        # Verifica si la canción limpia o el artista limpio están contenidos uno dentro del otro
                        if (gemini_s_clean in ex_s or ex_s in gemini_s_clean) and \
                           (gemini_a_clean in ex_a or ex_a in gemini_a_clean):
                            is_duplicate = True
                            break
                            
                    if not is_duplicate:
                        all_songs.append(item)
                        current_excludes.append(f"- {artist_name}: {song_name}")
                        current_excludes_clean.add(f"{gemini_a_clean}|{gemini_s_clean}")
                        novel_count += 1
                        
                        if novel_count >= remaining:
                            break
                            
                print(f"[*] La IA devolvió {len(data)} canciones. Python filtró los repetidos y rescató {novel_count} totalmente NUEVAS.")
                remaining -= novel_count
                
                if novel_count == 0:
                    consecutive_zeros += 1
                    if consecutive_zeros >= 2:
                        print("\n[!] ALERTA: La IA ha agotado su conocimiento sobre esta categoría.")
                        print(f"[*] Forzando la salida. Avanzando con las {len(all_songs)} canciones recolectadas.\n")
                        break
                else:
                    consecutive_zeros = 0 
                
            else:
                print("[-] Gemini no devolvió una lista JSON válida en este lote.")
                
        except Exception as e:
            print(f"[-] Error al consultar a Gemini: {e}")
            
        if remaining > 0 and consecutive_zeros < 2:
            print(f"[*] Aún faltan {remaining} canciones nuevas. Reintentando en 10 segundos...")
            time.sleep(10)
            
    print(f"[+] Total de canciones NUEVAS generadas exitosamente: {len(all_songs)}")
    return all_songs

def filter_and_ingest(songs_data: list, category_name: str):
    db: Session = SessionLocal()
    try:
        # 1. Obtener o crear Categoría
        category = db.query(Category).filter(Category.name == category_name).first()
        if not category:
            spotify_playlist_id = f"custom_cat_{uuid.uuid4().hex[:12]}"
            category = Category(name=category_name, spotify_playlist_id=spotify_playlist_id)
            db.add(category)
            db.commit()
            db.refresh(category)
            print(f"[+] Categoría '{category_name}' creada exitosamente.")
            
        loaded_count = 0
        total_songs = len(songs_data)
        
        # Palabras excluidas en el título
        excluded_words = ["live", "en vivo", "remix", "acoustic", "karaoke", "remaster", "remasterizado","cover"]
        
        print("\n[*] Iniciando Fase 2 y 3: Búsqueda en Spotify e Ingesta en Base de Datos...")
        for idx, item in enumerate(songs_data, 1):
            song_name = item.get("song", "")
            artist_name = item.get("artist", "")
            release_year_ia = int(item.get("release_year", 0)) # <--- Agregar esta línea
            
            if not song_name or not artist_name:
                continue
                
            # --- NUEVO CÓDIGO (MÁS INTELIGENTE Y FLEXIBLE) ---
            # Búsqueda de texto libre: mucho más efectiva para evadir problemas de tildes o colaboraciones
            query = f"{song_name} {artist_name}"
            
            try:
                results = sp.search(q=query, type='track', limit=10)
                tracks = results.get('tracks', {}).get('items', [])
                
                valid_track = None
                for track in tracks:
                    # Filtro: Palabras prohibidas
                    t_name = track.get('name', '').lower()
                    if any(word in t_name for word in excluded_words):
                        continue
                        
                    # Cumple con todo
                    valid_track = track
                    break
                    
                if not valid_track:
                    print(f"[-] {idx}/{total_songs} Saltado: '{song_name} - {artist_name}' (Es versión Live/Remix o no se halló en Spotify)")
                    continue
                
                spotify_id = valid_track.get('id')
                track_name = valid_track.get('name')
                
                # --- 1. UPSERT DEL ARTISTA (Lo movemos ARRIBA) ---
                # Necesitamos el ID del artista primero para poder verificar si la canción ya existe
                artist = db.query(Artist).filter(Artist.name == artist_name).first()
                if not artist:
                    e_type_str = item.get("entity_type", "Individual")
                    e_type = EntityTypeEnum.Grupo if e_type_str == "Grupo" else EntityTypeEnum.Individual
                    
                    artist = Artist(
                        name=artist_name,
                        entity_type=e_type,
                        gender=item.get("gender", "Desconocido"),
                        main_genre=item.get("main_genre", "Desconocido")
                    )
                    db.add(artist)
                    db.commit()
                    db.refresh(artist)

                # --- 2. DOBLE CAPA DE SEGURIDAD ANTI-DUPLICADOS ---
                # A) Verificamos si existe por el ID exacto de Spotify...
                existing_song = db.query(Song).filter(Song.spotify_id == spotify_id).first()
                
                # B) ...Y si no, verificamos si este Artista ya tiene una canción con este mismo Nombre
                if not existing_song:
                    existing_song = db.query(Song).filter(
                        Song.title == track_name,
                        Song.artist_id == artist.id
                    ).first()

                if existing_song:
                    # AQUÍ OCURRE EL ENRIQUECIMIENTO: Si ya existe, solo la vinculamos a la categoría
                    if category not in existing_song.categories:
                        existing_song.categories.append(category)
                        db.commit()
                        loaded_count += 1
                        print(f"[+] {idx}/{total_songs} Vinculada: '{track_name}' a la categoría actual.")
                    else:
                        print(f"[*] {idx}/{total_songs} Ya existe: '{track_name}' en esta categoría.")
                    continue
                
                # --- 3. CREAR CANCIÓN NUEVA EN BD ---
                new_song = Song(
                    title=track_name,
                    artist_id=artist.id,
                    release_year=release_year_ia,
                    spotify_id=spotify_id
                )
                new_song.categories.append(category)
                db.add(new_song)
                db.commit()
                
                loaded_count += 1
                print(f"[+] {idx}/{total_songs} Cargado: '{track_name} - {artist_name}' (Año: {release_year_ia})")
                
            except Exception as loop_e:
                db.rollback()
                print(f"[-] Error al procesar track '{song_name}': {loop_e}")
                
        print(f"\n[*] Proceso finalizado. Se lograron vincular/ingresar {loaded_count} canciones válidas a la categoría '{category_name}'.")

    except Exception as e:
        print(f"[-] Error fatal en base de datos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Pipeline para generar e ingerir canciones usando Gemini y Spotify.")
    parser.add_argument("--concept", type=str, required=True, help="Concepto descriptivo de la lista de canciones a crear.")
    parser.add_argument("--category_name", type=str, required=True, help="Nombre oficial de la categoría en la DB.")
    parser.add_argument("--qty", type=int, required=True, help="Cantidad objetivo aproximada de canciones a procesar.")
    
    args = parser.parse_args()
    
    print("[*] Verificando base de datos para evitar duplicados y enriquecer...")
    existing_excludes = get_existing_songs(args.category_name)
    if existing_excludes:
        print(f"[*] La categoría '{args.category_name}' ya tiene {len(existing_excludes)} canciones. Se instruirá a la IA para buscar material NUEVO.")
    else:
        print(f"[*] Creando nueva categoría '{args.category_name}' o la categoría actual está vacía.")
    
    print("\n[*] Iniciando Smart Pipeline...")
    generated_songs = generate_songs_with_gemini(args.concept, args.qty, existing_excludes)
    
    if generated_songs:
        filter_and_ingest(generated_songs, args.category_name)
    else:
        print("[-] Abortando ingesta. La IA no pudo generar las canciones solicitadas.")
        