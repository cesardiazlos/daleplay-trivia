from sqlalchemy import text
from database import engine

def migrate():
    with engine.begin() as conn:
        print(f"[*] Base de datos detectada: {engine.name}")
        
        if engine.name == 'postgresql':
            print("[*] Ejecutando alteración de columna para PostgreSQL...")
            # Convierte la columna Enum a VARCHAR, manteniendo los valores de texto
            conn.execute(text("ALTER TABLE artists ALTER COLUMN gender TYPE VARCHAR USING gender::text;"))
            
            # Elimina el tipo Enum nativo de la base de datos
            conn.execute(text("DROP TYPE IF EXISTS genderenum CASCADE;"))
            print("[+] Migración en PostgreSQL completada. La columna 'gender' ahora es un VARCHAR estándar.")
            
        elif engine.name == 'sqlite':
            print("[*] SQLite no utiliza tipos Enum nativos, internamente ya es VARCHAR.")
            print("[+] No es necesaria ninguna acción estructural en SQLite.")
        else:
            print(f"[-] Motor de base de datos no reconocido para la migración directa: {engine.name}")

if __name__ == "__main__":
    try:
        migrate()
        print("[*] Script finalizado exitosamente.")
    except Exception as e:
        print(f"[-] Ocurrió un error durante la migración: {e}")
