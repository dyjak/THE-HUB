# Deploy (VPS + Docker + Tailscale, prywatny dostęp)

Celem jest uruchomienie THE-HUB 24/7 na tanim VPS **bez wystawiania do publicznego Internetu**. Dostęp mają tylko osoby, którym go dasz (przez Tailscale).

## Co dostajesz

- Jedno prywatne URL w Twoim Tailnet: `http://<magicdns-nazwa>` (przez `tailscale serve`)
- Frontend + backend pod jednym originem (Caddy) → bez problemów z CORS
- Trwałe dane na dysku VPS:
  - SQLite: `deploy/data/users.db`
  - inventory: `deploy/data/inventory.json`
  - outputy: `deploy/data/*_output/`

## Wymagania

- VPS (praktyczne minimum: **1 vCPU / 2 GB RAM**)
- Docker + Docker Compose (plugin `docker compose`)
- Tailscale na VPS
- Skopiowany folder `local_samples/` na VPS do katalogu repo (na tym samym poziomie co `deploy/`)

## 1) Docker + Compose na VPS

Zainstaluj z dokumentacji Twojej dystrybucji (na Ubuntu najwygodniej repo Dockera).

Szybki test:

- `docker --version`
- `docker compose version`

## 2) Tailscale na VPS

1. Zainstaluj Tailscale
2. Uruchom:
   - `sudo tailscale up`
3. (Opcjonalnie) w panelu Tailscale włącz MagicDNS, żeby mieć stabilną nazwę hosta
4. Dodaj swój laptop/telefon do tego samego Tailnet
5. Dostęp dla kogoś innego: zaproszenie do Tailnet lub „device sharing”

Przydatne:

- `tailscale status`

## 3) Repo + sample

1. `git clone ...`
2. Skopiuj `local_samples/` do katalogu repo na VPS.

## 4) Przygotuj trwałe dane (bind-mounty)

Bind-mount pojedynczych plików wymaga, żeby istniały na hoście.

Z katalogu głównego repo:

- `mkdir -p deploy/data`
- `touch deploy/data/users.db deploy/data/inventory.json`
- `mkdir -p deploy/data/render_output deploy/data/midi_output deploy/data/param_output`

## 5) Konfiguracja `.env`

W katalogu `deploy/`:

1. Skopiuj `.env.example` → `.env`
2. Ustaw minimum:
   - `HUB_PUBLIC_URL` → Twoja nazwa MagicDNS, np. `http://thehub-vps` (bez portu)
   - `AUTH_SECRET_KEY`
   - `NEXTAUTH_SECRET`

Uwaga: wartości typu `NEXT_PUBLIC_*` są „wypiekane” w build frontendu. Zmiana `HUB_PUBLIC_URL` zwykle oznacza rebuild frontendu.

## 6) Start (pierwsze uruchomienie)

Z katalogu `deploy/`:

- `docker compose --env-file .env up -d --build`

Domyślnie Caddy słucha tylko na loopback: `127.0.0.1:8080`.

### Szybkie testy (na VPS)

- `curl -I http://127.0.0.1:8080/`
- `curl http://127.0.0.1:8080/api/health`

## 7) Wystaw tylko przez Tailscale (bez publicznego Internetu)

Najprościej: Tailscale Serve publikuje `127.0.0.1:8080` w Twoim Tailnet.

- `sudo tailscale serve --bg --http=80 http://127.0.0.1:8080`

Sprawdzenie statusu Serve:

- `tailscale serve status`

Reset (gdy pomylisz komendę lub chcesz zmienić target):

- `sudo tailscale serve reset`
- potem ponownie `sudo tailscale serve --bg --http=80 http://127.0.0.1:8080`

Wejście z urządzenia w Tailnet:

- Otwórz w przeglądarce: `http://<magicdns-nazwa>`

## Dostęp bez Tailscale (publiczny URL + hasło)

Da się wejść bez Tailscale „po URL”, ale wtedy serwis jest dostępny z Internetu. Żeby nie był otwarty dla każdego, najprościej dodać bramkę hasłem (Basic Auth) w Caddy.

W repo przygotowane jest to jako tryb „public” przez override compose.

### Co jest potrzebne

- Domena (zalecane, żeby mieć HTTPS): np. `hub.twojadomena.pl`
- Rekord DNS A/AAAA na IP VPS
- Otwarte porty 80 i 443 na firewallu VPS / w panelu OVH

### Kroki

1) Ustaw w `deploy/.env`:

- `HUB_PUBLIC_URL=https://hub.twojadomena.pl`
- `HUB_DOMAIN=hub.twojadomena.pl`
- `BASIC_AUTH_USER=jakislogin`
- `BASIC_AUTH_HASH=...` (hash hasła)

Te zmienne są przekazywane do kontenera Caddy (Caddyfile.public używa placeholderów `{$HUB_DOMAIN}`, `{$BASIC_AUTH_USER}`, `{$BASIC_AUTH_HASH}`), więc muszą być ustawione w `.env`.

