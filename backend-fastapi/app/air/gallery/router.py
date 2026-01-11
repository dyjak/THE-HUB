from __future__ import annotations

"""endpointy galerii (portfolio/linki).

to proste, publiczne api zwracające listę wpisów do wyświetlenia w ui.
z założenia to są dane statyczne (placeholdery), łatwe do podmiany.
"""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field


class GalleryItem(BaseModel):
    id: str = Field(..., description="Stable id for the entry")
    title: str = Field(..., description="Display title")
    description: str = Field("", description="Freeform description")
    soundcloud_url: str = Field(..., description="Public SoundCloud track/playlist URL")
    tags: List[str] = Field(default_factory=list)
    year: Optional[int] = None


router = APIRouter(
    prefix="/air/gallery",
    tags=["air:gallery"],
    # publiczne z założenia; frontend kontroluje dostęp pod /air/*
)


# wpisy
_DEMO_ITEMS: List[GalleryItem] = [
    GalleryItem(
        id="demo-01",
        title="CORRIDOR",
        description="Przykładowy utwór pokazujący jak brzmią generowane ścieżki po miksie/masterze w DAW.",
        soundcloud_url="https://soundcloud.com/ognisty_ogon/corridor-air-42-processed-project",
        tags=["dark", "typebeat", "mystery", "mix/master"],
        year=2026,
    ),
]


@router.get("/meta")
def meta():
    """zwraca metadane galerii (lista endpointów, liczba wpisów)."""
    return {
        "endpoints": [
            "/air/gallery/meta",
            "/air/gallery/items",
        ],
        "count": len(_DEMO_ITEMS),
    }


@router.get("/items")
def list_items():
    """zwraca listę wpisów galerii.

    opakowujemy listę w obiekt, żeby w przyszłości dało się dodać paging
    bez łamania kształtu odpowiedzi.
    """
    return {"items": [i.model_dump() for i in _DEMO_ITEMS]}
