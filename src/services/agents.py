from src.services.azure_openai_service import AzureOpenAIService
from src.services.ai_service_factory import AIServiceFactory
import os
import json

class AIAgent:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service

    async def deep_research(self, messages):
        system_prompt = """
1. Answering Comes First:

Always prioritize giving a complete, logical, and concise answer to my question.

If a term is already well-understood or can be sufficiently explained in your response, do not extract it as an unresolved term.

2. Term Extraction Rules:

Only extract terms when they cannot be fully explained based on the current context or available information.

There is no full code definition for that term extract it.

Extracted terms must be meaningful and non-trivial—i.e., resolving them would improve understanding of the original question.

Do not extract general-purpose words or vague concepts.

3. Avoid Redundancy:

If a term has already been explained or clarified in previous responses, do not list it again.

4.Output Format:

After answering, include a section titled Unresolved Terms: (only if there are unresolved terms).

List each term using backticks (`), and keep them short and specific (ideally no more than 4 words per term).

4. Examples of Behavior:

If I ask “How is an Azure AD token generated?” and you can explain it thoroughly, do not extract any terms.

If I ask about Managed Identity Federation and you can’t explain it fully based on current context, list `Managed Identity Federation` under Unresolved Terms:.
"""
        messages.insert(0, {
            "role": "system",
            "content": system_prompt
        })

        schema = {
            "name": "EventInfo",
            "strict": False,
            "schema": 
            {
                "type": "object",
                "properties": {
                        "answer": {
                        "type": "string"
                    },
                    "unresolved": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                },
                "required": ["answer", "unresolved"],
            }
        }

        try:
            response = await self.ai_service.chat_async(messages, {"json_schema": schema, "type": "json_schema"})

            response = json.loads(response.get("response", "{}"))
            return response
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def quality_check(self, question, deep_research_response, top_n=3):
        system = f"""
            You are an expert research evaluator.
            You will be given an proposed answer and unresolevd questions and keywords by deep research agent, original research question by user
                1. Extract **all** keywords that needed for further search.  
                2. For each extracted keyword:
                    a. Assess its relevance to the main research topic on a 0–10 scale.
                    b. Decide whether this keyword **warrants further online search** (Yes / No).  
                    c. Provide a explaination for the relevance rating and whether further search is needed.
            """

        prompt = f"""
            Given:
            - The user's original research question: {question}.
            - The system's proposed answer: {deep_research_response['answer']}
            - The unresolved questions: {deep_research_response['unresolved']}
            """
        schema = {
            "name": "QualityCheck",
            "schema": {
                "type": "object",
                "properties": {
                    "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                            },
                            "relevance": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 10
                            },
                            "explaination": {
                                "type": "string",
                            },
                        },
                        "required": [
                            "keyword",
                            "relevance",
                            "explaination"
                        ],
                        "additionalProperties": False
                    }
                    }
                },
                "required": ["results"],
                "additionalProperties": False
            }
        }

        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt}
        ]
        quality_response = await self.ai_service.chat_async(messages, {"json_schema": schema, "type": "json_schema"})
        
        # Parse the JSON response
        parsed_response = json.loads(quality_response.get("response", "{}"))
        
        # Get the top N items with highest relevance, filtering out those below relevance 8 and those with spaces
        top_relevance_keywords = []
        if parsed_response and "results" in parsed_response:
            # First filter by minimum relevance of 8 and no spaces in keyword
            high_relevance_results = [
                item for item in parsed_response["results"] 
                if item.get("relevance", 0) >= 8 and " " not in item.get("keyword", "")
            ]
            
            # Sort by relevance in descending order
            sorted_results = sorted(high_relevance_results, key=lambda x: x.get("relevance", 0), reverse=True)
            
            # Get top N items (or all if there are fewer than N)
            top_relevance_keywords = sorted_results[:top_n] if sorted_results else []
        
        return {
            "status": "success" if quality_response.get("status") == "success" else "error",
            "response": quality_response.get("response", ""),
            "parsed_response": parsed_response,
            "top_relevance_keywords": top_relevance_keywords,
            "error": quality_response.get("error")
        }
    
    def note_name(self, note):
        system = """
            You are an expert note name generator.
            You will be given a note content and you need to generate a name for it.
            """
        prompt = f"""
            Given:
            - The note content: {note}
            """
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt}
        ]
        response = self.ai_service.chat(messages)
        
        return {
            "status": "success" if response.get("status") == "success" else "error",
            "response": response.get("response", ""),
            "error": response.get("error")
        }

    async def rate_single_file(self, file_content, query="", prompt_template=None):
        """Process a single file through the AI service
        
        Args:
            file_content (dict): The file content dictionary containing 'file_path' and 'content'
            query (str): The search query to customize the prompt template
            prompt_template (str, optional): Template for generating the prompt. Use {file_path} and {content}
                                          as placeholders. If None, will use a default code analysis template.
        
        Returns:
            dict: The AI service response for this file
        """
        if not file_content or file_content.get("status") != "success":
            return {
                "status": "error",
                "file_path": file_content.get("file_path", "Unknown"),
                "error": "Invalid file content"
            }

        file_path = file_content.get("file_path", "Unknown")
        content = file_content.get("content", "")

        # Set default template if none provided
        if not prompt_template:
            prompt_template = f"""# Steps

1. **Analyze the Code**:
    - Identify if the code contains basic definitions like classes, objects, or constants.
    - Look for functional logic or operations related to {query} (e.g., {query} handling, storage, retrieval, or management).
2. **Determine Rating**:
    - Assign ratings below 5 if the code is primarily structural or lacks functional components.
    - Assign ratings between 5 to 10 if the code demonstrates real {query}-related logic or CRUD functionality.
    - Assign ratings above 7 if the code is creating a sql table and mapping schema update, or or demonstrates advanced SQL practices related to {query}.
    - Base the exact score on the extent and complexity of the {query}-related implementation.
# Output Format
just rating, nothing else"""

        # Add the file content after the prompt template
        prompt = f"{prompt_template}\n\nCode to analyze:\n{file_path}\n```\n{content}\n```"
        messages=[
            {"role": "user",   "content": prompt}
        ]
        response = await self.ai_service.chat_async(messages)
        return {
            "status": "success" if response.get("status") == "success" else "error",
            "file_path": file_path,
            "response": response.get("response", ""),
            "error": response.get("error")
        }