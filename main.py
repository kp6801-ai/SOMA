import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from database import create_tables, seed_label_relationships
from routes import router

load_dotenv()

app = FastAPI(title="SOMA API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    return {"status": "healthy", "environment": os.getenv("ENVIRONMENT")}