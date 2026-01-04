from __future__ import annotations
from typing import List, Dict, Any
from functools import lru_cache
from .inventory import load_inventory, build_inventory

# ten moduł to cienka warstwa dostępu do inventory w runtime.
#
# główne zadania:
# - trzymać w pamięci (cache) wynik wczytania inventory.json, żeby nie czytać pliku w kółko
# - jeśli inventory.json jeszcze nie istnieje, zbudować go automatycznie
# - udostępnić proste helpery dla innych modułów (lista instrumentów, sprawdzenie gotowości)

SCHEMA_MIN_VERSION = "air-inventory-1"

@lru_cache(maxsize=1)
def get_inventory_cached(deep: bool = False) -> Dict[str, Any]:
    # zwraca inventory z cache.
    # jeśli plik inventory.json nie istnieje (albo nie da się go wczytać), budujemy go od zera.
    # parametr `deep` jest tu tylko "podpowiedzią" dla budowania (może wydłużyć skan).
    inv = load_inventory()
    if inv is None:
        inv = build_inventory(deep=deep)
    return inv

def ensure_inventory(deep: bool = False) -> Dict[str, Any]:
    """wymusza przebudowę inventory, ignorując cache (np. ręczne odświeżenie w ui).

    typowy przypadek:
    - użytkownik dodał/usunął sample w `local_samples/`
    - chcemy przebudować inventory.json i od razu odświeżyć cache w pamięci
    """
    inv = build_inventory(deep=deep)
    # reset cache
    get_inventory_cached.cache_clear()
    get_inventory_cached()  # dogrzanie cache
    return inv

def list_instruments() -> List[str]:
    # zwraca posortowaną listę nazw instrumentów znanych inventory
    inv = get_inventory_cached()
    instruments = inv.get("instruments") or {}
    if isinstance(instruments, dict):
        return sorted(instruments.keys())
    return []

def instrument_exists(name: str) -> bool:
    # proste sprawdzenie, czy dany instrument istnieje w inventory
    return name in set(list_instruments())

def is_inventory_ready() -> bool:
    # sprawdza, czy inventory wygląda na poprawnie zbudowane (po obecności schema_version)
    inv = get_inventory_cached()
    return bool(inv.get("schema_version"))
