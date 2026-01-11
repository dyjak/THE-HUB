# Deploy (VPS + Tailscale, private access)

Goal: run THE-HUB 24/7 on a cheap VPS, **not public on the Internet**, only accessible to people you allow via Tailscale.

## What you get

- One URL inside your Tailnet: `http://<magicdns-name>` (via `tailscale serve`)
- Frontend + backend behind a single origin (Caddy) → no CORS pain.
- Persistent data on VPS disk:
  - SQLite: `deploy/data/users.db`
  - inventory: `deploy/data/inventory.json`
  - outputs: `deploy/data/*_output/`

## 1) Pick a VPS

Minimal practical: **1 vCPU / 2 GB RAM**. Your `local_samples` is ~270 MB so storage isn’t a problem.

## 2) Install Docker + Compose on the VPS

Use your distro docs. On Ubuntu, the official Docker repo is the easiest.

## 3) Install Tailscale on the VPS

- Install Tailscale
- `tailscale up` (enable MagicDNS in the admin panel if you want stable names)
- Add your own laptop/phone to the same Tailnet
- To give access to someone else: invite them to Tailnet or use Tailscale "device sharing".

## 4) Copy the repo + samples

- `git clone ...`
- Copy your `local_samples/` folder onto the VPS into the repo root (same level as `deploy/`).

## 4.1) Prepare persistent data folders/files

Bind-mounting single files requires they exist on the host.

From the repo root on the VPS:

- `mkdir -p deploy/data`
- `touch deploy/data/users.db deploy/data/inventory.json`
- `mkdir -p deploy/data/render_output deploy/data/midi_output deploy/data/param_output`

## 5) Configure env

In `deploy/`:
- copy `.env.example` → `.env`
- set:
  - `HUB_PUBLIC_URL` to your VPS MagicDNS name, e.g. `http://thehub-vps` (no port)
  - `AUTH_SECRET_KEY`, `NEXTAUTH_SECRET`

## 6) Start

From `deploy/` on the VPS:

- `docker compose --env-file .env up -d --build`

Caddy is bound to `127.0.0.1:8080` by default.

## 7) Expose only over Tailscale

Because Caddy listens on loopback, it is not reachable publicly.

Option A (simplest): use Tailscale Serve to publish localhost:8080 to your tailnet (HTTP)

- `sudo tailscale serve --http=80 http://127.0.0.1:8080`

Tip: add `--bg` to make it persistent without keeping a shell open:

- `sudo tailscale serve --bg --http=80 http://127.0.0.1:8080`

Then browse: `http://<magicdns-name>`.

If you prefer keeping it at :8080, skip Serve and change the compose port mapping to a Tailscale-only IP (advanced).

## Notes

- If you later want public HTTPS, swap this setup to a domain + Caddy automatic TLS.
- If you see missing inventory/instruments: call `POST /api/air/inventory/rebuild` once.
