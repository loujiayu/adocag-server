import os
import logging
import json
import base64
import jwt
import re
from urllib.parse import urlparse
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Configure UI referer whitelist - add your trusted UI domains here
# Can be loaded from environment variables or configuration file
ALLOWED_UI_ORIGINS = [
    "white-bush-09c68410f.6.azurestaticapps.net",
]

# Configure allowed email domains for Microsoft work accounts
# This can be moved to environment variables or configuration
ALLOWED_EMAIL_DOMAINS = [
    "microsoft.com",
    "contoso.com",  # Add your organization domains here
]

class ReferrerCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip check for non-API paths
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
            
        # Skip check for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
            
        # Skip check for health endpoint and API documentation
        if request.url.path == "/api/health" or request.url.path.startswith("/api/docs"):
            logging.info(f"Bypassing checks for endpoint: {request.url.path}")
            return await call_next(request)
        
        logging.info(f"Processing request for path: {request.url.path}")
          # Parse and log token information regardless of UI check
        # This ensures we log token info for all API requests
        token_payload = parse_and_log_token(request)
          # First check if the request is from a UI (has browser signature and referer)
        if is_request_from_ui(request):
            # If it's from a UI, check if the origin is in the whitelist
            if is_origin_in_whitelist(request):
                # For UI requests with whitelisted origin, also verify Microsoft work account
                if token_payload and is_microsoft_work_account(token_payload):
                    logging.info("UI request verified with Microsoft work account token")
                    return await call_next(request)
                else:
                    logging.warning("UI request blocked - not authenticated with Microsoft work account")
                    return Response(
                        content='{"detail":"Microsoft work account authentication required"}',
                        status_code=401,
                        media_type="application/json"
                    )
            else:
                # UI request but origin not in whitelist, block
                origin = request.headers.get("origin") or request.headers.get("referer")
                logging.warning(f"Request blocked - UI request with non-whitelisted origin: {origin}")
                return Response(
                    content='{"detail":"Invalid request origin"}',
                    status_code=403,
                    media_type="application/json"
                )
        else:
            if not token_payload:
                # No token found, block the request
                logging.warning("Request blocked - no token found")
                return Response(
                    content='{"detail":"Authentication required"}',
                    status_code=401,
                    media_type="application/json"
                )
            return await call_next(request)

# Utility function to check if request is from a UI
def is_request_from_ui(request: Request) -> bool:
    """
    Check if the request is coming from a UI based on User-Agent and origin/referer headers.
    In non-production environments, all requests are considered to be from the UI.
    
    Args:
        request: The FastAPI request object
    
    Returns:
        bool: True if the request is from a UI or in non-production environment, False otherwise
    """
    # In non-production environments, automatically pass the check
    if is_non_production_environment():
        return True
    
    # Check the User-Agent header for browser signatures
    user_agent = request.headers.get("User-Agent", "")
    logging.info(f"User-Agent: {user_agent}")
    
    # Common browser identifiers
    browser_signatures = ["Mozilla", "Chrome", "Safari", "Edge", "Firefox", "Opera", "Trident"]
    
    has_browser_signature = any(signature in user_agent for signature in browser_signatures)
    
    # Check if referer/origin exists
    referer = request.headers.get("origin") or request.headers.get("referer")
    logging.info(f"Referer header: {referer}")
    
    # Request is from a UI if it has a browser signature and a referer
    if has_browser_signature and referer:
        logging.info("Request identified as coming from a UI based on User-Agent and referer")
        return True
    
    # If no browser signature or no referer, not from a UI
    logging.info("Request not identified as coming from a UI")
    return False

def is_non_production_environment() -> bool:
    """
    Check if the current environment is non-production.
    
    Returns:
        bool: True if the environment is not production, False otherwise
    """
    return False
    environment = os.environ.get("ENVIRONMENT", "development").lower()
    if environment != "production":
        logging.info(f"Non-production environment ({environment}): allowing request as UI")
        return True
    return False

