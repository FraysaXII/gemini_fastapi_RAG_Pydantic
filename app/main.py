from fastapi import FastAPI
from dotenv import load_dotenv
import logging
import os

# Load environment variables from .env file early
# This should be one of the first things your application does.
load_dotenv()

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.v1.endpoints import chat as chat_router_v1
from app.api.v1.endpoints import vision as vision_router_v1
import logfire # type: ignore

# Setup logging (including Logfire)
# Must be called after load_dotenv() so settings are populated, 
# and before FastAPI app creation if Logfire needs to instrument it early.
s_setup_logging_done = False
def run_setup_logging_once():
    global s_setup_logging_done
    if not s_setup_logging_done:
        setup_logging()
        s_setup_logging_done = True

run_setup_logging_once()

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.OTEL_SERVICE_VERSION,
    description="A FastAPI backend to interact with Google Gemini API chat functionalities, built with Pydantic."
)

# Instrument FastAPI with Logfire
# This should be called after the FastAPI app instance is created.
try:
    logfire.instrument_fastapi(app)
    logger.info("Logfire FastAPI instrumentation enabled.")
except Exception as e:
    logger.error(f"Failed to instrument FastAPI with Logfire: {e}", exc_info=True)

# Include routers
app.include_router(chat_router_v1.router, prefix="/api/v1/chat", tags=["Chat V1"])
app.include_router(vision_router_v1.router, prefix="/api/v1/vision", tags=["Vision V1"])

@app.on_event("startup")
async def startup_event():
    logger.info("Application startup...")
    logfire.info("FastAPI application starting up.", app_name=settings.APP_NAME)
    # You can add other startup logic here, e.g., connecting to a database if sessions were persistent

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown...")
    logfire.info("FastAPI application shutting down.")
    # Clean up resources here if necessary

@app.get("/health", tags=["Health"])
async def health_check():
    logfire.info("Health check endpoint called.")
    return {"status": "ok", "message": "Welcome to Gemini FastAPI Interface!"}

# To run this app (from the root directory `gemini_fastapi_RAG_Pydantic`):
# Ensure you have a .env file with GEMINI_API_KEY
# pip install -r requirements.txt
# uvicorn app.main:app --reload 