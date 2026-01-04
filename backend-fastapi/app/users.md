# `app/users.py` — proste endpointy użytkowników (admin/dev)

Ten moduł to minimalistyczny router FastAPI do podglądu i usuwania użytkowników.

Ważne: w obecnej wersji **nie ma tu uwierzytelniania/autoryzacji** (brak `Depends(get_current_user)`), więc traktuj to jako endpointy developerskie.

## 1. Jak jest wpięty w aplikację

W [app/main.py](main.py) router jest montowany z prefixem `/api`:

- `GET /api/users`
- `GET /api/users/{user_id}`
- `DELETE /api/users/{user_id}`

Sam router w [users.py](users.py) jest utworzony jako `router = APIRouter()` bez lokalnego prefixu.

## 2. Endpoints

### 2.1. `GET /api/users`

Zwraca listę wszystkich użytkowników.

- Response model: `List[UserResponse]` (Pydantic z [auth/schemas.py](auth/schemas.py))

Przykładowa odpowiedź:

```json
[
  {"id": 1, "username": "alice"},
  {"id": 2, "username": "bob"}
]
```

### 2.2. `GET /api/users/{user_id}`

Zwraca pojedynczego użytkownika.

- `404` jeśli użytkownik nie istnieje (`"Użytkownik nie znaleziony"`).

Response:

```json
{"id": 1, "username": "alice"}
```

### 2.3. `DELETE /api/users/{user_id}`

Usuwa użytkownika.

- `404` jeśli użytkownik nie istnieje.

Response:

```json
{"message": "Użytkownik usunięty"}
```

## 3. DB i sesje

`users.py` tworzy dependency `get_db()` lokalnie (na bazie `SessionLocal` z [database/connection.py](database/connection.py)).

Wzorzec:

- `db = SessionLocal()`
- `yield db`
- `db.close()` w `finally`

## 4. Bezpieczeństwo / uwagi

- Te endpointy powinny być domknięte auth-em przed produkcją (np. `Depends(get_current_user)` + dodatkowa rola admin).
- Usuwanie usera usuwa rekord z tabeli `users`; projekty powiązane przez relację `User.projects` są skonfigurowane z `cascade="all, delete-orphan"` w modelu (zob. [auth/models.py](auth/models.py)).
