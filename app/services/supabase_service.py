# app/services/supabase_service.py
from supabase import create_client, Client, ClientOptions
from typing import Optional, List
import logfire
from datetime import datetime
import uuid
import asyncio

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
            self.db_schema = None
        else:
            try:
                client_options = ClientOptions(
                    schema=settings.SUPABASE_DB_SCHEMA
                )
                self.client: Optional[Client] = create_client(
                    settings.SUPABASE_URL, 
                    settings.SUPABASE_KEY,
                    options=client_options
                )
                logfire.info(f"Supabase client initialized successfully with schema: {settings.SUPABASE_DB_SCHEMA}")
                self.db_schema = settings.SUPABASE_DB_SCHEMA
            except Exception as e:
                logfire.error(f"Failed to initialize Supabase client: {e}", exc_info=True)
                self.client = None
                self.db_schema = None
        
        self.sessions_table = "chat_sessions"

    async def get_session(self, session_id: str) -> Optional[SessionResponse]:
        """Retrieves a session by its ID."""
        if not self.client:
            logfire.warning("Supabase client not initialized. Cannot get session.")
            return None
        try:
            response = await asyncio.to_thread(
                self.client.table(self.sessions_table)
                .select("*")
                .eq("session_id", session_id)
                .execute
            )
            
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
            session_id = str(uuid.uuid4())
            
            session = ChatSession(
                session_id=session_id,
                model_name=request.model_name,
                history=request.initial_history if request.initial_history is not None else [],
                metadata=request.metadata if request.metadata is not None else {}
                # created_at and updated_at will use default_factory from Pydantic model
            )
            
            logfire.info(f"Creating new session with ID: {session_id} in schema: {self.db_schema}")
            
            # Use model_dump(mode='json') to ensure datetimes are serialized
            session_data_for_insert = session.model_dump(mode='json')
            logfire.debug(f"Data for Supabase insert: {session_data_for_insert}")

            response = await asyncio.to_thread(
                self.client.table(self.sessions_table)
                .insert(session_data_for_insert)
                .execute
            )
            
            if not response.data:
                logfire.error("Failed to create session - no data returned from Supabase")
                return None
                
            # Supabase returns the inserted data, which should already be JSON-serializable
            # If Supabase returns datetime strings, Pydantic will parse them into datetime objects for SessionResponse
            return SessionResponse(**response.data[0])
        except Exception as e:
            error_msg = str(e)
            logfire.error(f"Error creating session in Supabase (schema: {self.db_schema}): {error_msg}", exc_info=True)
            
            if "foreign key constraint" in error_msg.lower():
                logfire.error("Foreign key constraint violation - check if referenced tables exist and have proper data")
            elif "duplicate key" in error_msg.lower():
                logfire.error("Duplicate key violation - a session with this ID already exists")
            elif "column" in error_msg.lower() and "does not exist" in error_msg.lower():
                logfire.error("Column does not exist - check if the table schema matches the model")
            elif "json serializable" in error_msg.lower():
                logfire.error("Data type issue: An object is not JSON serializable. Check datetime or other complex types.")
            
            return None

    async def update_session_history(self, session_id: str, request: UpdateSessionRequest) -> Optional[SessionResponse]:
        """Updates the history for an existing session."""
        if not self.client:
            logfire.warning("Supabase client not initialized. Cannot update session.")
            return None
        try:
            update_data = {
                # Ensure datetime is ISO format string for Supabase
                "updated_at": datetime.utcnow().isoformat() 
            }
            
            if request.history is not None:
                # Assuming history is already a list of dicts (JSON serializable)
                update_data["history"] = request.history 
            if request.metadata is not None:
                 # Assuming metadata is already a dict (JSON serializable)
                update_data["metadata"] = request.metadata
            if request.model_name is not None:
                update_data["model_name"] = request.model_name
            
            logfire.debug(f"Data for Supabase update: {update_data}")

            response = await asyncio.to_thread(
                self.client.table(self.sessions_table)
                .update(update_data)
                .eq("session_id", session_id)
                .execute
            )
            
            if not response.data:
                logfire.warning(f"Session {session_id} not found for update, or update returned no data.")
                return None
                
            return SessionResponse(**response.data[0])
        except Exception as e:
            logfire.error(f"Error updating session {session_id} in Supabase: {e}", exc_info=True)
            return None

    @logfire.instrument("Deleting session by ID", extract_args=True)
    async def delete_session(self, session_id: str) -> Optional[DeleteSessionResponse]:
        """Deletes a session by its ID."""
        logfire.info(f"Deleting session with ID: {session_id} from schema: {self.db_schema}")
        if not self.client:
            logfire.warning("Supabase client not initialized. Cannot delete session.")
            return None
        try:
            response = await asyncio.to_thread(
                self.client.table(self.sessions_table)
                .delete()
                .eq("session_id", session_id)
                .execute
            )
            
            # Check for data OR successful status code
            if response.data or (hasattr(response, 'status_code') and response.status_code in [200, 204]):
                logfire.info(f"Session {session_id} deleted successfully from Supabase.")
                return DeleteSessionResponse(
                    session_id=session_id,
                    message="Session deleted successfully"
                )
            else:
                status_code_msg = f" and status {response.status_code}" if hasattr(response, 'status_code') else ""
                logfire.warning(f"Session {session_id} delete operation returned no data{status_code_msg}.")
                return DeleteSessionResponse(
                    session_id=session_id,
                    message="Session presumed deleted (no data returned or unexpected status)."
                )
        except Exception as e: # Catching generic Exception as per existing file structure
            logfire.error(f"Error deleting session {session_id} in Supabase: {str(e)}", exc_info=True)
            return None

    @logfire.instrument("Getting all sessions", extract_args=True)
    async def get_all_sessions(self, limit: int = 100, offset: int = 0) -> List[SessionResponse]:
        """Retrieves all sessions with pagination."""
        logfire.info(f"Fetching all sessions with limit {limit}, offset {offset} from schema: {self.db_schema}")
        if not self.client:
            logfire.warning("Supabase client not initialized. Cannot get all sessions.")
            return []
        try:
            response = await asyncio.to_thread(
                 self.client.table(self.sessions_table)
                 .select("*")
                 .limit(limit)
                 .offset(offset)
                 .order("created_at", desc=True) # Assuming 'desc' is a valid parameter for PostgREST/supabase-py order
                 .execute
            )
            sessions = []
            if response.data:
                for item in response.data:
                    try:
                        sessions.append(SessionResponse(**item))
                    except Exception as validation_error:
                        logfire.error(f"Validation error parsing session data: {validation_error} for item: {item}", exc_info=True)
                        # Optionally skip this item or handle more gracefully
            return sessions
        except Exception as e:
            logfire.error(f"Error fetching all sessions from Supabase: {str(e)}", exc_info=True)
            return []

# supabase_service = SupabaseService()