"""
Quick local runner for the chat smoke test.

Usage (PowerShell):
  $env:OPENAI_API_KEY = "sk-..."; python run_local.py
or ensure backend-fastapi/.env contains OPENAI_API_KEY.
"""
from __future__ import annotations

from .client import simple_chat

if __name__ == "__main__":
    prompt = "Say 'hello' in one word."
    print("Prompt:", prompt)
    reply = simple_chat(prompt)
    print("Reply:", reply)
