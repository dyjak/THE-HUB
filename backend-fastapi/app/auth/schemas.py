from pydantic import BaseModel
from typing import List

class LoginRequest(BaseModel):
    pin: str

class RegisterRequest(BaseModel):
    username: str
    pin: str

class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        orm_mode = True