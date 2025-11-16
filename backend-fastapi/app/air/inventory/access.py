from __future__ import annotations
from typing import List, Dict, Any
from functools import lru_cache
from .inventory import load_inventory, build_inventory

SCHEMA_MIN_VERSION = "air-inventory-1"

@lru_cache(maxsize=1)
def get_inventory_cached(deep: bool = False) -> Dict[str, Any]:
    inv = load_inventory()
    if inv is None:
        inv = build_inventory(deep=deep)
    return inv

def ensure_inventory(deep: bool = False) -> Dict[str, Any]:
    """Force rebuild ignoring cache (e.g. manual refresh)."""
    inv = build_inventory(deep=deep)
    # Reset cache
    get_inventory_cached.cache_clear()
    get_inventory_cached()  # warm
    return inv

def list_instruments() -> List[str]:
    inv = get_inventory_cached()
    instruments = inv.get("instruments") or {}
    if isinstance(instruments, dict):
        return sorted(instruments.keys())
    return []

def instrument_exists(name: str) -> bool:
    return name in set(list_instruments())

def is_inventory_ready() -> bool:
    inv = get_inventory_cached()
    return bool(inv.get("schema_version"))
