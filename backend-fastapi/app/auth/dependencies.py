"""zależności i helpery uwierzytelniania.

ten moduł realizuje:
- tworzenie jwt access tokenów
- dependency do pobrania bieżącego użytkownika (wymagany token)
- dependency opcjonalne (zwraca None zamiast 401)

uwaga:
- sekret może być nadpisany przez `AUTH_SECRET_KEY` w env
- baza danych jest pobierana przez `SessionLocal` z `app.database.connection`
"""

from datetime import datetime, timedelta
from typing import Optional
import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..database.connection import SessionLocal
from .models import User


SECRET_KEY = "change-me-in-env"  # can be overridden by ENV
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


def get_db():
    """fastapi dependency: zwraca sesję bazy i zamyka ją po użyciu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """tworzy jwt access token.

    - payload jest kopiowany i rozszerzany o `exp`
    - czas wygaśnięcia domyślnie wynika z `ACCESS_TOKEN_EXPIRE_MINUTES`
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    secret = os.getenv("AUTH_SECRET_KEY", SECRET_KEY)
    return jwt.encode(to_encode, secret, algorithm=ALGORITHM)


security = HTTPBearer(auto_error=True)

# wersja opcjonalna: nie rzuca 401, tylko zwraca None gdy brak/niepoprawny token.
security_optional = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """fastapi dependency: zwraca zalogowanego użytkownika.

    rzuca 401, gdy:
    - token jest niepoprawny / nie da się go zdekodować
    - payload nie zawiera `sub`
    - użytkownik o danym id nie istnieje
    """
    token = credentials.credentials
    secret = os.getenv("AUTH_SECRET_KEY", SECRET_KEY)
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Nieautoryzowany")
    except JWTError:
        raise HTTPException(status_code=401, detail="Nieautoryzowany")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Nieautoryzowany")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: Session = Depends(get_db),
) -> User | None:
    """zwraca zalogowanego użytkownika lub None, jeśli brak poprawnego tokena.

    używane w publicznych endpointach, gdzie auth jest tylko dodatkową informacją.
    """

    if credentials is None:
        return None

    token = credentials.credentials
    secret = os.getenv("AUTH_SECRET_KEY", SECRET_KEY)
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    return user
