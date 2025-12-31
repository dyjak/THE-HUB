from __future__ import annotations

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
    # Public by design; frontend controls access under /air/*
)


# NOTE: Placeholder demo entries. Replace with your own portfolio links later.
_DEMO_ITEMS: List[GalleryItem] = [
    GalleryItem(
        id="demo-01",
        title="Cinematic Pulse (Demo)",
        description="Przykładowy utwór pokazujący jak brzmią generowane sample po miksie/masterze w DAW. (placeholder)",
        soundcloud_url="https://soundcloud.com/forss/flickermood",
        tags=["cinematic", "hybrid", "mix/master"],
        year=2025,
    ),
    GalleryItem(
        id="demo-02",
        title="Lo-fi Groove Sketch (Demo)",
        description="Luźny szkic: groove + tekstury. (placeholder)",
        soundcloud_url="https://soundcloud.com/forss/stranger",
        tags=["lofi", "groove"],
        year=2025,
    ),
    GalleryItem(
        id="demo-03",
        title="Tech House Drop (Demo)",
        description="Krótka prezentacja transjentów i subu po obróbce. (placeholder)",
        soundcloud_url="https://soundcloud.com/forss/sets/ecclesia",
        tags=["tech-house", "club"],
        year=2025,
    ),
]


@router.get("/meta")
def meta():
    return {
        "endpoints": [
            "/air/gallery/meta",
            "/air/gallery/items",
        ],
        "count": len(_DEMO_ITEMS),
    }


@router.get("/items")
def list_items():
    # Wrap in an object to allow future paging without breaking the shape.
    return {"items": [i.model_dump() for i in _DEMO_ITEMS]}
