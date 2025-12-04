from .connection import engine, Base

if __name__ == "__main__":
    # Upewnij się, że tabele istnieją; brak automatycznego dodawania użytkowników
    Base.metadata.create_all(bind=engine)
    print("Struktura bazy danych została zainicjalizowana (tabele istnieją).")