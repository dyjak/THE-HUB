"""modele bazy danych dla auth.

uwaga: w tym projekcie modele auth trzymają też tabelę projektów (`Proj`),
która linkuje użytkownika z `render` run_id.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database.connection import Base
import bcrypt

class User(Base):
    """użytkownik aplikacji.

    przechowujemy:
    - `username` (unikalny login)
    - `pin_hash` (hash pin-u; nigdy nie przechowujemy jawnego pinu w tym modelu)
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True)
    pin_hash = Column(String(255))

    # relacja do projektów użytkownika
    projects = relationship("Proj", back_populates="user", cascade="all, delete-orphan")

    @staticmethod
    def hash_pin(pin: str) -> str:
        """hashuje pin użytkownika."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(pin.encode(), salt)
        return hashed.decode()

    @staticmethod
    def verify_pin(pin: str, pin_hash: str) -> bool:
        """weryfikuje pin użytkownika."""
        return bcrypt.checkpw(pin.encode(), pin_hash.encode())


class Proj(Base):
    """projekt powiązany z użytkownikiem.

    pole `render` przechowuje `run_id` kroku render, które ui traktuje jako stabilne id projektu.
    """

    __tablename__ = "projs"

    id = Column(Integer, primary_key=True, index=True)
    # user_id może być null, gdy render został wykonany anonimowo
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # przechowujemy tylko run_id z etapu renderu
    render = Column(String(255), nullable=True)

    user = relationship("User", back_populates="projects")