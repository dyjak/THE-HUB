from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .auth import router as auth_router
from .users import router as users_router
from sqlalchemy.orm import Session
from .models import User

app = FastAPI()

# Konfiguracja CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[""
                   "http://localhost:3000"],
                   #"https://the-hub-sand.vercel.app/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upewnij się, że tabele są utworzone
Base.metadata.create_all(bind=engine)


# Funkcja do tworzenia testowych użytkowników
def seed_users():
    from .database import SessionLocal
    db = SessionLocal()
    try:
        # Sprawdź czy są już użytkownicy w bazie
        users_count = db.query(User).count()
        if users_count > 0:
            print(f"Baza danych zawiera już {users_count} użytkowników.")
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


# Wywołaj seeder przy starcie aplikacji
seed_users()

# Dodaj routery
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")