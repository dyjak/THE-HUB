from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .client import simple_chat, ChatError, list_providers, list_models

router = APIRouter(prefix="/chat-smoke", tags=["ai-param-test:chat-smoke"])


class ChatIn(BaseModel):
    prompt: str
    provider: str | None = None
    model: str | None = None


class ChatOut(BaseModel):
    reply: str
    provider: str
    model: str


@router.get("/providers")
async def providers():
    return {"providers": list_providers()}


@router.get("/models/{provider}")
async def models(provider: str):
    items = list_models(provider)
    return {"provider": provider, "models": items}


@router.post("/send", response_model=ChatOut)
async def chat_send(body: ChatIn) -> ChatOut:
    try:
        provider = (body.provider or "openai").lower()
        reply = simple_chat(body.prompt, provider=provider, model=body.model)
        return ChatOut(reply=reply, provider=provider, model=body.model or "")
    except ChatError as e:
        raise HTTPException(status_code=400, detail={"error": "chat_error", "message": str(e)})
