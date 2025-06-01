from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database.connection import Base, engine
from .auth.router import router as auth_router
from .users import router as users_router
from .database.seeder import seed_users

app = FastAPI()

# Konfiguracja CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upewnij się, że tabele są utworzone
Base.metadata.create_all(bind=engine)

# Wywołaj seeder przy starcie aplikacji
seed_users()

# Dodaj routery
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")