# app/services/supabase_service.py
from supabase import create_client, Client
from typing import Optional
import logfire
from datetime import datetime

from app.core.config import settings
from app.models.supabase_models import (
    ChatSession,
    CreateSessionRequest,
    UpdateSessionRequest,
    SessionResponse,
    DeleteSessionResponse
)

class SupabaseService:
    def __init__(self):
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            logfire.error("Supabase URL or Key not configured. SupabaseService will not function.")
            self.client: Optional[Client] = None
        else:
            try:
                self.client: Optional[Client] = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                logfire.info("Supabase client initialized successfully")
            except Exception as e:
                logfire.error(f"Failed to initialize Supabase client: {e}", exc_info=True)
                self.client = None
        
        self.db_schema = settings.SUPABASE_DB_SCHEMA
        self.sessions_table = "chat_sessions"

    async def get_session(self, session_id: str) -> Optional[SessionResponse]:
        """Retrieves a session by its ID."""
        if not self.client:
            logfire.warning("Supabase client not initialized. Cannot get session.")
            return None
        try:
            response = await self.client.table(self.sessions_table)\
                .select("*")\
                .eq("session_id", session_id)\
                .schema(self.db_schema)\
                .execute()
            
            if not response.data:
                logfire.warning(f"Session {session_id} not found")
                return None
                
            session_data = response.data[0]
            return SessionResponse(**session_data)
        except Exception as e:
            logfire.error(f"Error getting session {session_id} from Supabase: {e}", exc_info=True)
            return None

    async def create_session(self, request: CreateSessionRequest) -> Optional[SessionResponse]:
        """Creates a new session."""
        if not self.client:
            logfire.warning("Supabase client not initialized. Cannot create session.")
            return None
        try:
            session = ChatSession(
                model_name=request.model_name,
                history=request.initial_history,
                metadata=request.metadata
            )
            
            response = await self.client.table(self.sessions_table)\
                .insert(session.model_dump())\
                .schema(self.db_schema)\
                .execute()
            
            if not response.data:
                logfire.error("Failed to create session - no data returned")
                return None
                
            return SessionResponse(**response.data[0])
        except Exception as e:
            logfire.error(f"Error creating session in Supabase: {e}", exc_info=True)
            return None

    async def update_session_history(self, session_id: str, request: UpdateSessionRequest) -> Optional[SessionResponse]:
        """Updates the history for an existing session."""
        if not self.client:
            logfire.warning("Supabase client not initialized. Cannot update session.")
            return None
        try:
            update_data = {
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if request.history is not None:
                update_data["history"] = request.history
            if request.metadata is not None:
                update_data["metadata"] = request.metadata
            if request.model_name is not None:
                update_data["model_name"] = request.model_name
                
            response = await self.client.table(self.sessions_table)\
                .update(update_data)\
                .eq("session_id", session_id)\
                .schema(self.db_schema)\
                .execute()
            
            if not response.data:
                logfire.warning(f"Session {session_id} not found for update")
                return None
                
            return SessionResponse(**response.data[0])
        except Exception as e:
            logfire.error(f"Error updating session {session_id} in Supabase: {e}", exc_info=True)
            return None

    async def delete_session(self, session_id: str) -> Optional[DeleteSessionResponse]:
        """Deletes a session by its ID."""
        if not self.client:
            logfire.warning("Supabase client not initialized. Cannot delete session.")
            return None
        try:
            response = await self.client.table(self.sessions_table)\
                .delete()\
                .eq("session_id", session_id)\
                .schema(self.db_schema)\
                .execute()
            
            if not response.data:
                logfire.warning(f"Session {session_id} not found for deletion")
                return None
                
            return DeleteSessionResponse(
                session_id=session_id,
                message="Session deleted successfully"
            )
        except Exception as e:
            logfire.error(f"Error deleting session {session_id} from Supabase: {e}", exc_info=True)
            return None

# Instantiate the service (or use FastAPI dependency injection later)
# supabase_service = SupabaseService()