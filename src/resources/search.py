from fastapi import Request
from fastapi.responses import StreamingResponse
from src.services.ai_service_factory import AIServiceFactory
from src.services.agents import AIAgent
import json
from src.services.search_utilities import SearchUtilities

class DocumentSearchResource:
    def __init__(self, azure_devops_client=None, **kwargs):
        self.search_client = azure_devops_client
        self.default_api_provider = kwargs.get('api_provider', 'Azure OpenAI')
        
    def _get_ai_service(self, request_args):
        """Get the appropriate AI service based on request parameters"""
        return AIServiceFactory.create_service(request_args)

    async def post(self, request: Request):
        """Handle POST request for document search optimized for FastAPI"""
        # Get request parameters
        args = request.args if hasattr(request, 'args') else request.query_params
        query = args.get('query')
        repositories = args.get('repositories', "")
        
        # Validate query parameter
        if not query:
            return {"error": "Query parameter is required"}, 400
            
        # Parse repositories from request
        repo_list = [r.strip() for r in repositories.split(",")] if repositories else []
        
        # Get the AI service
        ai_service = self._get_ai_service(args)
        
        # Pass the AI service to AIAgent
        ai_agent = AIAgent(ai_service=ai_service)
        
        # Initialize search utilities
        search_utilities = SearchUtilities(
            search_client=self.search_client,
            ai_agent=ai_agent,
            rating_threshold=7  # Minimum rating to consider a file relevant
        )
        
        # Use our search utilities to get combined results
        search_results = await search_utilities.combine_search_results_with_wiki(
            query=query,
            repositories=repo_list,
            include_wiki=True
        )
        
        # If we have content results, generate a response using AI service
        if search_results["status"] == "success":
            # Format the context from search results
            context = search_utilities.format_content_context(search_results)
            # Generate an initial prompt for the AI service
            init_prompt = f"This document provides a brief overview of the key points. It avoids excessive detail and focuses on clarity and conciseness about {query}, without exceeding the 1000-token limit. It serves as a quick reference or starting point for deeper exploration if needed."
            # Create the full prompt
            prompt = f"{init_prompt}\n{context}"
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            # Create a generator function for SSE
            async def event_generator():
                # First yield the prompt event
                yield json.dumps({
                    "event": "prompt",
                    "data": {
                        "message": "Generating response...",
                        "content": prompt,
                        "done": False
                    }
                }) + "\n\n"
                
                async for sse_chunk in ai_service.stream_chat_async(messages):
                    yield sse_chunk

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    'Cache-Control': 'no-cache',
                    'Content-Type': 'text/event-stream',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no'
                }
            )
        else:
            # Return error response in a FastAPI-compatible way
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400, 
                detail=f"Unable to find relevant content for: {query}"
            )
