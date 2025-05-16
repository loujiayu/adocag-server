import os
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from src.services.azure_devops_search import AzureDevOpsSearch
from src.services.ai_service_factory import AIServiceFactory
from src.services.agents import AIAgent
from src.services.search_utilities import SearchUtilities, SearchSource
from src.resources.search import DocumentSearchResource
from src.resources.chat import ChatResource
from src.resources.scopesearch import ScopeSearchResource
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

# Initialize Azure DevOps client
azure_devops_client = AzureDevOpsSearch(
    organization=os.getenv('AZURE_DEVOPS_ORG'),
    project=os.getenv('AZURE_DEVOPS_PROJECT')
)

azure_devops_cosmos_client = AzureDevOpsSearch(
    organization="mscosmos",
    project="CosmosWiki",
)

# Initialize DocumentSearchResource
document_search_resource = DocumentSearchResource(azure_devops_client=azure_devops_client)

# Initialize ChatResource
chat_resource = ChatResource(azure_devops_client=azure_devops_client)

# Initialize ScopeSearchResource
scope_search_resource = ScopeSearchResource(azure_devops_client=azure_devops_client, azure_devops_cosmos_client=azure_devops_cosmos_client)

# Define request models
class MessageItem(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[MessageItem]

class NoteCreateRequest(BaseModel):
    content: str

class NoteUpdateRequest(BaseModel):
    content: Optional[str] = None
    title: Optional[str] = None

class SearchRequest(BaseModel):
    sources: List[SearchSource]

class ScopeScriptSearchRequest(BaseModel):
    search_text: str
    repository: Optional[str] = None
    branch: Optional[str] = "master"
    max_results: Optional[int] = 1000
    without_prefix: Optional[bool] = False

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
        'azure_devops_client': {
            'organization': azure_devops_client.organization,
            'project': azure_devops_client.project,
            'resource_area_identifier': azure_devops_client.search_client.resource_area_identifier
        },
        'environment': {
            'python_version': platform.python_version(),
            'system': platform.system(),
            'node': platform.node()
        }
    }

# Home endpoint
@app.get("/", tags=["Home"])
async def home():    return {
        'message': 'Welcome to the API server',
        'endpoints': {
            '/api/health': 'Health check endpoint',
            '/api/search/filelist': 'File list endpoint',
            '/api/search/chat': 'Full content search endpoint',
            '/api/search/scope': 'Scope script search endpoint',
            '/api/chat': 'Streaming chat endpoint',
            '/api/note': 'Note management endpoint'
        },
        'status': 'online'
    }

# Search endpoint - using DocumentSearchResource from search.py
@app.post("/api/search", tags=["Search"])
async def search_chat(
    search_request: SearchRequest,
    request: Request
):
    # Call the post method from DocumentSearchResource
    setattr(request, "json", lambda: search_request.dict())
    return await document_search_resource.post(request)

# Chat endpoint - using ChatResource from chat.py
@app.post("/api/chat", tags=["Chat"])
async def chat(
    chat_request: ChatRequest,
    request: Request,
    repositories: str = Query("", description="Comma-separated list of repositories"),
    is_deep_research: bool = Query(False, description="Whether to perform deep research"),
    temperature: Optional[float] = Query(0.7, ge=0.0, le=2.0, description="Model temperature, controls randomness. Higher values produce more creative responses.")
):
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
    request: Request
):
    # Call the post method from ScopeSearchResource
    return await scope_search_resource.post(
        request=request,
        search_text="(ext:script)",
        repository="AdsAppsMT",
        branch="master",
        max_results=1000,
    )

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

# Run the server when executed directly
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)