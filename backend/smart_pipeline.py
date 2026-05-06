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

def generate_songs_with_gemini(concept: str, qty: int):
    print(f"[*] Solicitando a Gemini la generación de {qty} canciones...")
    
    all_songs = []
    batch_size = 50
    remaining = qty
    
    while remaining > 0:
        current_qty = min(remaining, batch_size)
        
        PROMPT_TEMPLATE = f"""
Eres un curador musical implacable y de alto rigor. Debes generar una lista de {current_qty} canciones DIFERENTES que cumplan ESTRICTAMENTE con este concepto:
"{concept}"

REGLAS DE ORO:
- CERO TOLERANCIA A LAS ALUCINACIONES: Si el concepto exige un tipo de grupo (ej. hermanos), está ESTRICTAMENTE PROHIBIDO incluir solistas o bandas genéricas solo para rellenar.
- Si no conoces suficientes canciones que cumplan al 100% el criterio, es preferible que devuelvas una lista más corta (ej. 15 en vez de 50) antes que incluir artistas que no corresponden.
- Debes devolver ÚNICAMENTE un arreglo JSON puro, sin markdown, sin texto antes ni después.

NUEVA ESTRUCTURA DEL JSON (Añade el campo 'justification'):
[{{
  "song": "Nombre", 
  "artist": "Nombre", 
  "justification": "Explica en 1 oración corta por qué este artista cumple EXACTAMENTE con el concepto exigido", 
  "entity_type": "Individual" o "Grupo", 
  "gender": "Masculino" o "Femenino" o "Mixto" o "Desconocido", 
  "main_genre": "Género musical principal"
}}]

Reglas para los campos:
- 'entity_type' debe ser exactamente "Individual" o "Grupo".
- 'gender' debe ser exactamente "Masculino", "Femenino", "Mixto" o "Desconocido". (Nota: "Mixto" solo es válido si entity_type es "Grupo").
"""
        
        try:
            # Llamada con el nuevo SDK de Gemini
            response = client.models.generate_content(
                model='gemini-3.1-flash-lite-preview',
                contents=PROMPT_TEMPLATE,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            
            data = json.loads(response.text.strip())
            if isinstance(data, list):
                all_songs.extend(data)
            else:
                print("[-] Gemini no devolvió una lista JSON válida en este lote.")
        except Exception as e:
            print(f"[-] Error al consultar a Gemini: {e}")
            
        remaining -= current_qty
        if remaining > 0:
            print(f"[*] Pausando para no saturar la API (quedan {remaining} canciones por generar)...")
            time.sleep(5)
            
    print(f"[+] Total de canciones generadas por Gemini: {len(all_songs)}")
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
        excluded_words = ["live", "en vivo", "remix", "acoustic", "karaoke"]
        
        print("\n[*] Iniciando Fase 2 y 3: Búsqueda en Spotify e Ingesta en Base de Datos...")
        for idx, item in enumerate(songs_data, 1):
            song_name = item.get("song", "")
            artist_name = item.get("artist", "")
            
            if not song_name or not artist_name:
                continue
                
            query = f"track:{song_name} artist:{artist_name}"
            
            try:
                results = sp.search(q=query, type='track', limit=5)
                tracks = results.get('tracks', {}).get('items', [])
                
                valid_track = None
                for track in tracks:
                    # Filtro: Palabras prohibidas (Eliminamos validación preview_url aquí)
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
                release_date = valid_track.get('album', {}).get('release_date', '')
                release_year = int(release_date.split('-')[0]) if release_date else 0
                
                # Prevenir duplicados de canción globalmente
                existing_song = db.query(Song).filter(Song.spotify_id == spotify_id).first()
                if existing_song:
                    if category not in existing_song.categories:
                        existing_song.categories.append(category)
                        db.commit()
                    print(f"[*] {idx}/{total_songs} Ya existe: '{valid_track.get('name')}' vinculado a categoría.")
                    continue
                
                # Upsert de Artista extrayendo datos generados por Gemini
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
                
                # Crear Canción en BD
                new_song = Song(
                    title=valid_track.get('name'),
                    artist_id=artist.id,
                    release_year=release_year,
                    spotify_id=spotify_id
                )
                new_song.categories.append(category)
                db.add(new_song)
                db.commit()
                
                loaded_count += 1
                print(f"[+] {idx}/{total_songs} Cargado: '{valid_track.get('name')} - {artist_name}'")
                
            except Exception as loop_e:
                db.rollback()
                print(f"[-] Error al procesar track '{song_name}': {loop_e}")
                
        print(f"\n[*] Proceso finalizado. Se lograron ingresar {loaded_count} canciones válidas nuevas a la categoría '{category_name}'.")

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
    
    print("[*] Iniciando Smart Pipeline...")
    generated_songs = generate_songs_with_gemini(args.concept, args.qty)
    
    if generated_songs:
        filter_and_ingest(generated_songs, args.category_name)
    else:
        print("[-] Abortando ingesta. La IA no pudo generar las canciones solicitadas.")