def is_origin_in_whitelist(request: Request) -> bool:
    """
    Check if the origin URL from the request is in the whitelist.
    
    Args:
        request: The FastAPI request object
    
    Returns:
        bool: True if the origin is in the whitelist, False otherwise
    """
    if is_non_production_environment():
        return True
    
    origin_url = request.headers.get("origin") or request.headers.get("referer")
    if not origin_url:
        logging.warning("No origin or referer header found in request")
        return False
        
    parsed_url = urlparse(origin_url)
    host = parsed_url.netloc.split(':')[0]  # Remove port if present
    
    allowed = host in ALLOWED_UI_ORIGINS
    if allowed:
        logging.info(f"Allowed UI origin: {host}")
    else:
        logging.info(f"Blocked UI origin: {host}, not in {ALLOWED_UI_ORIGINS}")
    
    return allowed

def parse_and_log_token(request: Request) -> dict:
    """
    Parse the JWT token from the Authorization header and log the unique_name if it exists.
    
    Args:
        request: The FastAPI request object
        
    Returns:
        dict: The decoded token payload or empty dict if token is invalid/missing
    """
    # Try to get the token from the Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # No token found in headers
        return {}
    
    # Extract the token
    token = auth_header.split(" ")[1] if len(auth_header.split(" ")) > 1 else ""
    if not token:
        return {}
        
    try:
        # First try using PyJWT to decode the token
        try:
            # Note: verify=False because we're just logging, not authenticating
            payload = jwt.decode(token, options={"verify_signature": False})
            
            # Log the unique_name if it exists
            if "unique_name" in payload:
                logging.info(f"Token unique_name: {payload['unique_name']}")
            else:
                logging.info("Token unique_name not found, from api call")

            return payload
        except Exception as jwt_error:
            # If PyJWT fails, fall back to manual base64 decoding
            logging.debug(f"PyJWT decode failed: {jwt_error}")
            
            # Manually decode the token payload (second part)
            parts = token.split(".")
            if len(parts) >= 2:
                # Add padding to avoid base64 errors
                padded = parts[1] + "=" * (-len(parts[1]) % 4)
                try:
                    payload_json = base64.b64decode(padded).decode('utf-8')
                    payload = json.loads(payload_json)
                    
                    # Log the unique_name if it exists
                    if "unique_name" in payload:
                        logging.info(f"Token unique_name: {payload['unique_name']}")
                    elif "preferred_username" in payload:
                        logging.info(f"Token preferred_username: {payload['preferred_username']}")
                    elif "email" in payload:
                        logging.info(f"Token email: {payload['email']}")
                    elif "sub" in payload:
                        logging.info(f"Token subject: {payload['sub']}")
                        
                    return payload
                except Exception as base64_error:
                    logging.debug(f"Manual token decode failed: {base64_error}")
    except Exception as e:
        logging.warning(f"Error parsing token: {e}")
    
    return {}

def is_microsoft_work_account(token_payload: dict) -> bool:
    """
    Verify if the token is from a Microsoft work account.
    
    Args:
        token_payload: The decoded JWT token payload
        
    Returns:
        bool: True if the token is from a Microsoft work account, False otherwise
    """
    if not token_payload:
        logging.warning("No token payload to verify")
        return False
        
    # Check issuer - Microsoft tokens typically have an issuer starting with 'https://login.microsoftonline.com/'
    issuer = token_payload.get('iss', '')
    if 'login.microsoftonline.com' in issuer:
        logging.info(f"Token issuer verified as Microsoft: {issuer}")
        return True
        
    # Check tenant ID - Microsoft work accounts have a tenant ID claim
    if 'tid' in token_payload:
        logging.info(f"Microsoft tenant ID found in token: {token_payload['tid']}")
        return True
        
    # Check email domains
    email = token_payload.get('email', '') or token_payload.get('preferred_username', '') or token_payload.get('unique_name', '')
    if email:
        domain = email.split('@')[-1] if '@' in email else ''
        if domain and domain.lower() in [d.lower() for d in ALLOWED_EMAIL_DOMAINS]:
            logging.info(f"Email domain verified as allowed: {domain}")
            return True
        else:
            logging.warning(f"Email domain not in allowed list: {domain}")
            
    # If we reach here, we couldn't verify it's a Microsoft work account
    logging.warning("Could not verify token as Microsoft work account")
    return False
