from getpass import getpass

from .connection import SessionLocal
from ..auth.models import User


def prompt_new_user() -> None:
    db = SessionLocal()
    try:
        print("Dodawanie nowego użytkownika do bazy")
        username = input("Nazwa użytkownika: ").strip()
        if not username:
            print("Nazwa użytkownika nie może być pusta.")
            return

        # sprawdź czy nazwa jest unikalna
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"Użytkownik o nazwie '{username}' już istnieje (id={existing.id}).")
            return

        # PIN jako input ukryty
        pin = getpass("PIN (6 cyfr): ").strip()
        if len(pin) != 6 or not pin.isdigit():
            print("PIN musi mieć dokładnie 6 cyfr.")
            return

        user = User(
            username=username,
            pin_hash=User.hash_pin(pin),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print("\n✓ Użytkownik został dodany:")
        print(f"  id: {user.id}")
        print(f"  username: {user.username}")
        print(f"  PIN: {pin}")
    except Exception as e:
        db.rollback()
        print(f"Błąd podczas dodawania użytkownika: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    prompt_new_user()
