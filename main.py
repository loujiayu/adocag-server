import os
import uuid
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from dotenv import load_dotenv
from src.services.azure_devops_search import AzureDevOpsSearch
from src.services.ai_service_factory import AIServiceFactory
from src.services.agents import AIAgent
from src.services.search_utilities import SearchUtilities, SearchSource
from src.services.cache_manager import CacheManager
from src.resources.search import DocumentSearchResource
from src.resources.chat import ChatResource
from src.resources.scopesearch import ScopeSearchResource
from src.configs.repository_configs import REPOSITORY_CONFIGS
from src.middleware import ReferrerCheckMiddleware, is_request_from_ui, ALLOWED_UI_ORIGINS
import logging
import platform
import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Azure DevOps Search API",
    description="API for searching Azure DevOps repositories and generating AI responses",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Add referer check middleware
app.add_middleware(ReferrerCheckMiddleware)

# OAuth2 bearer token scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Initialize Azure DevOps client
azure_devops_client = AzureDevOpsSearch()

# azure_devops_cosmos_client = AzureDevOpsSearch(
#     organization="mscosmos",
#     project="CosmosWiki",
# )

# Initialize DocumentSearchResource
document_search_resource = DocumentSearchResource(azure_devops_client=azure_devops_client)

# Initialize ChatResource
chat_resource = ChatResource(azure_devops_client=azure_devops_client)

# Initialize ScopeSearchResource
scope_search_resource = ScopeSearchResource(azure_devops_client=azure_devops_client, azure_devops_cosmos_client=None)

# Initialize CacheManager for shared code functionality
cache_manager = CacheManager()

# Define request models
class MessageItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[MessageItem]
    stream_response: Optional[bool] = True

class NoteCreateRequest(BaseModel):
    content: str

class NoteUpdateRequest(BaseModel):
    content: Optional[str] = None
    title: Optional[str] = None

class SearchRequest(BaseModel):
    sources: List[SearchSource]
    stream_response: Optional[bool] = True
    custom_prompt: Optional[str] = None
2
class ScopeScriptSearchRequest(BaseModel):
    query: str = "(ext:script)"
    repository: Optional[str] = "AdsAppsMT"
    branch: Optional[str] = "master"
    max_results: Optional[int] = 1000
    stream_response: Optional[bool] = True
    custom_prompt: Optional[str] = None

class ShareCodeRequest(BaseModel):
    chatSession: Optional[str] = None

class ShareCodeResponse(BaseModel):
    status: str
    key: str
    message: Optional[str] = None

class GetSharedCodeResponse(BaseModel):
    status: str
    chatSession: Optional[str] = None
    message: Optional[str] = None

# Helper to get AI service from request
async def get_ai_service(request: Request):
    query_params = dict(request.query_params)
    return AIServiceFactory.create_service(query_params)

# Health check endpoint
@app.get("/api/health", tags=["Health"])
async def health_check():
    return {
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat(),
        'service': 'server-api',
        'environment': {
            'python_version': platform.python_version(),
            'system': platform.system(),
            'node': platform.node()
        }
    }

# Home endpoint - Inaccessible
@app.get("/", tags=["Home"])
async def home():
    raise HTTPException(status_code=403, detail="Access forbidden")

# Search endpoint - using DocumentSearchResource from search.py
@app.post("/api/search", tags=["Search"])
async def search_chat(
    search_request: SearchRequest,
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme)
):
    # Call accept_token only if token exists and request is not from UI
    if token and search_request.sources and not is_request_from_ui(request):
        logging.info(f"Applying token to repositories: {search_request.sources}")
        for source in search_request.sources:
            if hasattr(source, 'repositories'):
                for repository in source.repositories:
                    azure_devops_client.accept_token(repository, token)
    
    # Call the post method from DocumentSearchResource
    setattr(request, "json", lambda: search_request.dict())
    return await document_search_resource.post(request)

# Chat endpoint - using ChatResource from chat.py
@app.post("/api/chat", tags=["Chat"])
async def chat(
    chat_request: ChatRequest,
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    repositories: str = Query("", description="Comma-separated list of repositories"),
    is_deep_research: bool = Query(False, description="Whether to perform deep research"),
    temperature: Optional[float] = Query(0.7, ge=0.0, le=2.0, description="Model temperature, controls randomness. Higher values produce more creative responses."),
):
    # Apply token if repositories are specified and request is not from UI
    if token and repositories and not is_request_from_ui(request):
        # Split comma-separated repository names and apply token to each
        repos = [repo.strip() for repo in repositories.split(",") if repo.strip()]
        for repo in repos:
            azure_devops_client.accept_token(repo, token)
            
    # Add query parameters to request object for ChatResource compatibility
    setattr(request, "args", {
        "repositories": repositories,
        "is_deep_research": str(is_deep_research).lower(),
        "temperature": str(temperature)
    })
    
    # Convert Pydantic model to dict and attach to request
    messages = [{"role": msg.role, "content": msg.content} for msg in chat_request.messages]
    
    # Mock JSON parsing method for compatibility
    async def get_json():
        return {"messages": messages}
    
    # Add get_json method to request
    setattr(request, "get_json", get_json)
      # Call the post method from ChatResource which now returns FastAPI StreamingResponse directly
    return await chat_resource.post(request)

