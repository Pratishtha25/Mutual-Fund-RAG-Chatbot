import logging
import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from apscheduler.schedulers.background import BackgroundScheduler

# Add backend and ingestion directories to sys.path so we can import ingestion modules
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(backend_path, "ingestion"))
sys.path.insert(0, backend_path)
from ingestion.corpus_compiler import compile_corpus

from app.guardrails import (
    is_pii,
    is_advisory,
    get_pii_response,
    get_advisory_response
)
from app.search import SimilarityIndex
from app.llm import generate_cited_answer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize the global similarity index singleton
index = SimilarityIndex()

# Initialize background scheduler
scheduler = BackgroundScheduler()


def sync_data_job():
    """
    Background job to scrape/parse fresh data, rebuild corpus.json atomically,
    and trigger a hot-reload of the in-memory similarity matrix cache.
    """
    logger.info("Scheduler triggered data synchronization job...")
    raw_dir = "backend/data/raw_documents"
    out_file = "backend/data/corpus.json"
    try:
        # 1. Compile fresh corpus.json atomically
        compile_corpus(raw_dir, out_file)
        logger.info("Scheduler: Fresh corpus compiled.")
        
        # 2. Reload index (which checks hash, loads/re-vectorizes, and calls gc.collect)
        index.load()
        logger.info("Scheduler: In-memory SimilarityIndex reloaded.")
    except Exception as e:
        logger.error(f"Scheduler: Error during background sync: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown lifecycle events.
    At startup, loads/vectorizes corpus.json and starts background scheduler.
    At shutdown, stops the background scheduler.
    """
    logger.info("Starting up Groww FAQ Assistant API...")
    try:
        index.load()
        logger.info("Similarity index loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load similarity index during startup: {e}")
        
    try:
        # Schedule daily data sync at 10:00 IST (10am daily)
        scheduler.add_job(sync_data_job, 'cron', hour=10, minute=0, timezone='Asia/Kolkata', id="daily_sync")
        # Schedule weekly mf check on Friday at 10:00 IST (10am weekly)
        scheduler.add_job(sync_data_job, 'cron', day_of_week='fri', hour=10, minute=0, timezone='Asia/Kolkata', id="weekly_sync")
        
        scheduler.start()
        logger.info("Background scheduler started successfully.")
    except Exception as e:
        logger.error(f"Failed to start background scheduler: {e}")

    yield

    logger.info("Shutting down Groww FAQ Assistant API...")
    try:
        scheduler.shutdown()
        logger.info("Background scheduler shut down successfully.")
    except Exception as e:
        logger.error(f"Failed to shut down background scheduler: {e}")


app = FastAPI(
    title="Groww FAQ Assistant API",
    description="Factual, secure chatbot for Groww mutual funds and stock details.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration to allow local development connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    # Enforces 300 character input constraint in both frontend and backend
    message: str = Field(..., max_length=300, description="The user query (max 300 characters).")


class ChatResponse(BaseModel):
    status: str
    answer: str
    is_deflected: bool
    contains_pii: bool


@app.post("/api/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(request: ChatRequest):
    query = request.message.strip()

    # 1. Ingress Guardrail: PII Scanner
    if is_pii(query):
        logger.info("PII pattern matched. Blocking query.")
        return ChatResponse(
            status="success",
            answer=get_pii_response(),
            is_deflected=False,
            contains_pii=True
        )

    # 2. Ingress Guardrail: Advisory Keyword Deflector
    if is_advisory(query):
        logger.info("Advisory/speculative intent matched. Deflecting query.")
        return ChatResponse(
            status="success",
            answer=get_advisory_response(),
            is_deflected=True,
            contains_pii=False
        )

    # 3. Retrieval Coordinator & Semantic Search
    chunks, is_deflected_retrieval = index.search(query)
    if is_deflected_retrieval:
        logger.info("Retrieval returned empty/deflected matches (score cutoff or entity mismatch).")
        return ChatResponse(
            status="success",
            answer="I do not have this information in my verified records.",
            is_deflected=False,
            contains_pii=False
        )

    # 4. LLM Synthesis & Post-processing
    logger.info(f"Retrieved {len(chunks)} chunks. Querying local LLM...")
    answer = generate_cited_answer(query, chunks)

    return ChatResponse(
        status="success",
        answer=answer,
        is_deflected=False,
        contains_pii=False
    )
