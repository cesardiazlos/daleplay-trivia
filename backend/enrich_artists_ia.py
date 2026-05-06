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

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

PROMPT_TEMPLATE = """
Eres un experto en la industria musical. Necesito que clasifiques la siguiente lista de artistas musicales.
Para cada artista, devuelve un objeto JSON con los campos 'id', 'gender' y 'main_genre'.

REGLA ESTRICTA PARA 'gender':
Debes clasificar al artista usando ESTRICTAMENTE una de las siguientes etiquetas exactas:
- Solista Masculino
- Solista Femenino
- Grupo Masculino
- Grupo Femenino
- Dúo Masculino
- Dúo Femenino
- Dúo Mixto
- Banda (Voz Masculina)
- Banda (Voz Femenina)
- Banda (Voz Mixta)

REGLA PARA 'main_genre':
Asigna el género musical principal más representativo (ej: Reggaetón, Rock, Pop, Balada, Trap, Cumbia, Salsa, etc.).

La lista de artistas es la siguiente:
{artists_data}

Devuelve ÚNICAMENTE un array JSON puro, sin markdown, sin backticks y sin texto adicional.
Ejemplo de salida esperada:
[
  {{"id": "uuid-1", "gender": "Grupo Femenino", "main_genre": "Pop"}},
  {{"id": "uuid-2", "gender": "Solista Masculino", "main_genre": "Reggaetón"}}
]
"""

def enrich_artists():
    db: Session = SessionLocal()
    try:
        # Extraer artistas que necesitan actualización
        # gender es 'N/A' o nulo, O main_genre es 'Desconocido' o nulo
        artists_to_update = db.query(Artist).filter(
            (Artist.gender == 'N/A') | 
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
            
            # Preparar datos para el prompt
            artists_data = []
            for artist in batch:
                artists_data.append(f"ID: {artist.id} | Nombre: {artist.name}")
            
            prompt = PROMPT_TEMPLATE.format(artists_data="\n".join(artists_data))
            
            try:
                # Llamada a Gemini
                response = model.generate_content(prompt)
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
                        
                        # Nota: Si tu base de datos tiene `gender` definido como Enum en SQLAlchemy 
                        # y en PostgreSQL, asegúrate de que soporta estas nuevas cadenas, 
                        # de lo contrario, tendrás que migrar el tipo de columna a String.
                        artist.gender = data.get("gender", artist.gender)
                        artist.main_genre = data.get("main_genre", artist.main_genre)
                        updated_count += 1
                
                db.commit()
                print(f"[+] Lote actualizado exitosamente. ({updated_count} artistas actualizados)")
                
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
