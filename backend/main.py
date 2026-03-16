import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
from database import create_tables, seed_label_relationships
from limiter import limiter
from routes import router

load_dotenv()

app = FastAPI(title="SOMA API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_raw_origins = os.getenv("CORS_ORIGINS", "")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {"status": "healthy"}