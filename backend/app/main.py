"""
FastAPI application entrypoint.

Wires together middleware and routers. Business/LLM logic lives in
services/, request-shaping lives in prompts/, and data contracts live in
schemas/ — this file just assembles the app.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import support
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="AI Customer Support Assistant",
    description="Turns messy customer messages into structured, actionable support tickets.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(support.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "AI Customer Support Assistant API", "docs": "/docs"}
