# AIR (backend) — `gallery`

Ten moduł wystawia bardzo proste, publiczne API “portfolio”: lista statycznych wpisów (placeholdery) do pokazania w UI.

Nie ma tu bazy danych ani zapisu — dane są zaszyte w kodzie.

## 1. Pliki w module

- [router.py](router.py) — endpointy FastAPI + modele Pydantic.

## 2. Endpointy HTTP

Prefiks routera: `/api/air/gallery`

### 2.1. `GET /meta`

Zwraca metadane galerii:

- listę endpointów,
- `count` (liczba wpisów).

### 2.2. `GET /items`

Zwraca listę wpisów galerii w obiekcie:

```json
{ "items": [ ... ] }
```

Lista jest opakowana w obiekt, żeby w przyszłości dało się dodać paging bez zmiany kształtu odpowiedzi.

## 3. Model danych (`GalleryItem`)

Każdy wpis ma pola:

- `id`: stabilny identyfikator
- `title`: tytuł
- `description`: opis (string, może być pusty)
- `soundcloud_url`: publiczny URL track/playlist
- `tags`: lista tagów
- `year`: opcjonalny rok (`int`)

## 4. Źródło danych

W `router.py` dane są w stałej `_DEMO_ITEMS` (placeholder). Żeby podmienić na własne wpisy, edytujesz tę listę.
