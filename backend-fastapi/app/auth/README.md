# `app/auth` — uwierzytelnianie (PIN + JWT)

Ten moduł dostarcza minimalny mechanizm auth dla backendu FastAPI:

- rejestracja użytkownika (username + 6‑cyfrowy PIN),
- logowanie (walidacja PIN),
- generowanie JWT (Bearer token),
- dependency do pobierania aktualnego użytkownika z nagłówka `Authorization`.

## 1. Jak to jest wpięte w aplikację

W [app/main.py](../main.py) router auth jest montowany z prefixem `/api`:

- `POST /api/login`
- `POST /api/register`

W tym repo większość endpointów AIR jest aktualnie publiczna (bez `Depends(get_current_user)`), więc auth jest wykorzystywany głównie do:

- powiązania renderów z użytkownikiem w DB (`Proj.user_id`),
- zasilania endpointów typu „projekty użytkownika” parametrem `user_id` (przekazywanym z frontendu).

## 2. Endpoints

### 2.1. `POST /api/register`

Tworzy nowego użytkownika.

Request body (Pydantic: `RegisterRequest` z [schemas.py](schemas.py)):

```json
{
  "username": "alice",
  "pin": "123456"
}
```

Walidacje:

- `pin` musi mieć dokładnie 6 znaków i składać się z cyfr (`isdigit()`), inaczej `400`.
- `username` musi być unikalny, inaczej `400`.

Zapis do DB:

- PIN jest hashowany `bcrypt` i zapisywany w `users.pin_hash`.
- Jawny PIN **nie jest przechowywany**.

Response:

```json
{ "message": "Użytkownik zarejestrowany pomyślnie" }
```

### 2.2. `POST /api/login`

Loguje użytkownika i zwraca token JWT.

Request body (Pydantic: `LoginRequest`):

```json
{
  "username": "alice",
  "pin": "123456"
}
```

Walidacje/błędy:

- `pin` nie ma 6 cyfr → `400`.
- nie ma takiego użytkownika albo `bcrypt.checkpw()` nie przejdzie → `401`.

Response:

```json
{
  "message": "Login successful",
  "id": 1,
  "username": "alice",
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

Token jest JWT (HS256). Payload zawiera co najmniej:

- `sub`: `user.id`
- `exp`: data wygaśnięcia

## 3. JWT i dependencies

Kod jest w [dependencies.py](dependencies.py).

### 3.1. `create_access_token()`

Tworzy token JWT dla payloadu `data` i dopina `exp`.

Istotny fragment:

```python
expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
secret = os.getenv("AUTH_SECRET_KEY", SECRET_KEY)
return jwt.encode(to_encode, secret, algorithm="HS256")
```

Konfiguracja:

- `AUTH_SECRET_KEY` (env) — sekret do podpisywania JWT.
- domyślny `SECRET_KEY` w kodzie to placeholder (`change-me-in-env`).
- `ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24` (24h).

### 3.2. `get_current_user`

Dependency do endpointów chronionych:

- czyta `Authorization: Bearer <token>` (FastAPI `HTTPBearer(auto_error=True)`),
- dekoduje JWT,
- bierze `sub` jako `user_id` i pobiera użytkownika z DB,
- w razie problemu rzuca `401`.

Użycie (przykład):

```python
from app.auth.dependencies import get_current_user

@router.get("/me")
def me(user = Depends(get_current_user)):
    return {"id": user.id, "username": user.username}
```

### 3.3. `get_optional_user`

Wersja „miękka” (HTTPBearer `auto_error=False`):

- zwraca `None`, gdy brak tokena / token niepoprawny,
- przydatne dla endpointów publicznych, gdzie auth jest tylko dodatkiem.

## 4. Modele DB

Modele są w [models.py](models.py).

### 4.1. `User`

Kolumny:

- `id`: int
- `username`: unique
- `pin_hash`: bcrypt hash

Weryfikacja PIN:

- `User.hash_pin(pin)` → `bcrypt.hashpw()`
- `User.verify_pin(pin, pin_hash)` → `bcrypt.checkpw()`

### 4.2. `Proj`

Model projektu użytkownika (używany przez AIR):

- `user_id` (nullable)
- `created_at`
- `render` — `run_id` renderu (stabilny identyfikator projektu po stronie UI)

Relacja:

- `User.projects` ↔ `Proj.user`

## 5. Uwagi bezpieczeństwa (ważne w produkcji)

- Ustaw `AUTH_SECRET_KEY` w środowisku; nie polegaj na domyślnej wartości w kodzie.
- To jest prosty system auth bez refresh tokenów, bez blokad brute-force i bez rate-limit.
- Endpointy administracyjne w [app/users.py](../users.py) są publiczne w tej wersji (brak auth) — jeśli to ma iść na prod, warto je zabezpieczyć.
