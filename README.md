# Gemini FastAPI Interface

This project provides a robust FastAPI backend interface for interacting with Google's Gemini API, focusing on its chat and vision functionalities. It uses Pydantic for data validation and structuring, follows separation of concerns, and integrates standard Python logging with Pydantic Logfire for unified and enhanced observability.

## Features

- **FastAPI Backend**: Modern, high-performance API framework.
- **Pydantic Models**: For request/response validation and clear data contracts.
- **Gemini API Integration**: Service layer to interact with the `google-generativeai` SDK for chat and vision.
- **Chat Session Management**: Start, send messages to, retrieve history for, and delete chat sessions (in-memory implementation).
- **Streaming Support**: Endpoint for streaming chat responses.
- **Vision Support**: Endpoint for generating content from images and text prompts.
- **Configuration Management**: Using `pydantic-settings` for environment-based configuration.
- **Unified Structured Logging**: Standard Python `logging` routed through `Logfire` for consistent, structured, and enhanced observability. OpenTelemetry attributes enrich this data.
- **Organized Codebase**: Clear separation of concerns (API, services, models, core).

## Project Structure

```
gemini_fastapi_RAG_Pydantic/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application setup
│   ├── api/                    # API routers and endpoints
│   │   └── v1/
│   │       └── __init__.py
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── chat.py     # Chat related API endpoints
│   │           └── vision.py   # Vision related API endpoints
│   ├── core/                   # Core components like config and logging
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── logging_config.py
│   ├── models/                 # Pydantic models
│   │   ├── __init__.py
│   │   └── gemini_models.py
│   └── services/               # Business logic (Gemini interaction)
│       ├── __init__.py
│       └── gemini_service.py
├── .env.example              # Example environment variables
├── README.md                 # This file
└── requirements.txt          # Python dependencies
```

## Prerequisites

- Python 3.9+
- A Google Gemini API Key.
- `python-multipart` and `Pillow` (these will be in `requirements.txt`).
- (Optional) A Pydantic Logfire Token for cloud-based observability.
- (Optional but Recommended) Set OpenTelemetry environment variables (`OTEL_SERVICE_NAME`, `OTEL_SERVICE_VERSION`, `OTEL_DEPLOYMENT_ENVIRONMENT`) for richer, filterable telemetry, especially when deploying to multiple environments.

## Setup and Installation

1.  **Clone the repository (if applicable) or create the project structure.**

2.  **Create a virtual environment and activate it:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a `.env` file in the `gemini_fastapi_RAG_Pydantic` root directory. You can copy the example below.
    **Important**: Replace placeholder values with your actual keys and desired settings.
    The `.env.example` file in the repository root provides a template.

    **Key Environment Variables (see `app/core/config.py` for all defaults):**

    | Variable                      | Purpose                                                                 | Default (in config.py) | Example Value                 |
    | ----------------------------- | ----------------------------------------------------------------------- | ---------------------- | ----------------------------- |
    | `GEMINI_API_KEY`              | **Required.** Your Google Gemini API key.                               | N/A (must be set)      | `"YOUR_GEMINI_API_KEY_HERE"`    |
    | `LOGFIRE_TOKEN`               | Optional. Your Pydantic Logfire token for cloud observability.        | `None`                 | `"YOUR_LOGFIRE_TOKEN_HERE"`   |
    | `LOG_LEVEL`                   | Logging verbosity.                                                      | `"INFO"`               | `"DEBUG"`                     |
    | `APP_NAME`                    | Application name (e.g., for API docs title).                          | `"GeminiFastAPI"`      | `"My Gemini App"`             |
    | `OTEL_SERVICE_NAME`           | OpenTelemetry: Identifies your service.                                 | `"gemini-fastapi-dev"` | `"gemini-chat-prod"`          |
    | `OTEL_SERVICE_VERSION`        | OpenTelemetry: Version of your service.                                 | `"0.1.0"`              | `"1.0.2"`                     |
    | `OTEL_DEPLOYMENT_ENVIRONMENT` | OpenTelemetry: Deployment stage (dev, staging, prod).                 | `"development"`        | `"production"`                |

    **Example `.env` content:**
    ```env
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
    # LOGFIRE_TOKEN="YOUR_LOGFIRE_TOKEN_HERE"
    LOG_LEVEL="INFO"
    APP_NAME="GeminiFastAPI"
    OTEL_SERVICE_NAME="gemini-fastapi-dev"
    OTEL_SERVICE_VERSION="0.1.0"
    OTEL_DEPLOYMENT_ENVIRONMENT="development"
    ```

