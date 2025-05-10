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
        
        # Configure Logfire with minimal options
        # Don't use advanced scrubbing options that might not be supported in the current version
        logfire.configure(**logfire_options) # type: ignore
        logger = logging.getLogger(__name__)
        
        # Standard Python logging - now routed through Logfire
        # Note: The format string is removed as LogfireLoggingHandler will control formatting.
        # force=True ensures this configuration takes precedence.
        logging.basicConfig(
            level=settings.LOG_LEVEL.upper(),
            handlers=[
                LogfireLoggingHandler(), # Use Logfire's handler (simplified)
                logging.StreamHandler(sys.stdout)  # Add a standard handler to see all logs in console
            ],
            force=True # Ensure this config applies
        )
        logger.info("Standard logging and Pydantic Logfire core configured. Standard logs are now routed via Logfire.")

        # Instrument Pydantic
        try:
            logfire.instrument_pydantic()
            logger.info("Logfire Pydantic instrumentation enabled.")
        except Exception as e:
            logger.warning(f"Failed to instrument Pydantic: {e}")
        
        # Instrument HTTPX
        try:
            logfire.instrument_httpx()
            logger.info("Logfire HTTPX instrumentation enabled.")
        except Exception as e:
            logger.warning(f"Failed to instrument HTTPX: {e}")

        if settings.LOGFIRE_TOKEN:
            logger.info(f"Logfire token provided, sending data to Logfire cloud.")
        else:
            logger.warning("Logfire token not provided. Logfire will run in local/console mode.")

    except Exception as e:
        # Fallback to basic console logging if Logfire setup fails catastrophically
        fallback_logger = logging.getLogger(__name__ + ".fallback")
        # Ensure fallback basicConfig doesn't also try to use LogfireLoggingHandler if Logfire itself failed
        logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)], force=True)
        fallback_logger.error(f"CRITICAL: Failed to configure Pydantic Logfire or its instrumentations. Falling back to basic stdout logging. Details: {e}", exc_info=True)
        # Try minimal successful Logfire configuration
        try:
            logfire.configure(ignore_errors=True)
            fallback_logger.info("Successfully configured Logfire with minimal settings")
        except:
            fallback_logger.error("Could not configure Logfire even with minimal settings")

# Call setup_logging on import if you want it to be configured automatically
# when this module is imported. Or call it explicitly in main.py
# setup_logging() 