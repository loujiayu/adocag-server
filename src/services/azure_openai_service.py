from openai import AzureOpenAI, AsyncAzureOpenAI
import os
import logging
import json

class AzureOpenAIService:
    def __init__(self, azure_endpoint=None, api_key=None, deployment_name=None):
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
        self.max_tokens = 4000
        self.deployment_name = deployment_name or os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]

    def generate_response(self, prompt, response_format=None):
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000,
                response_format=response_format
            )
            return {
                "status": "success",
                "prompt": prompt,
                "response": response.choices[0].message.content
            }
        except Exception as e:
            logging.error(f"Error generating response: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def generate_response_async(self, prompt, response_format=None):
        try:
            response = await self.async_client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000,
                response_format=response_format
            )
            return {
                "status": "success",
                "prompt": prompt,
                "response": response.choices[0].message.content
            }
        except Exception as e:
            logging.error(f"Error generating async response: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
        
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