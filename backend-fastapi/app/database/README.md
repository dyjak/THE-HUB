# `app/database` — baza danych (SQLite + SQLAlchemy)

Ten pakiet trzyma **konfigurację połączenia do bazy** i kilka prostych narzędzi CLI.

Aktualnie aplikacja używa SQLite w pliku `users.db`.

## 1. Najważniejsze pliki

- [connection.py](connection.py) — `engine`, `SessionLocal`, `Base` + dependency `get_db()`.
- [migrate_db.py](migrate_db.py) — „migrate-lite”: minimalne poprawki schematu przez SQL (bez Alembica).
- [seeder.py](seeder.py) — bootstrap struktury: `Base.metadata.create_all()`.
- [add_user.py](add_user.py) — interaktywny skrypt do ręcznego dodania użytkownika.
- [__init__.py](__init__.py) — re-export `Base/engine/SessionLocal/get_db`.

## 2. Gdzie jest plik bazy danych

W [connection.py](connection.py) `DATABASE_URL` to:

- `sqlite:///./users.db`

To oznacza:

- plik `users.db` jest tworzony **w bieżącym katalogu roboczym procesu** (CWD), a nie „zawsze obok kodu”.

W praktyce:

- jeśli uruchamiasz backend z folderu `backend-fastapi/`, to DB zwykle ląduje w `backend-fastapi/users.db`.

## 3. SQLAlchemy: engine, sesje i dependency

### 3.1. `engine`

`engine` jest tworzony z:

- `connect_args={"check_same_thread": False}`

To jest typowe dla SQLite w aplikacji webowej (wątki/konkurencja).

### 3.2. `SessionLocal`

`SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`.

Sesja jest tworzona per-request (albo per skrypt CLI) i zamykana na końcu.

### 3.3. `get_db()` (FastAPI dependency)

Wspólny wzorzec używany w routerach:

```python
from app.database.connection import get_db

@router.get("/something")
def handler(db: Session = Depends(get_db)):
    ...
```

`get_db()` robi:

- `db = SessionLocal()`
- `yield db`
- `db.close()` w `finally`

Uwaga: w repo są też lokalne kopie `get_db()` w niektórych routerach (np. `app/auth/router.py`, `app/users.py`). Logicznie robią to samo.

## 4. Inicjalizacja tabel

W runtime, [app/main.py](../main.py) woła:

- `Base.metadata.create_all(bind=engine)`

czyli tabele powinny powstać automatycznie przy starcie aplikacji (o ile import modeli nastąpił).

Dodatkowo jest skrypt CLI:

- uruchomienie [seeder.py](seeder.py) robi to samo (`create_all`).

## 5. Migracje (migrate-lite)

[migrate_db.py](migrate_db.py) to minimalny skrypt, który:

- sprawdza przez `PRAGMA table_info(users)` czy istnieje kolumna `pin_hash` i ewentualnie ją dodaje,
- tworzy tabelę `projs`, jeśli nie istnieje.

To **nie jest pełny system migracji** (brak wersjonowania, brak downgrade). Jest przydatny, gdy masz starą bazę i chcesz ją „doprowadzić do stanu, w którym aplikacja wstaje”.

## 6. Dodawanie użytkownika z CLI

[add_user.py](add_user.py) pozwala dodać usera bez frontendu:

- pyta o `username`
- pyta o PIN przez `getpass()`
- hashuje PIN (`bcrypt` przez `User.hash_pin`)

Ważne: skrypt wypisuje PIN w konsoli jako potwierdzenie (OK dla dev, nie dla produkcji).

## 7. Jak DB jest używana w reszcie aplikacji

- `app/auth/models.py` definiuje:
  - `User` (użytkownik)
  - `Proj` (powiązanie user → render `run_id`)
- `app/air/render/router.py` (best-effort) zapisuje rekord `Proj(user_id, render=run_id)`.
- `app/air/user_projects_router.py` czyta `Proj` i łączy dane z plikami `render_state.json`.

## 8. Gotchas / ograniczenia

- `sqlite:///./users.db` zależy od CWD; jeśli uruchomisz backend z innego folderu, możesz „zgubić” bazę i stworzyć nową.
- Brak Alembica: zmiany schematu poza tymi w `migrate_db.py` wymagają ręcznej migracji.
- W repo są publiczne endpointy admin (`/api/users`); jeśli planujesz produkcję, warto je zabezpieczyć auth-em.
