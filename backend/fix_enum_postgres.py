from sqlalchemy import text
from database import engine

def fix_enum():
    if engine.name == 'postgresql':
        print("[*] Conectando a PostgreSQL en modo AUTOCOMMIT para alterar el Enum...")
        # ALTER TYPE ADD VALUE no puede ejecutarse dentro de un bloque de transacción.
        # execution_options(isolation_level="AUTOCOMMIT") desactiva la transacción explícita.
        with engine.execution_options(isolation_level="AUTOCOMMIT").begin() as conn:
            try:
                conn.execute(text("ALTER TYPE entitytypeenum ADD VALUE IF NOT EXISTS 'Grupo';"))
                print("[+] Valor 'Grupo' añadido al Enum exitosamente.")
            except Exception as e:
                print(f"[-] Error al intentar alterar Enum: {e}")
                
            try:
                result = conn.execute(text("UPDATE artists SET entity_type = 'Grupo' WHERE entity_type = 'Group';"))
                print(f"[+] {result.rowcount} registros actualizados de 'Group' a 'Grupo'.")
            except Exception as e:
                print(f"[-] Error al actualizar registros: {e}")
    else:
        print("[*] No estás usando PostgreSQL, no hay cambios de Enum pendientes.")

if __name__ == "__main__":
    fix_enum()
