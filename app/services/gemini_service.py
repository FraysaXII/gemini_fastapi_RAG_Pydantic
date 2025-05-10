import google.generativeai as genai # type: ignore
from google.generativeai.types import GenerationConfigDict, SafetySettingDict, ContentDict, PartDict # type: ignore
from google.generativeai.generative_models import GenerativeModel, ChatSession as GeminiChatSessionInternal # type: ignore
import logging
import uuid
from typing import List, Dict, Optional, AsyncGenerator, Any, cast
from datetime import datetime

from app.core.config import settings
from app.models.gemini_models import (
    Content as PydanticContent,
    Part as PydanticPart,
    GenerationConfig as PydanticGenerationConfig,
    SafetySetting as PydanticSafetySetting,
    StartChatRequest,
    StartChatResponse,
    SendMessageRequest,
    MessageResponse,
    StreamedMessagePart,
    GetHistoryResponse,
    Candidate as PydanticCandidate,
    GeminiMessageResponse as PydanticGeminiResponse
)
import logfire # type: ignore
from app.services.supabase_service import SupabaseService
from app.models.supabase_models import (
    CreateSessionRequest,
    UpdateSessionRequest
)

logger = logging.getLogger(__name__)

# In-memory store for chat sessions. For production, use a persistent store.
# Maps session_id (str) to Gemini SDK's ChatSession object and model name
_active_chat_sessions: Dict[str, Dict[str, Any]] = {}

def _pydantic_content_to_sdk(pydantic_content_list: List[PydanticContent]) -> List[ContentDict]:
    sdk_history = []
    for pc in pydantic_content_list:
        parts = []
        for p_part in pc.parts:
            part_dict: PartDict = {}
            if p_part.text is not None:
                part_dict['text'] = p_part.text
            # Add other part types like inline_data if needed
            parts.append(part_dict)
        
        content_dict: ContentDict = {"parts": parts}
        if pc.role:
            content_dict["role"] = pc.role
        sdk_history.append(content_dict)
    return sdk_history

def _sdk_content_to_pydantic(sdk_content: Any) -> PydanticContent:
    """Convert Gemini SDK Content object to Pydantic Content model."""
    pydantic_parts = []
    # SDK Content object has parts attribute directly
    for sdk_part in sdk_content.parts:
        # SDK Part object has text attribute directly
        pydantic_parts.append(PydanticPart(text=sdk_part.text))
    return PydanticContent(parts=pydantic_parts, role=sdk_content.role)

def _sdk_history_to_pydantic(sdk_history: List[Any]) -> List[PydanticContent]:
    """Convert list of Gemini SDK Content objects to list of Pydantic Content models."""
    return [_sdk_content_to_pydantic(c) for c in sdk_history]

