from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from ..database.connection import SessionLocal
from .models import User
from .schemas import LoginRequest, RegisterRequest

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/login")
def login(data: LoginRequest = Body(...), db: Session = Depends(get_db)):
    # Walidacja długości PIN-u
    if len(data.pin) != 6 or not data.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN musi składać się z 6 cyfr")

    # Znajdź użytkownika po PIN (musimy sprawdzić wszystkich)
    users = db.query(User).all()
    found_user = None

    for user in users:
        if User.verify_pin(data.pin, user.pin_hash):
            found_user = user
            break

    if not found_user:
        raise HTTPException(status_code=401, detail="Nieprawidłowy PIN")

    return {
        "message": "Login successful",
        "username": found_user.username
    }

@router.post("/register")
def register(data: RegisterRequest = Body(...), db: Session = Depends(get_db)):
    # Walidacja długości PIN-u
    if len(data.pin) != 6 or not data.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN musi składać się z 6 cyfr")

    user_exists = db.query(User).filter(User.username == data.username).first()

    if user_exists:
        raise HTTPException(status_code=400, detail="Nazwa użytkownika jest już zajęta")

    # Sprawdzenie czy PIN jest już używany (musimy sprawdzić wszystkich)
    users = db.query(User).all()

    for user in users:
        if User.verify_pin(data.pin, user.pin_hash):
            raise HTTPException(status_code=400, detail="Ten PIN jest już zajęty")

    user = User(
        username=data.username,
        pin_hash=User.hash_pin(data.pin)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "Użytkownik zarejestrowany pomyślnie"}