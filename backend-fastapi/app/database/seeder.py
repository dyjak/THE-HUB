"""inicjalizacja struktury bazy (seed/migrate-lite).

ten plik tworzy tabele na podstawie `Base.metadata`.
nie dodaje automatycznie użytkowników — to jest tylko bootstrap struktury.
"""

from .connection import engine, Base

if __name__ == "__main__":
    # Upewnij się, że tabele istnieją; brak automatycznego dodawania użytkowników
    Base.metadata.create_all(bind=engine)
    print("Struktura bazy danych została zainicjalizowana (tabele istnieją).")