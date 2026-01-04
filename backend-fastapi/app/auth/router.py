"""router endpointów auth.

endpointy:
- `POST /login`: zwraca jwt (bearer)
- `POST /register`: tworzy nowego użytkownika

uwaga:
- logika sesji bazy jest realizowana lokalnym `get_db()` (sesja na request)
- tworzenie tokenu jest delegowane do `create_access_token`
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from ..database.connection import SessionLocal
from .models import User
from .schemas import LoginRequest, RegisterRequest
from .dependencies import create_access_token

router = APIRouter()

def get_db():
    """fastapi dependency: zwraca sesję bazy i zamyka ją po użyciu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/login")
def login(data: LoginRequest = Body(...), db: Session = Depends(get_db)):
    """loguje użytkownika i zwraca access token."""

    # walidacja długości pin-u
    if len(data.pin) != 6 or not data.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN musi składać się z 6 cyfr")

    # znajdź użytkownika po username i zweryfikuj pin
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not User.verify_pin(data.pin, user.pin_hash):
        raise HTTPException(status_code=401, detail="Nieprawidłowa nazwa użytkownika lub PIN")

    access_token = create_access_token({"sub": user.id})

    return {
        "message": "Login successful",
        "id": user.id,
        "username": user.username,
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.post("/register")
def register(data: RegisterRequest = Body(...), db: Session = Depends(get_db)):
    """rejestruje użytkownika."""

    # walidacja długości pin-u
    if len(data.pin) != 6 or not data.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN musi składać się z 6 cyfr")

    user_exists = db.query(User).filter(User.username == data.username).first()

    if user_exists:
        raise HTTPException(status_code=400, detail="Nazwa użytkownika jest już zajęta")

    # sprawdzenie czy pin jest już używany (po kolumnie pin_plain)
    existing_pin_user = db.query(User).filter(User.pin_plain == data.pin).first()
    if existing_pin_user:
        raise HTTPException(status_code=400, detail="Ten PIN jest już zajęty")

    user = User(
        username=data.username,
        pin_hash=User.hash_pin(data.pin),
        pin_plain=data.pin,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "Użytkownik zarejestrowany pomyślnie"}