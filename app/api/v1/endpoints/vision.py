from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from typing import Optional
import logging
import logfire # type: ignore

from app.services.gemini_service import GeminiChatService
from app.models.gemini_models import (
    GenerateWithImageRequest, # Although we take params separately, this can inform structure
    GeminiMessageResponse,   # Corrected import name
    VisionResponse,           # Simple response model option
    GenerationConfig as PydanticGenerationConfig, # For parsing from Form data
    SafetySetting as PydanticSafetySetting
)
from app.core.config import settings
import json # For parsing JSON strings from form data

router = APIRouter()
logger = logging.getLogger(__name__)

# Dependency (same as in chat.py for now)
def get_gemini_service():
    return GeminiChatService()

@router.post("/generate_with_image", response_model=GeminiMessageResponse, summary="Generate content from text and image")
async def generate_with_image(
    image_file: UploadFile = File(..., description="The image file to process."),
    text_prompt: Optional[str] = Form(None, description="Text prompt to accompany the image."),
    model_name: str = Form("gemini-pro-vision", description="The vision-capable model to use."),
    # GenerationConfig and SafetySettings can be passed as JSON strings in the form data
    # and then parsed into their Pydantic models.
    generation_config_json: Optional[str] = Form(None, description="JSON string of GenerationConfig."),
    safety_settings_json: Optional[str] = Form(None, description="JSON string of a list of SafetySetting."),
    service: GeminiChatService = Depends(get_gemini_service)
):
    """
    Generates content based on a provided image and an optional text prompt.
    - **image_file**: The image to analyze.
    - **text_prompt**: Optional text to guide the generation.
    - **model_name**: Specify the vision model (e.g., 'gemini-pro-vision').
    - **generation_config_json**: Optional JSON string for generation parameters.
    - **safety_settings_json**: Optional JSON string for safety settings list.
    """
    logfire.info(f"Received request for /generate_with_image with model: {model_name}")

    parsed_generation_config: Optional[PydanticGenerationConfig] = None
    if generation_config_json:
        try:
            parsed_generation_config = PydanticGenerationConfig(**json.loads(generation_config_json))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON for generation_config_json: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON format for generation_config_json: {e}")
        except Exception as e: # Pydantic validation error
            logger.error(f"Validation error for generation_config_json: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid generation_config values: {e}")

    parsed_safety_settings: Optional[list[PydanticSafetySetting]] = None
    if safety_settings_json:
        try:
            settings_list = json.loads(safety_settings_json)
            if not isinstance(settings_list, list):
                raise ValueError("Safety settings JSON must be a list.")
            parsed_safety_settings = [PydanticSafetySetting(**item) for item in settings_list]
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON for safety_settings_json: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON format for safety_settings_json: {e}")
        except Exception as e: # Pydantic validation error or ValueError
            logger.error(f"Validation error for safety_settings_json: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid safety_settings values: {e}")

    try:
        response_data = await service.generate_content_with_image(
            image_file=image_file,
            prompt=text_prompt,
            model_name=model_name,
            generation_config=parsed_generation_config,
            safety_settings=parsed_safety_settings
        )
        logfire.info("Successfully generated content with image.")
        return response_data 
        # If you prefer the simpler VisionResponse:
        # if response_data.candidates and response_data.candidates[0].content.parts:
        #     generated_text = response_data.candidates[0].content.parts[0].text
        # else:
        #     generated_text = None
        # return VisionResponse(generated_text=generated_text, raw_response=response_data)

    except ValueError as ve:
        logger.warning(f"Value error processing image or request: {ve}", exc_info=True)
        logfire.warn(f"API Value Error (Vision): {ve!s}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error in /generate_with_image endpoint: {e}", exc_info=True)
        logfire.error(f"API Error (Vision): {e!s}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}") 