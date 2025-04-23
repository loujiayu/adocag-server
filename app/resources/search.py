from flask_restful import Resource
from flask import jsonify, request
from app.services.ai_service_factory import AIServiceFactory
from app.services.agents import AIAgent
from app.services.search_utilities import SearchUtilities

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
        
    def get(self):
        query = request.args.get('query')
        if not query:
            return {"error": "Query parameter is required"}, 400
            
        # Parse repositories from request
        repositories = request.args.get('repositories', "")
        repo_list = [r.strip() for r in repositories.split(",")] if repositories else []
        
        # Use our search utilities to get combined results
        search_results = self.search_utilities.combine_search_results_with_wiki(
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
            
            # Generate and return the AI response using the service from request parameters
            return self.ai_service.generate_response(prompt)
        else:
            return {"error": f"Unable to find relevant content for: {query}"}, 400
