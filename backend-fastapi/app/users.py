from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database.connection import SessionLocal
from .auth.models import User
from .auth.schemas import UserResponse
from typing import List

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pobieranie listy użytkowników
@router.get("/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

# Pobieranie szczegółów jednego użytkownika
@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")
    return user

# Usuwanie użytkownika
@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie znaleziony")

    db.delete(user)
    db.commit()
    return {"message": "Użytkownik usunięty"}