2) Wygeneruj hash hasła (na VPS):

- `docker run --rm caddy:2-alpine caddy hash-password --plaintext 'twoje-super-haslo'`

Wklej wynik do:

- `BASIC_AUTH_HASH=...`

Uwaga: `docker compose` traktuje znak `$` w pliku `.env` jako interpolację zmiennych. Hash z Caddy wygląda np. jak `$2a$14$...` i bez ucieczki zobaczysz warningi typu: `The "bnOg..." variable is not set`.

Rozwiązanie: w `deploy/.env` zamień każdy znak `$` na `$$`.

Przykład:

- masz z generatora: `$2a$14$abcd...`
- w `.env` wpisujesz: `$$2a$$14$$abcd...`

3) Uruchom w trybie public (bez Tailscale):

- `docker compose -f docker-compose.yml -f docker-compose.public.yml --env-file .env up -d --build`

Jeśli dostaniesz błąd typu: `failed to bind host port 0.0.0.0:80: address already in use`, to znaczy że na VPS już coś słucha na porcie 80 (np. nginx/apache/inny Caddy). Zobacz sekcję „Port 80/443 zajęty” poniżej.

4) (Opcjonalnie) Wyłącz Tailscale Serve, jeśli był włączony:

- `sudo tailscale serve reset`

Od teraz wchodzisz normalnie: `https://hub.twojadomena.pl` i przeglądarka poprosi o login/hasło.

### Uwagi bezpieczeństwa

- Jeśli nie masz domeny i wejdziesz po samym IP (HTTP), to hasło będzie leciało niezaszyfrowane → niezalecane.
- Basic Auth to „bramka”, ale nie zastępuje normalnego systemu uprawnień (to nadal publiczny serwis z hasłem).

## Najważniejsze komendy „po zmianach” (cheat-sheet)

Wszystkie komendy poniżej uruchamiaj z katalogu `deploy/`.

### Status / logi

- `docker compose ps`
- `docker compose logs -f --tail=200`
- `docker compose logs -f --tail=200 frontend`
- `docker compose logs -f --tail=200 backend`
- `docker compose logs -f --tail=200 caddy`

### Restart bez przebudowy

- `docker compose restart`
- `docker compose restart frontend`
- `docker compose restart backend`
- `docker compose restart caddy`

### Rebuild po zmianach w kodzie

Najczęściej wystarczy:

- `docker compose --env-file .env up -d --build`

Tylko backend:

- `docker compose build backend`
- `docker compose up -d backend`

Tylko frontend:

- `docker compose build frontend`
- `docker compose up -d frontend`

Ważne: jeśli zmieniasz `.env` w sposób wpływający na frontend (np. URL), przebuduj `frontend`.

### „Twardy” rebuild (gdy cachowanie przeszkadza)

- `docker compose down`
- `docker compose build --no-cache`
- `docker compose --env-file .env up -d`

### Aktualizacja z gita

Z katalogu repo (poza `deploy/`):

- `git pull`

Potem z `deploy/`:

- `docker compose --env-file .env up -d --build`

### Healthcheck po deployu

- `curl http://127.0.0.1:8080/api/health`

## Inventory / sample DB

Gdy brakuje instrumentów / inventory jest puste, wywołaj rebuild inventory (na VPS):

- `curl -X POST http://127.0.0.1:8080/api/air/inventory/rebuild`

## Backup / przenoszenie danych

Najważniejsze pliki/katalogi do backupu:

- `deploy/data/users.db`
- `deploy/data/inventory.json`
- `deploy/data/*_output/`

Szybka kopia bazy (na VPS):

- `cp deploy/data/users.db deploy/data/users.db.bak`

## Typowe problemy

- Front działa, ale logowanie/NextAuth robi redirect na `/api/auth/error`: sprawdź routing Caddy w `deploy/Caddyfile` i zrób `docker compose restart caddy`.
- Zmieniłeś adres (MagicDNS/Tailnet URL), a frontend „pamięta stary”: zaktualizuj `deploy/.env` i zrób `docker compose build frontend ; docker compose up -d frontend`.
- Serve nie działa: `tailscale serve status`, ewentualnie `sudo tailscale serve reset` i ustaw ponownie.

### Port 80/443 zajęty (tryb public)

Objaw przy starcie:

- `failed to bind host port 0.0.0.0:80/tcp: address already in use`

Diagnostyka (na VPS):

```sh
sudo ss -ltnp | egrep ':(80|443)\s'
sudo ss -ltnp | grep ':80 '
sudo ss -ltnp | grep ':443 '
```

Najczęstsze przyczyny i fix:

```sh
# nginx
sudo systemctl stop nginx
sudo systemctl disable nginx

# apache
sudo systemctl stop apache2
sudo systemctl disable apache2

# sprawdź czy nie masz innego kontenera na 80/443
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

Po uwolnieniu portów uruchom ponownie:

```sh
cd ~/THE-HUB/deploy
docker compose -f docker-compose.yml -f docker-compose.public.yml --env-file .env up -d --build
```

