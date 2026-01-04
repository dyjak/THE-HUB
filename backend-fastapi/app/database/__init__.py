"""database: konfiguracja połączenia i narzędzia pomocnicze.

pakiet zawiera:
- `connection.py`: engine, sessionmaker i `get_db()` do użycia w fastapi
- skrypty narzędziowe do migracji/seedowania i dodawania użytkownika
"""

from .connection import Base, engine, SessionLocal, get_db

__all__ = ["Base", "engine", "SessionLocal", "get_db"]