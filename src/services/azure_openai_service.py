from openai import AzureOpenAI, AsyncAzureOpenAI
import os
import logging
import json
from aiolimiter import AsyncLimiter

class AzureOpenAIService:
    def __init__(self, azure_endpoint=None, api_key=None, deployment_name=None, 
                 rate_limit=800, time_period=60):
        """
        Initialize Azure OpenAI Service with rate limiting
        
        Args:
            azure_endpoint: Azure OpenAI endpoint URL
            api_key: Azure OpenAI API key
            deployment_name: Azure OpenAI deployment model name
            rate_limit: Maximum number of requests in the time period (default: 20)
            time_period: Time period in seconds for the rate limit (default: 60)
        """
        self.client = AzureOpenAI(
            azure_endpoint=azure_endpoint or os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=api_key or os.environ["AZURE_OPENAI_KEY"],
            api_version="2025-01-01-preview",
        )
        self.async_client = AsyncAzureOpenAI(
            azure_endpoint=azure_endpoint or os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=api_key or os.environ["AZURE_OPENAI_KEY"],
            api_version="2025-01-01-preview",
        )
        self.max_tokens = 32000
        self.deployment_name = deployment_name or os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
        
        # Initialize rate limiter (default: 20 requests per minute)
        self.rate_limiter = AsyncLimiter(rate_limit, time_period)
        logging.info(f"Azure OpenAI Service initialized with rate limit: {rate_limit} requests per {time_period}s")

    def chat(self, messages, response_format=None):
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.7,
                max_tokens=self.max_tokens,
                response_format=response_format
            )
            return {
                "status": "success",
                "response": response.choices[0].message.content
            }
        except Exception as e:
            logging.error(f"Error in chat: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def chat_async(self, messages, response_format=None):
        try:
            # Apply rate limiting
            async with self.rate_limiter:
                response = await self.async_client.chat.completions.create(
                    model=self.deployment_name,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=self.max_tokens,
                    response_format=response_format
                )
            return {
                "status": "success",
                "response": response.choices[0].message.content
            }
        except Exception as e:
            logging.error(f"Error in async chat: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    def stream_chat(self, messages):
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                temperature=0.7,
                max_tokens=self.max_tokens,
                stream=True,
            )
        
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None:
                    yield json.dumps({
                        "event": "message",
                        "data": {
                            "content": chunk.choices[0].delta.content,
                            "done": False
                        }
                    }) + "\n\n"
                    
            # Send final message indicating completion
            yield json.dumps({
                "event": "message",
                "data": {
                    "content": "",
                    "done": True
                }
            }) + "\n\n"
        except Exception as e:
            logging.error(f"Error in streaming chat: {str(e)}")
            yield json.dumps({
                "event": "error",
                "data": {
                    "content": str(e),
                    "done": True
                }
            }) + "\n\n"

    async def stream_chat_async(self, messages):
        try:
            # Apply rate limiting before starting the stream
            async with self.rate_limiter:
                response = await self.async_client.chat.completions.create(
                    model=self.deployment_name,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=self.max_tokens,
                    stream=True,
                )
            
                async for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None:
                        yield json.dumps({
                            "event": "message",
                            "data": {
                                "content": chunk.choices[0].delta.content,
                                "done": False
                            }
                        }) + "\n\n"
                    
                # Send final message indicating completion
                yield json.dumps({
                    "event": "message",
                    "data": {
                        "content": "",
                        "done": True
                    }
                }) + "\n\n"
        except Exception as e:
            logging.error(f"Error in async streaming chat: {str(e)}")
            yield json.dumps({
                "event": "error",
                "data": {
                    "content": str(e),
                    "done": True
                }
            }) + "\n\n"