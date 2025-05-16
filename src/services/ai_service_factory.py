import os
from typing import Dict, List, Any, Generator, Optional, Union
from src.services.azure_openai_service import AzureOpenAIService
from src.services.gemini_service import GeminiService
import logging


class AIServiceFactory:
    """
    Factory class to create AI service instances based on the provider type
    """

    @staticmethod
    def create_service(request_args) -> Union[AzureOpenAIService, GeminiService]:
        """
        Create and return an AI service based on the specified provider in request_args
        
        Args:
            request_args: Flask request.args containing parameters like 'api_provider',
                         'azure_endpoint', 'api_key', 'deployment_name', etc.
            **kwargs: Additional arguments to pass to the service constructor
            
        Returns:
            An instance of the specified AI service
        """
        # Function to get a value from request_args first, then kwargs, then env vars with fallback
        def get_param(param_name, env_name=None):
            if request_args and param_name in request_args:
                return request_args.get(param_name)
            elif env_name:
                return os.environ.get(env_name)
        
        # Extract api_provider from request args, kwargs, or use default
        api_provider = get_param('api_provider', 'BuiltIn')
        
        if 'Azure OpenAI' == api_provider:
            # Extract Azure OpenAI specific parameters
            azure_endpoint = get_param(
                "azure_endpoint", 
                "AZURE_OPENAI_ENDPOINT", 
            )
            api_key = get_param(
                "azure_api_key", 
                "AZURE_OPENAI_KEY", 
            )
            deployment_name = get_param(
                "azure_model", 
                "AZURE_OPENAI_DEPLOYMENT_NAME", 
            )
              # Get temperature parameter
            temperature = float(get_param("temperature", None) or 0.7)
            
            # Create and return an Azure OpenAI service instance
            return AzureOpenAIService(
                azure_endpoint=azure_endpoint,
                api_key=api_key,
                deployment_name=deployment_name,
                temperature=temperature
            )
        elif "Google Vertex AI" == api_provider:
            # Extract Gemini specific parameters (currently none, but could be added later)
            gcp_model = get_param("gcp_model")
            project_name = get_param("gcp_project_name")
            gcp_region = get_param("gcp_region")
            
            # Create and return a Gemini service instance
            return GeminiService(project_name, gcp_model, gcp_region)
        else:
            # Default to Azure OpenAI with the same parameter extraction
            logging.warning(f"Unknown API provider '{api_provider}', defaulting to Azure OpenAI")
            azure_endpoint = get_param(
                "azure_endpoint", 
                "AZURE_OPENAI_ENDPOINT", 
            )
            api_key = get_param(
                "api_key", 
                "AZURE_OPENAI_KEY", 
            )
            deployment_name = get_param(
                "deployment_name", 
                "AZURE_OPENAI_DEPLOYMENT_NAME", 
            )
              # Get temperature parameter
            temperature = float(get_param("temperature", None) or 0.7)
            
            return AzureOpenAIService(
                azure_endpoint=azure_endpoint,
                api_key=api_key,
                deployment_name=deployment_name,
                temperature=temperature
            )