from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
from typing import Any

from .inventory import build_inventory, load_inventory, INVENTORY_SCHEMA_VERSION
from .access import get_inventory_cached, ensure_inventory
from urllib.parse import quote
from pathlib import Path
from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/air/inventory",
    tags=["air:inventory"],
    # Auth is enforced by the frontend /air/* route; these endpoints stay public.
)  # reload nudge

@router.get("/meta")
def meta():
    return {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "endpoints": [
            "/air/inventory/inventory",
            "/air/inventory/rebuild",
            "/air/inventory/available-instruments",
            "/air/inventory/samples/{instrument}",
        ],
    }

@router.get("/available-instruments")
def available_instruments():
    inv = get_inventory_cached()
    instruments = sorted((inv.get("instruments") or {}).keys()) if isinstance(inv.get("instruments"), dict) else []
    return {"available": instruments, "count": len(instruments)}

@router.get("/inventory")
def get_inventory():
    inv = load_inventory()
    if inv is None:
        inv = build_inventory()
    return inv

@router.post("/rebuild")
def rebuild(mode: str | None = None):
    deep = mode == "deep"
    inv = ensure_inventory(deep=deep)
    return {"rebuilt": True, "schema_version": inv.get("schema_version"), "instrument_count": inv.get("instrument_count"), "deep": deep}

@router.get("/samples/{instrument}")
def list_samples(instrument: str, offset: int = 0, limit: int = 100):
    inv = get_inventory_cached()
    rows = [r for r in (inv.get("samples") or []) if r.get("instrument") == instrument]
    if not rows:
        return {"instrument": instrument, "count": 0, "items": [], "default": None}
    start = max(0, int(offset)); end = start + max(1, min(500, int(limit)))
    out: list[dict[str, Any]] = []
    base = Path(inv.get("root") or ".").resolve()
    for r in rows[start:end]:
        # Build preview URL from relative path if available
        url = None
        try:
            rel = r.get("file_rel")
            if rel:
                rel_posix = Path(rel).as_posix()
                url = "/api/local-samples/" + quote(rel_posix, safe="/")
            else:
                # Try to compute rel from abs if under base
                f_abs = Path(r.get("file_abs")) if r.get("file_abs") else None
                if f_abs:
                    rel2 = f_abs.resolve().relative_to(base).as_posix()
                    url = "/api/local-samples/" + quote(rel2, safe="/")
        except Exception:
            url = None
        out.append({
            "id": r.get("id"),
            "file": r.get("file_abs") or str((base / (r.get("file_rel") or "")).resolve()),
            "name": (Path(r.get("file_abs")).name if r.get("file_abs") else Path(r.get("file_rel") or "").name),
            "url": url,
            "subtype": r.get('subtype'),
            "family": r.get('family'),
            "category": r.get('category'),
            "pitch": r.get('pitch'),
        })
    default_item = out[0] if out else None
    return {"instrument": instrument, "count": len(rows), "offset": start, "limit": limit, "items": out, "default": default_item}


@router.post("/select")
def select_samples(payload: dict):
    """Select sample per instrument using simple deterministic strategy.
    Body: { instruments: string[], offset?: number }
    Returns: { selections: [{ instrument, id, file, url, name }], missing: string[] }
    """
    instruments = payload.get("instruments") or []
    try:
        instruments = [str(i) for i in instruments if str(i).strip()]
    except Exception:
        instruments = []
    offset = 0
    try:
        if payload.get("offset") is not None:
            offset = max(0, int(payload.get("offset")))
    except Exception:
        offset = 0
    inv = get_inventory_cached()
    base = Path(inv.get("root") or ".").resolve()
    rows = inv.get("samples") or []
    selections: list[dict[str, Any]] = []
    missing: list[str] = []
    for inst in instruments:
        inst_rows = [r for r in rows if r.get("instrument") == inst]
        if not inst_rows:
            missing.append(inst)
            continue
        row = inst_rows[offset % len(inst_rows)]
        url = None
        try:
            rel = row.get("file_rel")
            if rel:
                rel_posix = Path(rel).as_posix()
                url = "/api/local-samples/" + quote(rel_posix, safe="/")
            elif row.get("file_abs"):
                rel2 = Path(row.get("file_abs")).resolve().relative_to(base).as_posix()
                url = "/api/local-samples/" + quote(rel2, safe="/")
        except Exception:
            url = None
        name = None
        try:
            if row.get("file_abs"):
                name = Path(row.get("file_abs")).name
            elif row.get("file_rel"):
                name = Path(row.get("file_rel")).name
        except Exception:
            name = row.get("id")
        selections.append({
            "instrument": inst,
            "id": row.get("id"),
            "file": row.get("file_abs") or str((base / (row.get("file_rel") or "")).resolve()),
            "url": url,
            "name": name,
        })
    return {"selections": selections, "missing": missing or None}
