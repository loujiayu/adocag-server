import os
from typing import Optional, Dict, Generator
from google import genai
from google.genai import types
from typing import List, Dict, Any, Generator, Optional
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

class GeminiService:
    def __init__(self, project: str, model: str, location: str):
        """Initialize Gemini service
        
        Args:
            project: The Google Cloud project ID
            model: The default Gemini model to use
            location: The Google Cloud location
        """
        self.client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )
        self.default_model = model
        self.default_config = types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.8,
            seed=0,
            max_output_tokens=4000,
            response_modalities=["TEXT"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="zephyr"
                    )
                ),
            ),
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
            ],
        )

    def stream_chat(self, messages: List[Dict[str, Any]], model_name: str = None) -> Generator:
        """
        Generate a streaming response using the Gemini model
        
        Args:
            message: The message to send to Gemini
            model_name: The Gemini model to use (defaults to self.default_model)
            
        Yields:
            Chunks of the response as Server-Sent Events
        """
        try:
            role_mapping = {
                "assistant": "model",
                "user": "user"
            }
            contents = [
                types.Content(
                    role=role_mapping[item["role"]],
                    parts=[types.Part.from_text(text=item["content"])]
                )
                for item in messages
            ]
            
            response = self.client.models.generate_content_stream(
                model=model_name or self.default_model,
                config=self.default_config,
                contents=contents
            )
            
            full_response = ""
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    yield json.dumps({
                        "event": "message",
                        "data": {
                            "content": chunk.text,
                            "done": False
                        }
                    }) + "\n\n"
            
            # Send final message
            yield json.dumps({
                "event": "message",
                "data": {
                    "content": '',
                    "done": True
                }
            }) + "\n\n"
            
        except Exception as e:
            yield json.dumps({
                "event": "error",
                "data": {
                    "message": str(e)
                }
            }) + "\n\n"

    def generate_response(self, prompt: str, model_name: str = None) -> Dict:
        """
        Generate a response using the Gemini model
        
        Args:
            prompt: The prompt to send to Gemini
            content_results: Optional results from file content to include in context
            model_name: The Gemini model to use (defaults to self.default_model)
            
        Returns:
            Dictionary containing the response and status
        """
        try:
            # Prepare the content for the prompt with context if available

            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                ),
            ]
            
            response = self.client.models.generate_content(
                model=model_name or self.default_model,
                config=self.default_config,
                contents=contents
            )
            
            return {
                "status": "success",
                "response": response.text,
                "prompt": prompt
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "prompt": prompt
            }