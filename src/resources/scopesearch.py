from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse
import logging
from typing import Optional, Dict, Any, Union, List
from src.services.azure_devops_search import AzureDevOpsSearch
from src.services.search_utilities import SearchUtilities
from src.services.ai_service_factory import AIServiceFactory
import json

class ScopeSearchResource:
    def __init__(self, azure_devops_client: Optional[AzureDevOpsSearch] = None, azure_devops_cosmos_client: Optional[AzureDevOpsSearch] = None,
                 ai_agent=None, rating_threshold=7, cache_enabled=True, **kwargs):
        """
        Initialize the ScopeSearchResource
        
        Args:
            azure_devops_client: An instance of AzureDevOpsSearch
            ai_agent: Optional AI agent for rating search results
            rating_threshold: Minimum rating threshold for including files
            cache_enabled: Whether to enable caching of search results
            **kwargs: Additional arguments
        """
        self.search_client: AzureDevOpsSearch = azure_devops_client
        # Initialize AI service
        self.ai_service = AIServiceFactory.create_service({})
        self.azure_devops_cosmos_client = azure_devops_cosmos_client
        self.search_utilities = SearchUtilities(
            search_client=azure_devops_client,
            ai_agent=ai_agent,
            rating_threshold=rating_threshold,
            cache_enabled=cache_enabled
        )

    def format_sse_response(self, data, is_done=False):
        """Format data as Server-Sent Events (SSE) with the specified format"""
        event_data = {
            "event": data.get('event', 'message'),
            "data": {
                "content": data.get('content', ""),
                "message": data.get('message', ""),
                "done": is_done
            }
        }
        return json.dumps(event_data) + "\n\n"

    async def post(
        self, 
        request: Request, 
        search_text: str, 
        repository: Optional[Union[str, List[str]]] = None, 
        branch: str = "master", 
        max_results: int = 1000,
    ):
        """
        Handle POST request for scope script search with streaming chat response
        
        Args:
            request: FastAPI Request object
            search_text: Text to search for
            repository: Optional repository name or list of repository names to search in
            branch: Branch to search in (default: master)
            max_results: Maximum number of results to return (default: 1000)
            
        Returns:
            StreamingResponse containing AI service's analysis of the search results
        """
        try:
            # Call Azure DevOps search directly for scope script search
            search_results = self.search_client.search_code(
                search_text=search_text,
                repository=repository,
                branch=branch,
                max_results=max_results,
                without_prefix=True
            )
            
            if search_results.get("status") == "success":
                file_content = await self.search_utilities.get_file_content_from_results(
                    search_results, max_length=3000000, with_rating=False
                )
            
                # Format the context from search results
                search_results = {
                  "code_results": file_content,
                  "wiki_results": None
                }
                context = self.search_utilities.format_content_context(search_results)                # Read scope knowledge from file
                with open('src/scope_knowledge', 'r', encoding='utf-8') as f:
                    scope_knowledge = f.read()

                system_content = f"Scope knowledge: {scope_knowledge}"

                async def event_generator():
                    yield json.dumps({
                        "event": "systemprompt",
                        "data": {
                            "message": "Generating response...",
                            "content": f'##Scope knowledge## \n{scope_knowledge}',
                            "done": False
                        }
                    }) + "\n\n"

                    
                    yield json.dumps({
                        "event": "prompt",
                        "data": {
                            "message": "Generating response...",
                            "content": f'##Code Sample##\n{context}',
                            "done": False
                        }
                    }) + "\n\n"
                    # First yield the processing message
                    yield self.format_sse_response({
                        "event": "processing",
                        "message": "Analyzing search results...",
                    })

                    # Prepare messages for AI chat
                    messages = [
                        {
                            "role": "system",
                            "content": system_content
                        },
                        {
                            "role": "user",
                            "content": f"It's code samples, please summarize the concept of the scope language for '{search_text}':\n\n{context}"
                        }
                    ]

                    # Stream the chat response
                    async for sse_chunk in self.ai_service.stream_chat_async(messages=messages):
                        yield sse_chunk

                return StreamingResponse(
                    event_generator(),
                    media_type='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Content-Type': 'text/event-stream',
                        'Connection': 'keep-alive',
                        'X-Accel-Buffering': 'no'
                    }
                )
                
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Search failed: {search_results.get('message', 'Unknown error')}"
                )
        except Exception as e:
            logging.error(f"Error in scope script search: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
