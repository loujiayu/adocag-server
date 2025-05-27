import os
import logging
from urllib.parse import urlparse
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Configure UI referer whitelist - add your trusted UI domains here
# Can be loaded from environment variables or configuration file
ALLOWED_UI_ORIGINS = [
    "localhost",
    "white-bush-09c68410f.6.azurestaticapps.net",
]

class ReferrerCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip check for non-API paths or development environment
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        logging.info(f"Processing request for path: {request}")
        # Use the is_request_from_ui function to check if the request is from a whitelisted UI
        if is_request_from_ui(request):
            # Valid referer, proceed with request
            return await call_next(request)
        
        # Get the referer for logging purposes
        referer = request.headers.get("referer")
        if referer:            
            logging.warning(f"Request blocked - invalid referer: {referer}")
            return Response(
                content='{"detail":"Invalid request"}',
                status_code=403,
                media_type="application/json"
            )
        
        # No referer header
        if os.environ.get("STRICT_REFERER_CHECK", "false").lower() == "true":
            logging.warning("Request blocked - missing referer header")
            return Response(
                content='{"detail":"Invalid request"}',
                status_code=403,
                media_type="application/json"
            )
        
        # If not strict mode, allow requests without referer
        return await call_next(request)

# Dependency to check referer for specific endpoints (alternative to middleware)
async def verify_ui_referer(request: Request):
    # No referer check in dev environment
    if os.environ.get("ENVIRONMENT") == "development":
        return
    
    # Check if the request has a referer header
    referer = request.headers.get("referer")
    if not referer:
        if os.environ.get("STRICT_REFERER_CHECK", "false").lower() == "true":
            raise HTTPException(status_code=403, detail="Missing referer header")
        return
    
    # Use the is_request_from_ui function to check if the request is from a whitelisted UI
    if not is_request_from_ui(request):
        raise HTTPException(status_code=403, detail="Invalid referer")

# Utility function to check if request is from a UI
def is_request_from_ui(request: Request) -> bool:
    """
    Check if the request is coming from a whitelisted UI.
    
    Args:
        request: The FastAPI request object
    
    Returns:
        bool: True if the request is from a whitelisted UI, False otherwise
    """
    referer = request.headers.get("referer")
    logging.info(f"Referer header: {referer}")
    if not referer:
        return False
        
    parsed_url = urlparse(referer)
    host = parsed_url.netloc.split(':')[0]  # Remove port if present
    
    return host in ALLOWED_UI_ORIGINS
