from sqlalchemy import text
from database import engine

def migrate():
    with engine.begin() as conn:
        print(f"[*] Base de datos detectada: {engine.name}")
        print("[*] Ejecutando actualización de entity_type en la tabla artists...")
        
        if engine.name == 'postgresql':
            # En PostgreSQL, entity_type es un tipo Enum estricto. Primero debemos añadir el nuevo valor 'Grupo'.
            try:
                conn.execute(text("ALTER TYPE entitytypeenum ADD VALUE IF NOT EXISTS 'Grupo';"))
                print("[+] Valor 'Grupo' añadido al Enum en PostgreSQL.")
            except Exception as e:
                print(f"[*] Nota al intentar alterar Enum: {e}")
                
            # Actualizamos los registros existentes
            result = conn.execute(text("UPDATE artists SET entity_type = 'Grupo' WHERE entity_type = 'Group';"))
            print(f"[+] {result.rowcount} registros actualizados de 'Group' a 'Grupo'.")
            
        elif engine.name == 'sqlite':
            # SQLite trata los Enums internamente como VARCHAR
            result = conn.execute(text("UPDATE artists SET entity_type = 'Grupo' WHERE entity_type = 'Group';"))
            print(f"[+] {result.rowcount} registros actualizados de 'Group' a 'Grupo' en SQLite.")
            
        else:
            print(f"[-] Motor de base de datos no reconocido: {engine.name}")

if __name__ == "__main__":
    try:
        migrate()
        print("[*] Script de migración de entity_type finalizado exitosamente.")
    except Exception as e:
        print(f"[-] Ocurrió un error durante la migración: {e}")
