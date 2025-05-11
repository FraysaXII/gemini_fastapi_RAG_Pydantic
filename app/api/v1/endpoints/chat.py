from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, Dict
import logging
import logfire # type: ignore

from app.services.gemini_service import GeminiChatService
from app.models.gemini_models import (
    StartChatRequest,
    StartChatResponse,
    SendMessageRequest,
    MessageResponse,
    GetHistoryResponse,
    StreamedMessagePart
)
from app.core.config import settings # For potential direct use or inspection

router = APIRouter()
logger = logging.getLogger(__name__)

# Dependency for GeminiChatService
# This allows FastAPI to manage the lifecycle of the service if needed,
# or simply provide an instance. For this simple case, a new instance is created per request group.
# For a more complex app, you might initialize it once and share.
def get_gemini_service():
    # logfire.attach_current_trace_to_logs() # If you want to link standard logs to logfire traces
    return GeminiChatService()

@router.post("/start_session", 
            response_model=StartChatResponse, 
            summary="Start a New Chat Session", 
            description="Initializes a new chat session with the Gemini API. Users can optionally provide an initial history to set the context for the conversation, along with generation configurations and safety settings. A unique session ID is returned, which is used for subsequent interactions within the same conversation. If Supabase is configured, session metadata (excluding history for this initial call) will be persisted."
)
async def start_session(
    request: StartChatRequest = Body(...),
    service: GeminiChatService = Depends(get_gemini_service)
):
    """
    Initializes a new chat session with the Gemini API.
    You can provide an initial history to set the context for the conversation.
    """
    try:
        logfire.info(f"Attempting to start chat session with model: {request.model_name}")
        response = await service.start_chat_session(request)
        logfire.info(f"Successfully started chat session: {response.session_id}")
        return response
    except ValueError as ve:
        error_message = str(ve)
        logger.error(f"Value error starting chat session: {error_message}")
        logfire.error(f"API Value Error starting chat session: {error_message}")
        if "database" in error_message.lower() or "supabase" in error_message.lower():
            # Database related error
            raise HTTPException(status_code=500, 
                                detail=f"Database error: {error_message}. Please check Supabase connection and configuration.")
        else:
            # Other validation errors
            raise HTTPException(status_code=400, detail=error_message)
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error starting chat session: {error_message}", exc_info=True)
        logfire.error(f"API Error starting chat session: {error_message}", exc_info=True)
        raise HTTPException(status_code=500, 
                           detail=f"Server error when starting chat session: {error_message}")

@router.post("/send_message", 
            summary="Send a Message to a Chat Session",
            description="Sends a message from the user to an existing chat session identified by `session_id`. \n\n- **Non-Streaming**: If `stream` is `False` (default), the full response from the Gemini model is returned after processing. Session history is updated if Supabase is configured.\n- **Streaming**: If `stream` is `True`, the response is streamed back as newline-delimited JSON objects (`StreamedMessagePart`). This is suitable for applications that want to display the response incrementally. The full interaction history is updated in Supabase (if configured) after the stream completes."
)
async def send_message_endpoint(
    request: SendMessageRequest = Body(...),
    service: GeminiChatService = Depends(get_gemini_service)
):
    """
    Sends a message to an existing chat session. 
    Set `stream` to `True` to receive a streaming response.
    Otherwise, a complete `MessageResponse` will be returned.
    """
    logfire.info(f"Received message for session: {request.session_id}, stream: {request.stream}")
    if request.stream:
        try:
            # Ensure the service method is async if it truly does async work with SDK
            # For now, assuming send_message_stream is an async generator
            async def stream_generator() -> AsyncGenerator[str, None]:
                async for part in service.send_message_stream(request):
                    yield part.model_dump_json() + "\n" # Send each part as a JSON string line
            
            return StreamingResponse(stream_generator(), media_type="application/x-ndjson")
        except Exception as e:
            logger.error(f"Error streaming message for session {request.session_id}: {e}", exc_info=True)
            logfire.error(f"API Error streaming message: {e!s}", session_id=request.session_id)
            # StreamingResponse cannot easily convey HTTPExceptions once headers are sent.
            # Errors within the stream should be part of the StreamedMessagePart model.
            # For initial errors (like session not found before stream starts), an HTTPException is fine.
            # Here, we assume the error might happen before streaming starts or is a setup issue.
            raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")
    else:
        try:
            response = await service.send_message(request)
            logfire.info(f"Successfully sent message and received response for session: {request.session_id}")
            return response # FastAPI will serialize this to JSON (MessageResponse model)
        except ValueError as ve: # Specific for session not found or similar logical errors
            logger.warning(f"Value error sending message for session {request.session_id}: {ve}")
            logfire.warn(f"API Value Error: {ve!s}", session_id=request.session_id)
            raise HTTPException(status_code=404, detail=str(ve))
        except Exception as e:
            logger.error(f"Error sending message for session {request.session_id}: {e}", exc_info=True)
            logfire.error(f"API Error sending message: {e!s}", session_id=request.session_id)
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{session_id}", 
            response_model=GetHistoryResponse, 
            summary="Get Chat Session History",
            description="Retrieves the full conversation history for a given chat session ID. If Supabase is configured and the session exists, the persisted history is returned. Otherwise, it might reflect in-memory history or indicate that the session is not found."
)
async def get_history(
    session_id: str,
    service: GeminiChatService = Depends(get_gemini_service)
):
    """
    Retrieves the conversation history for a given chat session ID.
    """
    try:
        logfire.info(f"Requesting history for session: {session_id}")
        response = await service.get_chat_history(session_id)
        logfire.info(f"Successfully retrieved history for session: {session_id}")
        return response
    except ValueError as ve: # Session not found
        logger.warning(f"History not found for session {session_id}: {ve}")
        logfire.warn(f"API History Error: {ve!s}", session_id=session_id)
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error getting history for session {session_id}: {e}", exc_info=True)
        logfire.error(f"API Error getting history: {e!s}", session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/session/{session_id}", 
             response_model=Dict[str, str], 
             summary="Delete a Chat Session",
             description="Deletes a specified chat session. This removes the session from the server\'s active memory and, if Supabase is configured, also deletes the corresponding record from the persistent database."
)
async def delete_session(
    session_id: str,
    service: GeminiChatService = Depends(get_gemini_service)
):
    """
    Deletes a chat session and its history from the server's memory.
    """
    try:
        logfire.info(f"Requesting deletion of session: {session_id}")
        response = await service.delete_chat_session(session_id)
        logfire.info(f"Successfully deleted session: {session_id}")
        return response
    except ValueError as ve: # Session not found
        logger.warning(f"Failed to delete non-existent session {session_id}: {ve}")
        logfire.warn(f"API Delete Error: {ve!s}", session_id=session_id)
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}", exc_info=True)
        logfire.error(f"API Error deleting session: {e!s}", session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e)) 