from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database.connection import Base
import bcrypt

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True)
    pin_hash = Column(String(255))

    # relacja do projektów użytkownika
    projects = relationship("Proj", back_populates="user", cascade="all, delete-orphan")

    @staticmethod
    def hash_pin(pin: str) -> str:
        """Hashuje PIN użytkownika"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(pin.encode(), salt)
        return hashed.decode()

    @staticmethod
    def verify_pin(pin: str, pin_hash: str) -> bool:
        """Weryfikuje PIN użytkownika"""
        return bcrypt.checkpw(pin.encode(), pin_hash.encode())


class Proj(Base):
    __tablename__ = "projs"

    id = Column(Integer, primary_key=True, index=True)
    # user_id może być NULL, gdy render został wykonany anonimowo
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Przechowujemy tylko run_id z etapu renderu
    render = Column(String(255), nullable=True)

    user = relationship("User", back_populates="projects")