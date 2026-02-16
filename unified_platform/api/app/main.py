from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.init_db import seed_defaults
from app.db.session import SessionLocal, engine
from app.models import core, integration, inventory, mdm, pim, procurement, sales  # noqa: F401
from app.ws.manager import ws_manager

app = FastAPI(title=settings.app_name, openapi_url=f"{settings.api_v1_prefix}/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
def startup() -> None:
    # Runtime guard for local starts without migrations.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok"}


@app.websocket("/api/v1/ws/dashboard")
async def ws_dashboard(websocket: WebSocket) -> None:
    channel = "dashboard"
    await ws_manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(channel, websocket)


@app.websocket("/api/v1/ws/inventory/{location_id}")
async def ws_inventory(websocket: WebSocket, location_id: int) -> None:
    channel = f"inventory:{location_id}"
    await ws_manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(channel, websocket)


@app.websocket("/api/v1/ws/receiving/{shipment_id}")
async def ws_receiving(websocket: WebSocket, shipment_id: int) -> None:
    channel = f"receiving:{shipment_id}"
    await ws_manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(channel, websocket)


@app.websocket("/api/v1/ws/sync-status")
async def ws_sync_status(websocket: WebSocket) -> None:
    channel = "sync-status"
    await ws_manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(channel, websocket)
