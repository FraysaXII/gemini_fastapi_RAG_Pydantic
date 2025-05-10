from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class ChatSession(BaseModel):
    """Pydantic model for chat session data stored in Supabase."""
    session_id: str = Field(..., description="Unique identifier for the chat session")
    model_name: str = Field(..., description="The Gemini model used for this session")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Chat history as a list of message dictionaries")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When the session was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When the session was last updated")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional session metadata")

class CreateSessionRequest(BaseModel):
    """Request model for creating a new chat session."""
    model_name: str = Field(..., description="The Gemini model to use for this session")
    initial_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Optional initial chat history")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional session metadata")

class UpdateSessionRequest(BaseModel):
    """Request model for updating an existing chat session."""
    history: Optional[List[Dict[str, Any]]] = Field(None, description="New chat history to replace existing")
    metadata: Optional[Dict[str, Any]] = Field(None, description="New metadata to update existing")
    model_name: Optional[str] = Field(None, description="New model name to switch to")

class SessionResponse(BaseModel):
    """Response model for session operations."""
    session_id: str = Field(..., description="The session identifier")
    model_name: str = Field(..., description="The model being used")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Current chat history")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Session metadata")

class DeleteSessionResponse(BaseModel):
    """Response model for session deletion."""
    session_id: str = Field(..., description="The deleted session identifier")
    message: str = Field(..., description="Deletion status message") 