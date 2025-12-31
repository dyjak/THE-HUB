from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_gallery_items_shape() -> None:
    resp = client.get("/api/air/gallery/items")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert isinstance(data["items"], list)

    # basic shape check for first item
    if data["items"]:
        first = data["items"][0]
        assert isinstance(first, dict)
        for key in ("id", "title", "description", "soundcloud_url"):
            assert key in first
