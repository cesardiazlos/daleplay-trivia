import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Construir la URL de conexión a PostgreSQL
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "daleplay")

DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Intentar crear el motor de SQLAlchemy con Fallback
try:
    if DATABASE_URL.startswith("sqlite"):
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=False)
    else:
        engine = create_engine(DATABASE_URL, echo=False)
        # Probamos la conexión para que salte al except si AWS no responde
        with engine.connect() as conn:
            pass
except Exception as e:
    print(f"Error conectando a PostgreSQL ({DB_HOST}): {e}")
    print("Realizando fallback automático a SQLite local...")
    DATABASE_URL = "sqlite:///./daleplay.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=False)

# Crear la fábrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base para los modelos declarativos (SQLAlchemy 2.0)
class Base(DeclarativeBase):
    pass

# Dependencia para obtener una sesión de base de datos en FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
