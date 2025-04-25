from flask.views import MethodView
from flask import request, Response
from src.services.ai_service_factory import AIServiceFactory
from src.services.agents import AIAgent
import json
from src.services.search_utilities import SearchUtilities
from src.utils import event_stream_to_response

class DocumentSearchResource(MethodView):
    def __init__(self, azure_devops_client = None, method_type = None, **kwargs):
        self.method_type = method_type
        self.search_client = azure_devops_client
        self.default_api_provider = kwargs.get('api_provider', 'Azure OpenAI')
        
        # Get the AI service
        self.ai_service = self._get_ai_service()
        
        # Pass the AI service to AIAgent
        self.ai_agent = AIAgent(ai_service=self.ai_service)
        
        # Initialize search utilities
        self.search_utilities = SearchUtilities(
            search_client=azure_devops_client,
            ai_agent=self.ai_agent,
            rating_threshold=7  # Minimum rating to consider a file relevant
        )
        
    def _get_ai_service(self):
        """Get the appropriate AI service based on request parameters"""
        return AIServiceFactory.create_service(request.args)

    async def post(self):
        query = request.args.get('query')
        if not query:
            return {"error": "Query parameter is required"}, 400
            
        # Parse repositories from request
        repositories = request.args.get('repositories', "")
        repo_list = [r.strip() for r in repositories.split(",")] if repositories else []
        
        # Use our search utilities to get combined results
        search_results = await self.search_utilities.combine_search_results_with_wiki(
            query=query,
            repositories=repo_list,
            include_wiki=True
        )
        
        # If we have content results, generate a response using AI service
        if search_results["status"] == "success":
            # Format the context from search results
            context = self.search_utilities.format_content_context(search_results)
            
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
                
                async for sse_chunk in self.ai_service.stream_chat_async(messages):
                    yield sse_chunk
            
            response_data = await event_stream_to_response(event_generator())

            return Response(
                response_data,
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Content-Type': 'text/event-stream',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no'
                }
            )
        else:
            return {"error": f"Unable to find relevant content for: {query}"}, 400