class GeminiChatService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            logfire.error("Gemini API key not configured. GeminiChatService will not function.")
            raise ValueError("GEMINI_API_KEY must be configured")
        
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Initialize Supabase service if credentials are available
            self.supabase = SupabaseService() if settings.SUPABASE_URL and settings.SUPABASE_KEY else None
            if not self.supabase:
                logfire.warning("Supabase URL or Key not configured. Running without persistent storage.")
            # Initialize the in-memory chat sessions store
            self._active_chat_sessions: Dict[str, Dict[str, Any]] = {}
            logfire.info("GeminiChatService initialized successfully")
        except Exception as e:
            logfire.error(f"Failed to initialize GeminiChatService: {e}", exc_info=True)
            raise

    def _create_chat_session(self, model_name: str, history: List[Dict[str, Any]]) -> Any:
        """Creates a new Gemini chat session."""
        try:
            model = genai.GenerativeModel(model_name)
            chat = model.start_chat(history=history)
            return chat
        except Exception as e:
            logfire.error(f"Failed to create Gemini chat session: {e}", exc_info=True)
            raise

    @logfire.instrument("Starting new chat session", extract_args=True)
    async def start_chat_session(self, request: StartChatRequest) -> StartChatResponse:
        """Starts a new chat session with optional initial history."""
        try:
            session_id = str(uuid.uuid4())
            
            # Convert initial history to dictionaries if present
            initial_history_dicts = []
            if request.initial_history:
                for content in request.initial_history:
                    # Convert Content model to dictionary with proper structure
                    content_dict = {
                        "parts": [
                            {"text": part.text} if part.text is not None else part.model_dump(exclude_none=True)
                            for part in content.parts
                        ],
                        "role": content.role
                    }
                    initial_history_dicts.append(content_dict)
            
            # Create session in Supabase if available
            if self.supabase:
                create_request = CreateSessionRequest(
                    model_name=request.model_name,
                    initial_history=initial_history_dicts,
                    metadata={
                        "generation_config": request.generation_config.model_dump() if request.generation_config else None,
                        "safety_settings": [s.model_dump() for s in request.safety_settings] if request.safety_settings else None
                    }
                )
                
                logfire.info(f"Creating session in Supabase with model: {request.model_name}")
                supabase_response = await self.supabase.create_session(create_request)
                if not supabase_response:
                    error_msg = "Failed to create session in database - check Supabase logs for details"
                    logfire.error(error_msg)
                    raise ValueError(error_msg)
                
                # Use the session_id from Supabase
                session_id = supabase_response.session_id
                logfire.info(f"Successfully created session in Supabase with ID: {session_id}")
            else:
                logfire.info("Running without Supabase persistence")
            
            # Create Gemini chat session
            chat = self._create_chat_session(
                request.model_name,
                initial_history_dicts
            )
            
            # Store chat object in memory
            self._active_chat_sessions[session_id] = {"session": chat, "model_name": request.model_name}
            
            logger.info(f"Started new chat session {session_id} with model {request.model_name}")
            logfire.info(f"New chat session created: {{session_id=!r}}", session_id=session_id)

            # Convert the SDK history back to Pydantic
            current_pydantic_history = _sdk_history_to_pydantic(chat.history)

            return StartChatResponse(
                session_id=session_id,
                history=current_pydantic_history,
                initial_message=None
            )
        except Exception as e:
            # Capture full error information
            error_msg = str(e)
            logfire.error(f"Error starting chat session: {error_msg}", exc_info=True)
            # Re-raise the same exception but with a clearer message for debugging
            if "failed to create session" in error_msg.lower():
                # Add diagnostic information to error message
                raise ValueError(f"Database error: {error_msg}. Check Supabase connection and schema.")
            raise

    @logfire.instrument("Sending message to chat session", extract_args=True)
    async def send_message(self, request: SendMessageRequest) -> MessageResponse:
        """Sends a message to an existing chat session."""
        try:
            # Get session from Supabase if available
            session = None
            if self.supabase:
                session = await self.supabase.get_session(request.session_id)
                if not session:
                    raise ValueError(f"Session {request.session_id} not found")
            
            # Get or create chat object
            chat = self._active_chat_sessions.get(request.session_id)
            if not chat:
                if session:
                    chat = self._create_chat_session(session.model_name, session.history)
                else:
                    raise ValueError(f"Session {request.session_id} not found")
                self._active_chat_sessions[request.session_id] = chat
            
            # Convert message to dictionary
            message_dict = {
                "parts": [{"text": part.text} if part.text is not None else part.model_dump() for part in request.message.parts],
                "role": request.message.role
            }
            
            # Send message to Gemini
            response = chat.send_message(
                message_dict,
                generation_config=request.generation_config.model_dump() if request.generation_config else None,
                safety_settings=[s.model_dump() for s in request.safety_settings] if request.safety_settings else None
            )
            
            # Convert response to dictionary
            response_dict = {
                "parts": [{"text": part.text} for part in response.parts],
                "role": response.role
            }
            
            # Update history in Supabase if available
            if self.supabase:
                new_history = (session.history if session else []) + [message_dict, response_dict]
                update_request = UpdateSessionRequest(history=new_history)
                updated_session = await self.supabase.update_session_history(request.session_id, update_request)
                if not updated_session:
                    raise ValueError("Failed to update session history")
            
            return MessageResponse(
                session_id=request.session_id,
                response=Content(**response_dict),
                updated_history=[Content(**msg) for msg in [message_dict, response_dict]]
            )
        except Exception as e:
            logfire.error(f"Error sending message: {e}", exc_info=True)
            raise

    async def send_message_stream(self, request: SendMessageRequest) -> AsyncGenerator[StreamedMessagePart, None]:
        """Streams a message response from an existing chat session."""
        async with logfire.span("Sending message to chat session (streaming)", extract_args=True, session_id=request.session_id, stream=request.stream):
            try:
                # Get session from Supabase if available
                session = None
                if self.supabase:
                    session = await self.supabase.get_session(request.session_id)
                    if not session:
                        raise ValueError(f"Session {request.session_id} not found")
                
                # Get or create chat object
                chat = self._active_chat_sessions.get(request.session_id)
                if not chat:
                    if session:
                        chat = self._create_chat_session(session.model_name, session.history)
                    else:
                        raise ValueError(f"Session {request.session_id} not found")
                    self._active_chat_sessions[request.session_id] = chat
                
                # Convert message to dictionary
                message_dict = {
                    "parts": [{"text": part.text} if part.text is not None else part.model_dump() for part in request.message.parts],
                    "role": request.message.role
                }
                
                # Stream response from Gemini
                response_stream = chat.send_message(
                    message_dict,
                    generation_config=request.generation_config.model_dump() if request.generation_config else None,
                    safety_settings=[s.model_dump() for s in request.safety_settings] if request.safety_settings else None,
                    stream=True
                )
                
                collected_parts = []
                async for chunk in response_stream:
                    collected_parts.append(chunk)
                    yield StreamedMessagePart(
                        session_id=request.session_id,
                        chunk_text=chunk.text,
                        is_final_chunk=False
                    )
                
                # Create final response dictionary
                final_response_dict = {
                    "parts": [{"text": "".join(p.text for p in collected_parts)}],
                    "role": "model"
                }
                
                # Update history in Supabase if available
                if self.supabase:
                    new_history = (session.history if session else []) + [message_dict, final_response_dict]
                    update_request = UpdateSessionRequest(history=new_history)
                    updated_session = await self.supabase.update_session_history(request.session_id, update_request)
                    if not updated_session:
                        raise ValueError("Failed to update session history")
                
                # Send final chunk
                yield StreamedMessagePart(
                    session_id=request.session_id,
                    is_final_chunk=True,
                    full_response_part=Part(text="".join(p.text for p in collected_parts))
                )
            except Exception as e:
                logfire.error(f"Error streaming message: {e}", exc_info=True)
                yield StreamedMessagePart(
                    session_id=request.session_id,
                    error=str(e)
                )

    @logfire.instrument("Getting chat history", extract_args=True)
    async def get_chat_history(self, session_id: str) -> GetHistoryResponse:
        """Retrieves the chat history for a session."""
        try:
            if self.supabase:
                session = await self.supabase.get_session(session_id)
                if not session:
                    raise ValueError(f"Session {session_id} not found")
                return GetHistoryResponse(
                    session_id=session_id,
                    history=session.history
                )
            else:
                # If no Supabase, return empty history
                return GetHistoryResponse(
                    session_id=session_id,
                    history=[]
                )
        except Exception as e:
            logfire.error(f"Error getting chat history: {e}", exc_info=True)
            raise

    @logfire.instrument("Deleting chat session", extract_args=True)
    async def delete_chat_session(self, session_id: str) -> Dict[str, str]:
        """Deletes a chat session."""
        try:
            # Remove from memory
            self._active_chat_sessions.pop(session_id, None)
            
            # Delete from Supabase if available
            if self.supabase:
                response = await self.supabase.delete_session(session_id)
                if not response:
                    raise ValueError(f"Failed to delete session {session_id}")
            
            logger.info(f"Deleted chat session: {session_id}")
            logfire.info(f"Chat session deleted: {{session_id=!r}}", session_id=session_id)
            return {"message": f"Session {session_id} deleted successfully"}
        except Exception as e:
            logfire.error(f"Error deleting chat session: {e}", exc_info=True)
            raise

    @logfire.instrument("Generating content with vision", extract_args=True) # type: ignore
    async def generate_content_with_image(
        self,
        image_file: Any, # FastAPI UploadFile
        prompt: Optional[str],
        model_name: str,
        generation_config: Optional[PydanticGenerationConfig] = None,
        safety_settings: Optional[List[PydanticSafetySetting]] = None,
    ) -> PydanticGeminiResponse: # Reusing GeminiMessageResponse for detailed output
        import base64
        from PIL import Image # type: ignore
        import io

        logger.info(f"Generating content with image using model: {model_name}")

        image_bytes = await image_file.read()
        
        # Determine MIME type (simple check, can be enhanced)
        mime_type = image_file.content_type
        if not mime_type or not mime_type.startswith("image/"):
             # Attempt to infer if not provided or incorrect
            try:
                img = Image.open(io.BytesIO(image_bytes))
                if img.format:
                    inferred_mime_type = Image.MIME.get(img.format.upper())
                    if inferred_mime_type:
                        mime_type = inferred_mime_type
                    else: # Fallback if format not in Image.MIME (e.g. WEBP might need specific handling)
                        logger.warning(f"Could not infer MIME type from PIL Image format: {img.format}. Defaulting to application/octet-stream.")
                        mime_type = "application/octet-stream" # Or raise error
                else:
                    raise ValueError("Cannot determine image format from content.")
            except Exception as e:
                logger.error(f"Error processing image to determine MIME type: {e}")
                raise ValueError(f"Invalid or unsupported image file: {e}")
        
        logger.debug(f"Image MIME type: {mime_type}")

        # Prepare parts for Gemini API
        content_parts = []
        if prompt:
            content_parts.append(PartDict(text=prompt))
        
        content_parts.append(PartDict(inline_data=PartDict(mime_type=mime_type, data=base64.b64encode(image_bytes).decode("utf-8"))))

        model = genai.GenerativeModel(model_name)

        generation_config_sdk: Optional[GenerationConfigDict] = None
        if generation_config:
            generation_config_sdk = cast(GenerationConfigDict, generation_config.model_dump(exclude_none=True))
            
        safety_settings_sdk: Optional[List[SafetySettingDict]] = None
        if safety_settings:
            safety_settings_sdk = cast(List[SafetySettingDict], [s.model_dump() for s in safety_settings])
        
        try:
            with logfire.span("gemini_sdk.generate_content_vision", model_name=model_name):
                response = await model.generate_content_async( # Use async version
                    contents=content_parts, # generate_content takes a list of parts or full ContentDict items
                    generation_config=generation_config_sdk,
                    safety_settings=safety_settings_sdk,
                    # stream=False # Default for generate_content
                )
            
            logfire.info("Successfully received response from Gemini vision model.")

            # Convert SDK response to Pydantic model
            # This is a simplified conversion, assuming response.candidates structure
            pydantic_candidates = []
            if response.candidates:
                for candidate_proto in response.candidates:
                    # Assuming candidate_proto.content is an SDK Content object
                    # and candidate_proto.content.parts is a list of SDK Part objects
                    sdk_content_parts = []
                    if candidate_proto.content and candidate_proto.content.parts:
                         for sdk_part_obj in candidate_proto.content.parts:
                            # Convert each SDK Part object to PartDict
                            # This depends on the actual structure of sdk_part_obj
                            # Assuming it has a .text attribute
                            part_text = getattr(sdk_part_obj, 'text', None)
                            sdk_content_parts.append(PydanticPart(text=part_text))
                    
                    pydantic_content = PydanticContent(
                        parts=sdk_content_parts, 
                        role=candidate_proto.content.role if candidate_proto.content else "model"
                    )
                    
                    pydantic_candidates.append(
                        PydanticCandidate(
                            content=pydantic_content,
                            finish_reason=candidate_proto.finish_reason.name if candidate_proto.finish_reason else None,
                            safety_ratings=[type(sr).to_dict(sr) for sr in candidate_proto.safety_ratings] if candidate_proto.safety_ratings else None,
                            # token_count needs to be accessed correctly if available
                        )
                    )
            
            prompt_feedback_dict = None
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                 prompt_feedback_dict = type(response.prompt_feedback).to_dict(response.prompt_feedback)


            return PydanticGeminiResponse(
                candidates=pydantic_candidates,
                prompt_feedback=prompt_feedback_dict
            )

        except Exception as e:
            logger.error(f"Error generating content with vision model {model_name}: {e}", exc_info=True)
            logfire.error(f"Gemini SDK vision error: {e!s}", model_name=model_name)
            raise

# Helper to convert SDK's GenerateContentResponse to Pydantic model
# This might be used if we call generate_content directly instead of chat sessions
# For chat, the history management within the ChatSession object is key.

# def _sdk_generate_content_response_to_pydantic(
#     sdk_response: genai.types.GenerateContentResponse
# ) -> PydanticGeminiResponse:
#     candidates = []
#     for candidate_proto in sdk_response.candidates:
#         content_dict = type(candidate_proto.content).to_dict(candidate_proto.content)
#         pydantic_content = _sdk_content_to_pydantic(content_dict)
#         candidates.append(
#             PydanticCandidate(
#                 content=pydantic_content,
#                 finish_reason=candidate_proto.finish_reason.name if candidate_proto.finish_reason else None,
#                 safety_ratings=[type(sr).to_dict(sr) for sr in candidate_proto.safety_ratings],
#                 # token_count=candidate_proto.token_count # Check exact attribute
#             )
#         )
#     prompt_feedback_dict = type(sdk_response.prompt_feedback).to_dict(sdk_response.prompt_feedback) \
#                            if sdk_response.prompt_feedback else None
#     return PydanticGeminiResponse(candidates=candidates, prompt_feedback=prompt_feedback_dict) 