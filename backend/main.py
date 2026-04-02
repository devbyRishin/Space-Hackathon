from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api import telemetry, maneuver, simulate, visualization
import os

app = FastAPI(title="Autonomous Constellation Manager", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry.router)
app.include_router(maneuver.router)
app.include_router(simulate.router)
app.include_router(visualization.router)

@app.get("/health")
async def health():
    return {"status": "operational", "system": "ACM v1.0"}

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="frontend")