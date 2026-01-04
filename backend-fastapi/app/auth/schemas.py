"""schematy pydantic dla endpointów auth."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """dane wejściowe logowania."""
    username: str
    pin: str

class RegisterRequest(BaseModel):
    """dane wejściowe rejestracji."""
    username: str
    pin: str

class UserResponse(BaseModel):
    """publiczny widok użytkownika w odpowiedziach api."""
    id: int
    username: str

    class Config:
        orm_mode = True