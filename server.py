from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
from dashboard.router import router as dashboard_router
import os

app = FastAPI()

# Mount dashboard router
app.include_router(dashboard_router)

# Optional: Mount static files if needed (e.g. for CSS)
# app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    print("Starting Travel Architect API & Dashboard...")
    uvicorn.run("server:app", host="0.0.0.0", port=8081, reload=True)
