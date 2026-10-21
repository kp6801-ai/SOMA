import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from database import create_tables, seed_label_relationships
from routes import router

load_dotenv()

app = FastAPI(title="SOMA API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set SOMA_WRITE_KEY in the environment to require `X-API-Key` on every non-GET request.
WRITE_KEY = os.getenv("SOMA_WRITE_KEY", "")


@app.middleware("http")
async def require_write_key(request: Request, call_next):
    if WRITE_KEY and request.method not in ("GET", "HEAD", "OPTIONS"):
        key = request.headers.get("x-api-key", "")
        if not (key and secrets.compare_digest(key, WRITE_KEY)):
            return JSONResponse({"detail": "X-API-Key required for write operations"}, status_code=401)
    return await call_next(request)


@app.on_event("startup")
def startup():
    create_tables()
    seed_label_relationships()

app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {"status": "SOMA API is running"}

@app.get("/health")
def health():
    return {"status": "healthy", "environment": os.getenv("ENVIRONMENT")}