# Scope Script Search endpoint
@app.post("/api/search/scope", tags=["Search"])
async def search_scope_script(
    request: Request,
    search_request: ScopeScriptSearchRequest,
    token: Optional[str] = Depends(oauth2_scheme),
):
    # Call accept_token if token exists and request is not from UI
    if token and search_request.repository and not is_request_from_ui(request):
        azure_devops_client.accept_token(search_request.repository, token)
    
    # Call the post method from ScopeSearchResource
    return await scope_search_resource.post(
        request=request,
        search_text=search_request.query,
        repository=search_request.repository,
        branch=search_request.branch,
        max_results=search_request.max_results,
        stream_response=search_request.stream_response,        custom_prompt=search_request.custom_prompt
    )

# Share endpoints
@app.post("/api/share", tags=["Share"], response_model=ShareCodeResponse, status_code=201)
async def create_shared_code(share_request: ShareCodeRequest):
    """Create a shared code snippet and return a key to access it"""
    try:
        # Generate a unique key for the shared code
        share_key = str(uuid.uuid4())
        
        # Prepare the data to store
        share_data = share_request.chatSession
        
        # Store in cache with 30 days TTL (2,592,000 seconds)
        cache = cache_manager.get_cache()
        success = await cache.set(f"share:{share_key}", share_data, ttl=259200)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store shared code")
        
        return ShareCodeResponse(
            status="success", 
            key=share_key,
            message="Code shared successfully"
        )
        
    except Exception as e:
        logging.error(f"Error creating shared code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating shared code: {str(e)}")

@app.get("/api/share", tags=["Share"], response_model=GetSharedCodeResponse)
async def get_shared_code(key: str = Query(..., description="Shared code key")):
    """Retrieve a shared code snippet by its key"""
    try:
        # Retrieve from cache
        cache = cache_manager.get_cache()
        share_data = await cache.get(f"share:{key}")
        
        if share_data is None:
            return GetSharedCodeResponse(
                status="error",
                message="Shared code not found or expired"
            )
        
        return GetSharedCodeResponse(
            status="success",
            chatSession=share_data
        )
        
    except Exception as e:
        logging.error(f"Error retrieving shared code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving shared code: {str(e)}")

# Note endpoints
@app.get("/api/note", tags=["Notes"])
async def get_notes(ai_service = Depends(get_ai_service)):
    # For now, return empty list (would need DB integration for real implementation)
    return {"status": "success", "notes": []}

@app.get("/api/note/{note_id}", tags=["Notes"])
async def get_note(note_id: str, ai_service = Depends(get_ai_service)):
    # Check if note exists (would need DB integration)
    # For now, return not found
    raise HTTPException(status_code=404, detail="Note not found")

@app.post("/api/note", tags=["Notes"], status_code=201)
async def create_note(note: NoteCreateRequest, ai_service = Depends(get_ai_service)):
    ai_agent = AIAgent(ai_service=ai_service)
    
    try:
        # Generate note name
        response = ai_agent.note_name(note.content)
        if response.get("status") == "error":
            raise HTTPException(status_code=500, detail=response.get("error"))
        
        note_name = response.get("response", "Untitled Note")
        
        # Save wiki page
        save_res = azure_devops_client.save_wiki_page(note_name, note.content)
        
        if save_res.get("status") == "error":
            raise HTTPException(status_code=500, detail=save_res.get("message"))
        
        return {"status": "success", "id": save_res['page'].page.id, "title": note_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/note/{note_id}", tags=["Notes"])
async def update_note(note_id: str, note: NoteUpdateRequest, ai_service = Depends(get_ai_service)):
    # Would need DB integration
    raise HTTPException(status_code=404, detail="Note not found")

@app.delete("/api/note/{note_id}", tags=["Notes"])
async def delete_note(note_id: str, ai_service = Depends(get_ai_service)):
    try:
        res = azure_devops_client.delete_wiki_page(note_id)
        
        if res.get("status") == "error":
            raise HTTPException(status_code=500, detail=res.get("message"))
            
        return {"status": "success", "message": "Note deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add repository info endpoint
@app.get("/api/repositories", tags=["Repositories"])
async def get_repositories():
    """Return list of supported repositories and their configurations"""
    repositories = []
    for repo_name, config in REPOSITORY_CONFIGS.items():
        repositories.append({
            "name": config.name,
            "organization": config.organization,
            "project": config.project,
            "searchPrefix": config.search_prefix,
            "excludedPaths": config.excluded_paths,
            "branch": config.branch,
            "includedPaths": config.included_paths
        })
    return repositories

# API docs endpoint
@app.get("/api/docs", tags=["Documentation"])
async def get_docs(format: str = Query("html", description="Format to return docs in: 'html' or 'md'")):
    """Return API documentation in HTML or Markdown format"""
    try:
        with open('API_DOCUMENTATION.md', 'r', encoding='utf-8') as f:
            content = f.read()
            
        if format.lower() == 'md':
            return Response(
                content=content,
                media_type='text/markdown'
            )
        else:
            import markdown2
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>API Documentation</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    pre {{
                        background-color: #f5f5f5;
                        padding: 15px;
                        border-radius: 5px;
                        overflow-x: auto;
                    }}
                    code {{
                        font-family: 'Consolas', 'Monaco', monospace;
                        background-color: #f5f5f5;
                        padding: 2px 4px;
                        border-radius: 3px;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin: 20px 0;
                    }}
                    th, td {{
                        border: 1px solid #ddd;
                        padding: 12px;
                        text-align: left;
                    }}
                    th {{
                        background-color: #f8f9fa;
                    }}
                    h1, h2, h3 {{
                        color: #2c3e50;
                        margin-top: 1.5em;
                    }}
                </style>
            </head>
            <body>
                {markdown2.markdown(content, extras=['tables', 'code-friendly', 'fenced-code-blocks'])}
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error loading documentation: {str(e)}"
        )

# Run the server when executed directly
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)