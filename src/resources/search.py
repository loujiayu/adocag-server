from flask_restful import Resource
from flask import jsonify, request, Response
import json
from src.services.ai_service_factory import AIServiceFactory
from src.services.agents import AIAgent
from src.services.search_utilities import SearchUtilities

class DocumentSearchResource(Resource):
    def __init__(self, azure_devops_client, method_type, **kwargs):
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

    def generate_file_stream(self, search_results, query, include_wiki=True):
        """
        Generator function for streaming search results
        
        Args:
            search_results: The search results from SearchUtilities
            query: The search query
            include_wiki: Whether to include wiki results

        Yields:
            SSE formatted responses for each file processed
        """
        # First yield the initial search metadata
        initial_metadata = {
            "event": "processing",
            "message": f"Searching for '{query}'...",
        }
        yield self.format_sse_response(initial_metadata)

        # Extract files from search results if the search was successful
        if search_results["status"] == "success":
            # Get file contents one by one and stream them
            accumulated_context = ""
            
            # Process wiki results if enabled
            wiki_results = None
            if include_wiki and hasattr(self.search_client, 'search_wiki'):
                wiki_results = self.search_client.search_wiki(query)
                
                if wiki_results and wiki_results.get("status") == "success" and wiki_results.get("results"):
                    # Yield wiki results info
                    yield self.format_sse_response({
                        "event": "processing",
                        "message": f"Found {len(wiki_results.get('results', []))} wiki results",
                    })
                    
                    # Add wiki results to accumulated context
                    wiki_context = "\nContext from Wiki:\n"
                    for result in wiki_results.get("results", []):
                        if hasattr(result, "content") and result.content:
                            wiki_context += f"\nWiki Page: {result.file_name}\n{result.content}\n"
                    
                    accumulated_context += wiki_context
            
            # Use the generator function to process code files one by one
            for file_result in self.search_utilities.yield_file_content_from_results(
                    search_results, 
                    query=query, 
                    max_length=3000000):
                
                # If it's the final notification, process accumulated context and generate response
                if file_result.get("is_final", False):
                    if accumulated_context:
                        # Generate an initial prompt for the AI service
                        init_prompt = f"This document provides a brief overview of the key points. It avoids excessive detail and focuses on clarity and conciseness about {query}, without exceeding the 1000-token limit. It serves as a quick reference or starting point for deeper exploration if needed."
                        
                        # Create the full prompt
                        prompt = f"{init_prompt}\n{accumulated_context}"

                        yield self.format_sse_response({
                            "event": "prompt",
                            "message": "Generating summary...",
                            "content": prompt
                        })
                        messages = [
                            {"role": "user", "content": prompt}
                        ]
                        # Generate AI response using the accumulated context
                        yield from self.ai_service.stream_chat(messages)
                else:
                    # For regular file results, yield the file content
                    if file_result["status"] == "success":
                        # Add to accumulated context for final summary
                        file_content = f"\nFile: {file_result.get('file_path', 'Unknown')}\n```\n{file_result.get('content', '')}\n```\n"
                        accumulated_context += file_content
                        
                        # Yield the file content as a stream event
                        yield self.format_sse_response({
                            "event": "processing",
                            "message": f"Processing file: {file_result.get('file_name', 'Unknown')}",
                        })
        else:
            # If the search failed, yield an error message
            yield self.format_sse_response({
                "event": "error",
                "message": f"Unable to find relevant content for: {query}"
            }, is_done=True)

    def post(self):
        query = request.args.get('query')
        if not query:
            return {"error": "Query parameter is required"}, 400
            
        # Parse repositories from request
        repositories = request.args.get('repositories', "")
        repo_list = [r.strip() for r in repositories.split(",")] if repositories else []
        
        # Check if wiki should be included
        include_wiki = request.args.get('include_wiki', 'true').lower() == 'true'
        
        # Use our search utilities to get combined results
        search_results = self.search_utilities.search_repositories(
            query=query,
            repositories=repo_list
        )
        
        # Return a streaming response
        return Response(
            self.generate_file_stream(search_results, query, include_wiki),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Content-Type': 'text/event-stream',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
