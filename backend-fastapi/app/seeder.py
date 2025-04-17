# seeder.py
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import User


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
                pin_hash=User.hash_pin(pin)
            )
            db.add(user)

        db.commit()
        print(f"Dodano {len(test_users)} testowych użytkowników do bazy danych.")

    except Exception as e:
        print(f"Błąd podczas tworzenia użytkowników: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    # Upewnij się, że tabele istnieją
    Base.metadata.create_all(bind=engine)
    seed_users()