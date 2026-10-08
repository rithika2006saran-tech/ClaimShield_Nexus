from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router

app = FastAPI(title="ClaimShield Nexus API", version="1.0.0",
              description="Evidence-connected healthcare FWA investigation intelligence. Synthetic data only. Outputs are investigation leads for human review.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/")
def root():
    return {"name": "ClaimShield Nexus", "docs": "/docs", "health": "/api/health"}