## Running the Application

Execute the following command from the `gemini_fastapi_RAG_Pydantic` root directory:

```bash
uvicorn app.main:app --reload
```

This will start the FastAPI development server, typically on `http://127.0.0.1:8000`.

## API Documentation

Once the server is running, you can access the interactive API documentation (Swagger UI) at:
`http://127.0.0.1:8000/docs`

And the alternative ReDoc documentation at:
`http://127.0.0.1:8000/redoc`

## Key Endpoints

All chat endpoints are prefixed with `/api/v1/chat`.

-   `POST /start_session`: Initializes a new chat session.
    -   **Request Body**: `StartChatRequest` (includes optional initial history, generation config, safety settings, model name).
    -   **Response**: `StartChatResponse` (includes session ID and initial history).
-   `POST /send_message`: Sends a message to an existing chat session.
    -   **Request Body**: `SendMessageRequest` (includes session ID, message content, optional config, and `stream` flag).
    -   **Response (non-streaming)**: `MessageResponse` (includes model's response and updated history).
    -   **Response (streaming)**: `StreamingResponse` with `application/x-ndjson` content type, yielding `StreamedMessagePart` objects.
-   `GET /history/{session_id}`: Retrieves the conversation history for a session.
    -   **Response**: `GetHistoryResponse`.
-   `DELETE /session/{session_id}`: Deletes a chat session from memory.
    -   **Response**: Success message or error.

All vision endpoints are prefixed with `/api/v1/vision`.

-   `POST /generate_with_image`: Generates content based on an image and optional text prompt.
    -   **Request**: `multipart/form-data` including:
        -   `image_file` (file): The image to process.
        -   `text_prompt` (form field, optional): Text to accompany the image.
        -   `model_name` (form field): The vision-capable model (e.g., "gemini-pro-vision").
        -   `generation_config_json` (form field, optional): JSON string of `GenerationConfig`.
        -   `safety_settings_json` (form field, optional): JSON string of a list of `SafetySetting`.
    -   **Response**: `PydanticGeminiResponse` (includes candidates with generated content, safety ratings, etc.).

## Logging and Observability

This application employs a unified logging strategy centered around Pydantic Logfire for comprehensive and structured observability.

-   **Pydantic Logfire**: Serves as the core of the logging system.
    -   If a `LOGFIRE_TOKEN` is provided in the `.env` file, traces and enriched logs are sent to the Pydantic Logfire cloud service. Without a token, Logfire typically outputs structured logs to the console, making it useful for local development.
    -   Automatic instrumentation for FastAPI, Pydantic model validation, and HTTPX (used by the `google-generativeai` SDK) is enabled, providing rich telemetry with minimal manual setup.
    -   Custom tracing with `logfire.span()`, `logfire.info()`, etc., is used in the service and API layers for application-specific insights.

### Unified Logging with Logfire

To provide a consistent and centralized logging experience, the application is configured to route standard Python log messages (from `logging.getLogger()`) through Pydantic Logfire. This is achieved by:

1.  Initializing `logfire.configure()` early in the application lifecycle (this picks up settings like the `LOGFIRE_TOKEN`).
2.  Setting up standard Python `logging.basicConfig()` to use `logfire.LogfireLoggingHandler()` as its primary (and typically sole) handler. The overall log filtering level is controlled by the `LOG_LEVEL` environment variable (defaulting to "INFO" as per `app/core/config.py`).

**Benefits:**

-   **Single, Structured Output**: All logs, whether from your custom `logger.info("...")` calls or from Logfire's automatic instrumentation, are processed and formatted by Logfire. This ensures consistency, especially for console output.
-   **Enriched Telemetry with OpenTelemetry**: Logfire leverages OpenTelemetry. By setting standard OpenTelemetry environment variables (`OTEL_SERVICE_NAME`, `OTEL_SERVICE_VERSION`, `OTEL_DEPLOYMENT_ENVIRONMENT`), your logs and traces are automatically tagged. This is crucial for filtering, searching, and analyzing telemetry from different services, versions, or deployment environments (e.g., dev, staging, production) in the Logfire UI or any OpenTelemetry-compatible backend.
-   **Centralized Collection**: When a `LOGFIRE_TOKEN` is active, all processed logs and traces are sent to the Logfire cloud, providing a single pane of glass for observability.
-   **Simplified Configuration**: Reduces the need to manage multiple Python logging formatters or console handlers, as Logfire handles the presentation.

This approach ensures that even logs from third-party libraries that use standard Python `logging` are captured and processed cohesively alongside Logfire's detailed traces and spans, all conforming to the `LOG_LEVEL` you set.

## Deployment Considerations (e.g., on Render)

When deploying this application to a platform like Render ([Render FastAPI Docs](https://render.com/docs/deploy-fastapi)):

1.  **Environment Variables in Render**:
    *   Securely set `GEMINI_API_KEY` in Render's environment variable settings for your service.
    *   Set `LOGFIRE_TOKEN` if you intend to send production logs to the Logfire cloud.
    *   Adjust `LOG_LEVEL` appropriately for your production environment (e.g., `"INFO"` or `"WARNING"`).
    *   **Critically, configure OpenTelemetry variables for your production environment** to distinguish its telemetry:
        *   `OTEL_SERVICE_NAME`: e.g., `gemini-fastapi-prod` (or your chosen production service name)
        *   `OTEL_DEPLOYMENT_ENVIRONMENT`: e.g., `production`
        *   `OTEL_SERVICE_VERSION`: Update this to match the version of the application you are deploying (e.g., `1.0.0`).
    *   `APP_NAME` can also be set here if you wish to override the default configured in `app/core/config.py`.

2.  **Build and Start Commands for Render**:
    *   **Build Command**: Render will typically need a command to install dependencies. This is usually:
        ```bash
        pip install -r requirements.txt
        ```
    *   **Start Command**: For a FastAPI application using Uvicorn, the start command needs to bind to `0.0.0.0` and use the port Render provides via the `$PORT` environment variable. A common start command is:
        ```bash
        uvicorn app.main:app --host 0.0.0.0 --port $PORT
        ```
    *   Always refer to the latest Render documentation for deploying Python and FastAPI applications, as best practices can evolve.

3.  **Using `render.yaml` (Optional)**:
    *   For more complex applications or to manage your infrastructure as code, Render supports a `render.yaml` file. This file allows you to define your web service, background workers, databases, environment variables, build commands, and start commands in a declarative way within your repository.

## Further Development

-   **Persistent Session Storage**: Implement persistent storage for chat sessions using Supabase (PostgreSQL) within a dedicated `gemini_fastapi` schema. This replaces the current in-memory session storage.
-   **Advanced Error Handling**: Implement more granular error handling and custom exception classes.
-   **Authentication & Authorization**: Add security measures to protect the API endpoints (Supabase Auth can be leveraged here).
-   **Testing**: Add comprehensive unit and integration tests.
-   **CI/CD**: Set up a continuous integration and deployment pipeline.

## Supabase Setup (for Persistent Sessions)

To use Supabase for persistent session storage:

1.  **Create a Supabase Project**: If you haven't already, create a project at [supabase.com](https://supabase.com).
2.  **Create Schema**: In the Supabase SQL Editor, create the `gemini_fastapi` schema:
    ```sql
    CREATE SCHEMA IF NOT EXISTS gemini_fastapi;
    ```
3.  **Create Table**: Create the `chat_sessions` table within this schema using the DDL provided (see step 4 in the development plan).
4.  **Environment Variables**: Add your Supabase URL and Anon Key (or Service Role Key, see below) to your `.env` file:
    *   `SUPABASE_URL`: Found in your Supabase project's API settings.
    *   `SUPABASE_KEY`: This can be the `anon` public key if your Row Level Security (RLS) policies allow client-side access. For backend-only access, it's more secure to use the `service_role` key. **Ensure RLS is enabled and configured appropriately for the `chat_sessions` table if using the anon key from the backend.** Using the service role key from the backend bypasses RLS but should be kept highly confidential.
    *   `SUPABASE_DB_SCHEMA`: Set to `gemini_fastapi`.