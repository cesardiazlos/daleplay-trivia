import os
import json
import time
from dotenv import load_dotenv

# Imports de Gemini
from google import genai
from google.genai import types

# Imports de BD
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Song

# Cargar variables de entorno
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("No se encontró GEMINI_API_KEY en el archivo .env")

# Inicialización con el nuevo SDK
client = genai.Client(api_key=GEMINI_API_KEY)

def fix_historical_years():
    db: Session = SessionLocal()
    try:
        songs = db.query(Song).all()
        total_songs = len(songs)
        print(f"[*] Se encontraron {total_songs} canciones para corregir.")

        batch_size = 50
        for i in range(0, total_songs, batch_size):
            batch = songs[i:i+batch_size]
            print(f"\n{'-'*50}")
            print(f"[*] Procesando lote {i//batch_size + 1} (canciones {i+1} a {min(i+batch_size, total_songs)})...")
            
            song_list_text = "\n".join([
                f"ID: {song.id} | Canción: {song.title} | Artista: {song.artist.name if song.artist else 'Desconocido'}" 
                for song in batch
            ])
            
            PROMPT = f"""
Eres un experto historiador musical con rigor enciclopédico. Te daré una lista de canciones con sus IDs internos de base de datos.
Tu tarea es identificar el AÑO ORIGINAL DE LANZAMIENTO de cada canción (el año exacto en que el sencillo o álbum original vio la luz por primera vez).

REGLA DE ORO: Ignora por completo años de remasterizaciones, reediciones, versiones "Live" o compilaciones. Queremos el año de nacimiento de la canción.

LISTA DE CANCIONES:
{song_list_text}

Debes devolver ÚNICAMENTE un arreglo JSON con esta estructura exacta:
[{{
    "id": <ID numérico de la canción tal cual se te entregó>,
    "correct_year": <Año original de lanzamiento en formato YYYY numérico>
}}]
"""
            
            # --- SISTEMA DE REINTENTOS AUTOMÁTICOS ---
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model='gemini-3.1-flash-lite-preview',
                        contents=PROMPT,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )
                    
                    raw_text = response.text.strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3]
                        
                    data = json.loads(raw_text.strip())
                    
                    if isinstance(data, list):
                        updated_count = 0
                        same_count = 0
                        
                        for item in data:
                            song_id = item.get('id') or item.get('ID')
                            correct_year = item.get('correct_year') or item.get('year')
                            
                            if song_id is not None and correct_year is not None:
                                song_to_update = next((s for s in batch if str(s.id) == str(song_id)), None)
                                
                                if song_to_update:
                                    new_year = int(correct_year)
                                    old_year = song_to_update.release_year
                                    
                                    if old_year != new_year:
                                        print(f"  [CORRECCIÓN] {song_to_update.title}: {old_year} -> {new_year}")
                                        song_to_update.release_year = new_year
                                        updated_count += 1
                                    else:
                                        same_count += 1
                                else:
                                    print(f"  [?] ID no encontrado en lote: {song_id}")
                            else:
                                print(f"  [?] JSON incompleto de Gemini: {item}")
                                    
                        db.commit()
                        print(f"[+] Resumen del lote: {updated_count} corregidos, {same_count} ya estaban correctos.")
                        break # <-- Si el código llega aquí, fue un éxito. Rompe el ciclo de reintentos.
                    
                    else:
                        print("[-] Error: La respuesta no es una lista válida.")
                        raise ValueError("Estructura JSON incorrecta")
                        
                except Exception as e:
                    db.rollback()
                    print(f"[-] Error en intento {attempt + 1} de {max_retries}: {e}")
                    if attempt < max_retries - 1:
                        print("[*] Servidor saturado. Esperando 30 segundos para reintentar el mismo lote...")
                        time.sleep(30) # Pausa larga solo cuando hay error
                    else:
                        print("[-] Lote saltado definitivamente tras múltiples fallos continuos.")
            
            # Pausa normal y saludable de 10 segundos entre cada lote exitoso
            print("[*] Pausando 10 segundos para cuidar el Rate Limit de la API...")
            time.sleep(10)
            
        print("\n[+] ¡PROCESO FINALIZADO!")
        
    except Exception as e:
        print(f"[-] Error fatal: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_historical_years()
    