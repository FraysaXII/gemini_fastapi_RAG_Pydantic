import logging
import sys
import logfire
from logfire import LogfireLoggingHandler
from .config import settings

def setup_logging():
    # Pydantic Logfire core configuration (done first)
    try:
        logfire_options = {}
        if settings.LOGFIRE_TOKEN:
            logfire_options["token"] = settings.LOGFIRE_TOKEN
        
        # resource_attributes are typically picked up by OpenTelemetry from env vars
        # or set via specific OpenTelemetry SDK configuration if needed.
        # Removing from logfire.configure() as it causes a TypeError.
        # Ensure OTEL_SERVICE_NAME, OTEL_SERVICE_VERSION, OTEL_DEPLOYMENT_ENVIRONMENT
        # are set as environment variables for Logfire/OpenTelemetry to pick them up.

        logfire.configure(**logfire_options) # type: ignore
        logger = logging.getLogger(__name__)
        # Standard Python logging - now routed through Logfire
        # Note: The format string is removed as LogfireLoggingHandler will control formatting.
        # force=True ensures this configuration takes precedence.
        logging.basicConfig(
            level=settings.LOG_LEVEL.upper(),
            handlers=[
                LogfireLoggingHandler() # Use Logfire's handler (simplified)
            ],
            force=True # Ensure this config applies
        )
        logger.info("Standard logging and Pydantic Logfire core configured. Standard logs are now routed via Logfire.")

        # Instrument Pydantic
        logfire.instrument_pydantic() 
        # logger.info("Logfire Pydantic instrumentation enabled.") # Logged by the root logger now

        # Instrument HTTPX
        logfire.instrument_httpx()
        # logger.info("Logfire HTTPX instrumentation enabled.") # Logged by the root logger now

        if settings.LOGFIRE_TOKEN:
            logger.info(f"Logfire token provided, sending data to Logfire cloud.")
        else:
            logger.warning("Logfire token not provided. Logfire will run in local/console mode.")

    except Exception as e:
        # Fallback to basic console logging if Logfire setup fails catastrophically
        fallback_logger = logging.getLogger(__name__ + ".fallback")
        # Ensure fallback basicConfig doesn't also try to use LogfireLoggingHandler if Logfire itself failed
        logging.basicConfig(level=logging.ERROR, handlers=[logging.StreamHandler(sys.stdout)], force=True)
        fallback_logger.error(f"CRITICAL: Failed to configure Pydantic Logfire or its instrumentations. Falling back to basic stdout logging for errors. Details: {e}", exc_info=True)

# Call setup_logging on import if you want it to be configured automatically
# when this module is imported. Or call it explicitly in main.py
# setup_logging() 