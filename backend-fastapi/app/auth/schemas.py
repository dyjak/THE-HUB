from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    pin: str

class RegisterRequest(BaseModel):
    username: str
    pin: str

class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        orm_mode = True