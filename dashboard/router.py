from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dashboard.core.memory.engine import MemoryEngine
from dashboard.core.memory.schema import get_weaviate_client
from dashboard.core.llm_worker import refactor_memory

router = APIRouter()
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

SYSTEM_CONFIGS = {
    "opaque": {"inbox": "OpaqueInbox", "bank": "OpaqueBank"},
    "user_controlled": {"inbox": "UserInbox", "bank": "UserBank"},
    "hybrid": {"inbox": "HybridInbox", "bank": "HybridBank"},
    "legacy": {"inbox": "MemoryInbox", "bank": "MemoryBank"}
}

def get_engine(system: str = "user_controlled") -> MemoryEngine:
    config = SYSTEM_CONFIGS.get(system, SYSTEM_CONFIGS["user_controlled"])
    return MemoryEngine(inbox_name=config["inbox"], bank_name=config["bank"])

class FactUpdate(BaseModel):
    content: str
    tags: str = ""

@router.get("/dashboard", response_class=HTMLResponse)
async def list_trips(request: Request, system: str = Query("user_controlled")):
    """List all available trips (Scopes) from the selected system."""
    client = get_weaviate_client()
    try:
        config = SYSTEM_CONFIGS.get(system, SYSTEM_CONFIGS["user_controlled"])
        # We check the bank for existing contexts
        collection = client.collections.get(config["bank"])
        response = collection.query.fetch_objects(limit=50)
        
        unique_scopes = set()
        for obj in response.objects:
            scope = obj.properties.get("context_scope")
            if scope:
                unique_scopes.add(scope)
        
        trips = [{"trip_id": s} for s in unique_scopes]
        return templates.TemplateResponse(
            "index.html", 
            {"request": request, "trips": trips, "system": system}
        )
    finally:
        client.close()

@router.get("/dashboard/{trip_id}", response_class=HTMLResponse)
async def read_dashboard(request: Request, trip_id: str, system: str = Query("user_controlled")):
    return templates.TemplateResponse(
        "dashboard.html", 
        {"request": request, "trip_id": trip_id, "system": system}
    )

@router.get("/api/trip/{trip_id}")
async def get_trip_api(trip_id: str, system: str = Query("user_controlled")):
    engine = get_engine(system)
    facts = engine.get_editor_view(trip_id)
    return facts

@router.post("/api/trip/{trip_id}")
async def update_trip_manual(trip_id: str, update: FactUpdate, system: str = Query("user_controlled")):
    engine = get_engine(system)
    engine.add_memory(trip_id, update.content, tags=["manual", "user-override"])
    return {"status": "success"}

@router.post("/api/trip/{trip_id}/batch")
async def batch_sync_endpoint(trip_id: str, request: Request, system: str = Query("user_controlled")):
    data = await request.json()
    engine = get_engine(system)
    # data expected to be a list of facts
    engine.batch_update_facts(trip_id, data)
    return {"status": "synced"}

class MagicRequest(BaseModel):
    current_facts: list
    instruction: str

@router.post("/api/trip/{trip_id}/magic_organize")
async def magic_organize_endpoint(trip_id: str, request: MagicRequest):
    # Call Gemini to transform JSON
    new_facts = refactor_memory(request.current_facts, request.instruction)
    return new_facts

@router.post("/api/trip/{trip_id}/approve/{fact_id}")
async def approve_fact_endpoint(trip_id: str, fact_id: str, system: str = Query("user_controlled")):
    engine = get_engine(system)
    engine.approve_fact(fact_id)
    return {"status": "approved"}

@router.delete("/api/trip/{trip_id}/fact/{fact_id}")
async def reject_fact_endpoint(trip_id: str, fact_id: str, system: str = Query("user_controlled")):
    engine = get_engine(system)
    engine.delete_fact(fact_id)
    return {"status": "deleted"}

@router.put("/api/trip/{trip_id}/fact/{fact_id}")
async def update_fact_endpoint(trip_id: str, fact_id: str, update: FactUpdate, system: str = Query("user_controlled")):
    engine = get_engine(system)
    # Handle tags as string (comma-separated)
    tags_list = [t.strip() for t in update.tags.split(",")] if update.tags else []
    engine.update_fact(fact_id, update.content, tags_list)
    return {"status": "updated"}
