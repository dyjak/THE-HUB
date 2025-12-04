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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    secret = os.getenv("AUTH_SECRET_KEY", SECRET_KEY)
    return jwt.encode(to_encode, secret, algorithm=ALGORITHM)


security = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
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
