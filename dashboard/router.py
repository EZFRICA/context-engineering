from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from app.core.memory.engine import MemoryEngine
from app.core.memory.schema import get_weaviate_client

router = APIRouter()
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
memory_engine = MemoryEngine()

class FactUpdate(BaseModel):
    # For now, just a dummy for manual injection if needed
    content: str
    tags: str = ""

@router.get("/dashboard", response_class=HTMLResponse)
async def list_trips(request: Request):
    """List all available trips (Scopes) from MemoryBank."""
    client = get_weaviate_client()
    try:
        collection = client.collections.get("MemoryBank")
        response = collection.query.fetch_objects(limit=50)
        
        unique_scopes = set()
        for obj in response.objects:
            scope = obj.properties.get("context_scope")
            if scope:
                unique_scopes.add(scope)
        
        trips = [{"trip_id": s} for s in unique_scopes]
        return templates.TemplateResponse("index.html", {"request": request, "trips": trips})
    finally:
        client.close()

@router.get("/dashboard/{trip_id}", response_class=HTMLResponse)
async def read_dashboard(request: Request, trip_id: str):
    return templates.TemplateResponse("dashboard.html", {"request": request, "trip_id": trip_id})

@router.get("/api/trip/{trip_id}")
async def get_trip_api(trip_id: str):
    # Returns raw facts as a list (not wrapped in dict)
    facts = memory_engine.get_editor_view(trip_id)
    return facts

@router.post("/api/trip/{trip_id}")
async def update_trip_manual(trip_id: str, update: FactUpdate):
    # Manual injection via Dashboard -> Direct Write (Bypass LLM)
    memory_engine.add_memory(trip_id, update.content, tags=["manual", "user-override"])
    return {"status": "success"}

@router.post("/api/trip/{trip_id}/approve/{fact_id}")
async def approve_fact_endpoint(trip_id: str, fact_id: str):
    memory_engine.approve_fact(fact_id)
    return {"status": "approved"}

@router.delete("/api/trip/{trip_id}/fact/{fact_id}")
async def reject_fact_endpoint(trip_id: str, fact_id: str):
    memory_engine.delete_fact(fact_id)
    return {"status": "deleted"}
