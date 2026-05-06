import os
import json
import time
from dotenv import load_dotenv
import google.generativeai as genai
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Artist

# Cargar variables de entorno
load_dotenv()

# Configurar API de Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("No se encontró GEMINI_API_KEY en el archivo .env")

genai.configure(api_key=GEMINI_API_KEY)

# Configurar el modelo, pidiendo explicitamente JSON
generation_config = {
  "temperature": 0.1,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
  "response_mime_type": "application/json",
}

model_primary = genai.GenerativeModel(
    model_name="gemini-3.1-flash-lite-preview",
    generation_config=generation_config,
)

model_fallback = genai.GenerativeModel(
    model_name="gemini-3-flash-preview",
    generation_config=generation_config,
)

PROMPT_TEMPLATE = """
Eres un experto en la industria musical. Necesito que clasifiques la siguiente lista de artistas musicales.
Para cada artista, devuelve un objeto JSON con los campos 'id', 'entity_type', 'gender' y 'main_genre'.

REGLAS ESTRICTAS PARA 'entity_type':
- Individual
- Grupo

REGLAS ESTRICTAS PARA 'gender':
- Masculino
- Femenino
- Mixto (Esta opción SOLO aplica si el entity_type es "Grupo")
- Desconocido

REGLA PARA 'main_genre':
Asigna el género musical principal más representativo (ej: Reggaetón, Rock, Pop, Balada, Trap, Cumbia, Salsa, etc.).

La lista de artistas es la siguiente:
{artists_data}

Devuelve ÚNICAMENTE un array JSON puro, sin markdown, sin backticks y sin texto adicional.
Ejemplo de salida esperada:
[
  {{"id": "uuid-1", "entity_type": "Grupo", "gender": "Femenino", "main_genre": "Pop"}},
  {{"id": "uuid-2", "entity_type": "Individual", "gender": "Masculino", "main_genre": "Reggaetón"}}
]
"""

def enrich_artists():
    db: Session = SessionLocal()
    try:
        # Extraer artistas que necesitan actualización
        # gender es 'NA' o nulo, O main_genre es 'Desconocido' o nulo
        artists_to_update = db.query(Artist).filter(
            (Artist.gender == 'NA') | 
            (Artist.gender.is_(None)) | 
            (Artist.main_genre == 'Desconocido') | 
            (Artist.main_genre.is_(None))
        ).all()

        total_artists = len(artists_to_update)
        print(f"[*] Se encontraron {total_artists} artistas pendientes de enriquecimiento.")

        if total_artists == 0:
            print("[*] Nada que actualizar.")
            return

        batch_size = 50
        
        for i in range(0, total_artists, batch_size):
            batch = artists_to_update[i : i + batch_size]
            
            print(f"\n[*] Procesando lote {i//batch_size + 1} de {(total_artists + batch_size - 1)//batch_size} (Artistas {i+1} al {min(i+batch_size, total_artists)})...")
            start_time = time.time()
            
            # Preparar datos para el prompt
            artists_data = []
            for artist in batch:
                artists_data.append(f"ID: {artist.id} | Nombre: {artist.name}")
            
            prompt = PROMPT_TEMPLATE.format(artists_data="\n".join(artists_data))
            
            try:
                # Llamada a Gemini (Modelo principal)
                try:
                    response = model_primary.generate_content(prompt)
                    response_text = response.text.strip()
                except Exception as model_err:
                    print(f"[-] Modelo principal falló: {model_err}. Intentando con modelo de respaldo...")
                    response = model_fallback.generate_content(prompt)
                    response_text = response.text.strip()
                
                # Parsear el JSON
                enriched_data = json.loads(response_text)
                
                # Crear un diccionario para fácil acceso por ID
                enriched_dict = {item["id"]: item for item in enriched_data}
                
                # Actualizar la base de datos
                updated_count = 0
                for artist in batch:
                    str_id = str(artist.id)
                    if str_id in enriched_dict:
                        data = enriched_dict[str_id]
                        
                        # Nota: Asegúrate de que 'entity_type' esté actualizado en la DB
                        artist.entity_type = data.get("entity_type", artist.entity_type)
                        artist.gender = data.get("gender", artist.gender)
                        artist.main_genre = data.get("main_genre", artist.main_genre)
                        updated_count += 1
                
                db.commit()
                end_time = time.time()
                elapsed_time = round(end_time - start_time, 2)
                print(f"[+] Lote completado en {elapsed_time} segundos. ({updated_count} artistas actualizados)")
                
            except json.JSONDecodeError as e:
                db.rollback()
                print(f"[-] Error al parsear JSON de Gemini: {e}")
                print(f"Respuesta cruda: {response_text}")
            except Exception as e:
                db.rollback()
                print(f"[-] Error durante el procesamiento del lote (Posible límite de cuota o error de BD): {e}")
                print("Esperando 10 segundos antes de continuar...")
                time.sleep(10)
                
    except Exception as e:
        print(f"[-] Error fatal: {e}")
    finally:
        db.close()
        print("\n[*] Proceso finalizado.")

if __name__ == "__main__":
    enrich_artists()
