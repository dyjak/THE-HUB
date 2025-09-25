"""Test sekwencji luzowania zapytań (offline) – weryfikuje kolejność bez realnych requestów.

Ponieważ funkcja build_relaxed_queries jest zagnieżdżona w get_samples_for_genre,
reimplementujemy minimalnie ten sam algorytm tutaj aby wykryć regresje (jeśli
zostanie zmieniona kolejność – test można zaktualizować świadomie).
"""

from typing import List


def build_relaxed_queries_reference(inst: str, base_query: str, biases: List[str], hints: List[str], synonyms: List[str]) -> List[str]:
    q: List[str] = [base_query]
    q.extend([f"{b} {base_query}" for b in biases])
    q.extend(hints)
    q.append(f"{inst} wav")
    for syn in synonyms:
        q.append(f"{syn} wav")
    seen = set()
    dedup: List[str] = []
    for item in q:
        if item not in seen:
            dedup.append(item)
            seen.add(item)
    return dedup


def test_build_relaxed_queries_order():
    inst = "drums"
    base = "jazz drums"
    biases = ["soft", "warm"]
    hints = ["drum kit one shot wav", "acoustic drums wav"]
    synonyms = ["drum kit", "drum loop", "drum beat", "percussion"]

    queries = build_relaxed_queries_reference(inst, base, biases, hints, synonyms)

    # Spodziewane pierwsze elementy w określonej kolejności
    assert queries[0] == base
    # biasy zaraz po bazowym
    assert queries[1] == f"{biases[0]} {base}"
    assert queries[2] == f"{biases[1]} {base}"
    # hints potem
    assert hints[0] in queries and hints[1] in queries
    # instrument wav po hints
    assert any(q == f"{inst} wav" for q in queries)
    # synonimy obecne
    for syn in synonyms:
        assert f"{syn} wav" in queries
    # brak duplikatów
    assert len(queries) == len(set(queries))
