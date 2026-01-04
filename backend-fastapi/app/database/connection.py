"""połączenie z bazą danych (sqlalchemy).

aktualnie używany jest sqlite (plik `users.db`).
moduł udostępnia:
- `engine`
- `SessionLocal`
- `Base` dla deklaratywnych modeli
- dependency `get_db()` do użycia w fastapi
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./users.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """fastapi dependency: zwraca sesję bazy i zamyka ją po użyciu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()