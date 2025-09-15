from sqlalchemy import Column, Integer, String
from ..database.connection import Base
import bcrypt

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    pin_hash = Column(String, unique=True, index=True)  # PIN musi być unikalny

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