from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import logging
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import logfire # type: ignore

# Load environment variables from .env file early
# This should be one of the first things your application does.
load_dotenv()

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.v1.endpoints import chat as chat_router_v1
from app.api.v1.endpoints import vision as vision_router_v1

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

# Define a more detailed description for the API
api_description = f"""
# Gemini FastAPI Service - Holistika Research & Envoy Tech Lab

**Version:** {settings.OTEL_SERVICE_VERSION}

**Status:** Active

**Security Level:** 3 (Restricted) - For Internal Use

## Overview

This service provides a robust backend interface to Google's Gemini AI models, offering advanced chat and vision functionalities. It is developed using Python 3.x, FastAPI for high-performance API delivery, Pydantic for rigorous data validation, and the `google-generativeai` SDK for seamless interaction with the Gemini API.

The primary objective of this service is to offer a scalable, reliable, and well-documented API for internal Holistika Research projects requiring generative AI capabilities.

## Key Features

*   **Modern FastAPI Backend**: Leverages asynchronous programming for high performance.
*   **Pydantic Data Validation**: Ensures clear data contracts and robust validation for all requests and responses.
*   **Comprehensive Gemini API Integration**:
    *   **Chat Functionality**: Supports starting new chat sessions, sending messages (streaming and non-streaming), retrieving conversation history, and deleting sessions.
    *   **Vision Functionality**: Enables content generation from images and text prompts using vision-capable Gemini models.
*   **Session Management**: Includes capabilities for chat session management. Optionally, it can use Supabase (PostgreSQL) for persistent storage of chat sessions within a dedicated `gemini_fastapi` schema.
*   **Unified Structured Logging**: Integrates standard Python `logging` with Pydantic Logfire, enriched with OpenTelemetry attributes for enhanced observability and centralized log management.
*   **Configuration Management**: Utilizes `pydantic-settings` for flexible environment-based configuration.

## Intended Use

This API is intended for use by internal applications and services within Holistika Research and Envoy Tech Lab that require generative AI capabilities provided by Google's Gemini models.

Refer to the official `SOP-GEMINI_FASTAPI_SERVICE_001_v1.md` for detailed operational procedures, deployment guidelines, and maintenance protocols.
"""

# Define tags with metadata
tags_metadata = [
    {
        "name": "Chat V1",
        "description": "Endpoints for managing chat sessions and sending messages to Gemini chat models. Supports streaming and non-streaming responses. Optionally persists sessions using Supabase.",
    },
    {
        "name": "Vision V1",
        "description": "Endpoints for interacting with Gemini vision-capable models. Allows sending images and text prompts to generate content.",
    },
    {
        "name": "Application Health & Information",
        "description": "Endpoints for checking application status and retrieving basic information.",
    },
]

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.OTEL_SERVICE_VERSION,
    description=api_description.format(settings=settings),
    contact={
        "name": "Holistika Research - Envoy Tech Lab",
        "url": "https://holistikaresearch.com/", # Replace with actual URL if available
        "email": "admin@holistikaresearch.com",    # Replace with actual contact email
    },
    license_info={
        "name": "Proprietary - Restricted Internal Use",
        # "url": "https://example.com/license", # Replace with actual license URL if available
    },
    openapi_tags=tags_metadata,
    swagger_ui_parameters={
        "deepLinking": True,
        "docExpansion": "list", # "none" or "full" are other options
        "filter": True, # Enables filtering by tags
        "showExtensions": True,
        "showCommonExtensions": True,
        "syntaxHighlight.theme": "obsidian" # Example theme, others: "arta", "monokai", "nord", "tomorrow-night"
    }
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

@app.get("/health", tags=["Application Health & Information"], summary="Health Check", description="Performs a basic health check of the application. Returns the application status and a welcome message.")
async def health_check():
    logfire.info("Health check endpoint called.")
    return {"status": "ok", "message": "Welcome to Gemini FastAPI Interface!"}

@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/redoc")

# To run this app (from the root directory `gemini_fastapi_RAG_Pydantic`):
# Ensure you have a .env file with GEMINI_API_KEY
# pip install -r requirements.txt
# uvicorn app.main:app --reload 