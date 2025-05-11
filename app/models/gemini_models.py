from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

# Based on google.generativeai.types.ContentDict and related structures

class Part(BaseModel):
    text: Optional[str] = None
    inline_data: Optional[Dict[str, Any]] = None # For images, etc. {mime_type: str, data: base64_encoded_str}
    # function_call: Optional[FunctionCall] = None # If supporting function calling
    # function_response: Optional[FunctionResponse] = None # If supporting function calling

class Content(BaseModel):
    parts: List[Part]
    role: Optional[str] = None # 'user' or 'model'. SDK handles this based on context.

# Based on google.generativeai.types.GenerationConfigDict
class GenerationConfig(BaseModel):
    candidate_count: Optional[int] = None
    stop_sequences: Optional[List[str]] = None
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None

# Based on google.generativeai.types.SafetySettingDict
class SafetySetting(BaseModel):
    category: Literal[
        "HARM_CATEGORY_UNSPECIFIED",
        "HARM_CATEGORY_DEROGATORY",
        "HARM_CATEGORY_TOXICITY",
        "HARM_CATEGORY_VIOLENCE",
        "HARM_CATEGORY_SEXUAL",
        "HARM_CATEGORY_MEDICAL",
        "HARM_CATEGORY_DANGEROUS",
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    ]
    threshold: Literal[
        "HARM_BLOCK_THRESHOLD_UNSPECIFIED",
        "BLOCK_LOW_AND_ABOVE",
        "BLOCK_MEDIUM_AND_ABOVE",
        "BLOCK_ONLY_HIGH",
        "BLOCK_NONE",
    ]

class ChatSession(BaseModel):
    # This model is for our API representation, not a direct mapping to SDK's ChatSession
    session_id: str = Field(description="Unique identifier for the chat session.")
    history: List[Content] = Field(default_factory=list, description="History of the conversation.")
    # We might not store the actual SDK chat object here for FastAPI responses for simplicity
    # and to avoid serialization issues with complex external objects.
    # Instead, the service layer will manage SDK chat objects mapped by session_id.

class StartChatRequest(BaseModel):
    initial_history: Optional[List[Content]] = Field(None, description="Optional initial history for the chat session.")
    generation_config: Optional[GenerationConfig] = Field(None, description="Optional generation configuration.")
    safety_settings: Optional[List[SafetySetting]] = Field(None, description="Optional safety settings.")
    model_name: str = Field("gemini-2.5-pro-exp-03-25", description="The model to use, e.g., 'gemini-pro' or 'gemini-1.5-pro-latest'.")

class StartChatResponse(BaseModel):
    session_id: str = Field(description="Unique identifier for the newly created chat session.")
    initial_message: Optional[Content] = Field(None, description="Optional initial message from the model if any (e.g., a greeting if history was empty).")
    history: List[Content] = Field(description="The initial history of the chat session, including any messages provided.")


class SendMessageRequest(BaseModel):
    session_id: str = Field(..., description="The ID of the chat session to send the message to.")
    message: Content = Field(..., description="The message content from the user.")
    generation_config: Optional[GenerationConfig] = Field(None, description="Optional generation configuration for this message.")
    safety_settings: Optional[List[SafetySetting]] = Field(None, description="Optional safety settings for this message.")
    stream: bool = Field(False, description="Whether to stream the response.")


class MessageResponse(BaseModel): # For non-streaming
    session_id: str
    response: Content # The model's response message
    updated_history: List[Content] # The full history after this interaction

# For streaming, FastAPI would use a StreamingResponse.
# The items yielded by the stream could be of this type:
class StreamedMessagePart(BaseModel):
    session_id: str
    chunk_text: Optional[str] = None # Part of the model's response
    is_final_chunk: bool = False
    full_response_part: Optional[Part] = None # The assembled Part when is_final_chunk is true
    error: Optional[str] = None

class GetHistoryRequest(BaseModel):
    session_id: str = Field(..., description="The ID of the chat session to retrieve history for.")

class GetHistoryResponse(BaseModel):
    session_id: str
    history: List[Content]

# It's useful to also have a model for the content part of the Gemini SDK's Candidate
class Candidate(BaseModel):
    content: Content
    finish_reason: Optional[str] = None # e.g., "STOP", "MAX_TOKENS", "SAFETY"
    safety_ratings: Optional[List[Dict[str, Any]]] = None # Detailed safety ratings
    token_count: Optional[int] = None

class GeminiMessageResponse(BaseModel): # More detailed, closer to SDK's GenerateContentResponse
    candidates: List[Candidate]
    prompt_feedback: Optional[Dict[str, Any]] = None
    # usage_metadata: Optional[Dict[str, Any]] = None # Available in 1.5 Pro


# --- Vision Specific Models ---

class GenerateWithImageRequest(BaseModel):
    text_prompt: Optional[str] = Field(None, description="Text prompt to accompany the image.")
    # Image will be handled as UploadFile in the endpoint, then converted to a Part by the service.
    # We don't put UploadFile here as Pydantic models are for validated data, not raw file objects.
    model_name: str = Field("gemini-pro-vision", description="The vision-capable model to use, e.g., 'gemini-pro-vision' or a 1.5 pro model name.")
    generation_config: Optional[GenerationConfig] = Field(None, description="Optional generation configuration.")
    safety_settings: Optional[List[SafetySetting]] = Field(None, description="Optional safety settings.")

# We can reuse GeminiMessageResponse for the output of generate_content, as it contains candidates.
# Or define a simpler one if preferred:
class VisionResponse(BaseModel):
    generated_text: Optional[str] = Field(None, description="The text generated by the model in response to the image and/or prompt.")
    # Potentially include more structured data if the model provides it.
    raw_response: Optional[GeminiMessageResponse] = Field(None, description="The full raw response from the Gemini API.")

