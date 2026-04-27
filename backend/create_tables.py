from database import engine, Base
import models # Esto asegura que los modelos se lean

print("Creando tablas en AWS RDS...")
Base.metadata.create_all(bind=engine)
print("¡Tablas creadas con éxito!")