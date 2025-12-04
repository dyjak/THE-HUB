from sqlalchemy.orm import Session
from .connection import SessionLocal, engine, Base
from ..auth.models import User

def seed_users():
    db = SessionLocal()
    try:
        # Sprawdź czy są już użytkownicy w bazie
        users_count = db.query(User).count()
        if users_count > 0:
            print(f"Baza danych zawiera już {users_count} użytkowników. Pomijam tworzenie testowych użytkowników.")
            return

        # Lista testowych użytkowników (nazwa, PIN)
        test_users = [
            ("admin", "123456"),
            ("user1", "654321"),
            ("user2", "111111"),
        ]

        # Dodaj użytkowników do bazy
        for username, pin in test_users:
            user = User(
                username=username,
                pin_hash=User.hash_pin(pin),
                pin_plain=pin  # DODANE - zapisz PIN w plain text dla unikalności
            )
            db.add(user)

        db.commit()
        print(f"Dodano {len(test_users)} testowych użytkowników do bazy danych.")
        print("\nTestowi użytkownicy:")
        for username, pin in test_users:
            print(f"  - {username} / PIN: {pin}")

    except Exception as e:
        print(f"Błąd podczas tworzenia użytkowników: {e}")
        db.rollback()
    finally:
        db.close()

def reset_users():
    """Usuwa wszystkich użytkowników z bazy - użyj ostrożnie!"""
    db = SessionLocal()
    try:
        count = db.query(User).count()
        db.query(User).delete()
        db.commit()
        print(f"✓ Usunięto {count} użytkowników z bazy danych.")
    except Exception as e:
        print(f"❌ Błąd podczas usuwania użytkowników: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    
    # Upewnij się, że tabele istnieją
    Base.metadata.create_all(bind=engine)
    
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        print("⚠️  RESETOWANIE UŻYTKOWNIKÓW...")
        reset_users()
        seed_users()
    else:
        seed_users()