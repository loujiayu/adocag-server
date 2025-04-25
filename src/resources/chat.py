from flask_restful import Resource
from flask import request, Response
from src.services.ai_service_factory import AIServiceFactory
import os
import json
from src.services.agents import AIAgent
from src.services.search_utilities import SearchUtilities

class ChatResource(Resource):
    def __init__(self, azure_devops_client=None, **kwargs):
        # Store default API provider that can be overridden by request args
        self.default_api_provider = kwargs.get('api_provider', 'Azure OpenAI')
        self.azure_devops_client = azure_devops_client
        
        # _get_ai_service helper method is called in both __init__ and post
        self.ai_service = self._get_ai_service()
        
        # Pass the AI service to AIAgent
        self.ai_agent = AIAgent(ai_service=self.ai_service)
        
        # Initialize search utilities if we have a search client
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

    def merge_search_results(self, results_list):
        """Merge multiple search results into a single result"""
        if not results_list:
            return {
                "status": "error",
                "message": "No search results to merge"
            }
        
        # Initialize with first result structure
        merged_result = {
            "status": "success",
            "code_results": {
                "status": "success",
                "contents": [],
                "content_count": 0,
                "total_length": 0,
            },
            "wiki_results": {
                "status": "success",
                "results": []
            }
        }
        
        # Merge all results
        for result in results_list:
            if result.get("status") != "success":
                continue
                
            # Merge code results
            code_results = result.get("code_results", {})
            if code_results and code_results.get("status") == "success":
                for content in code_results.get("contents", []):
                    file_path = content.get("file_path")
                    merged_result["code_results"]["contents"].append(content)
            
            # Merge wiki results
            wiki_results = result.get("wiki_results", {})
            if wiki_results and wiki_results.get("status") == "success":
                wiki_items = wiki_results.get("results", [])
                # Add unique wiki results
                for wiki_item in wiki_items:
                    if hasattr(wiki_item, "file_name"):
                        wiki_id = wiki_item.file_name
                        # Check if this wiki page is already in our merged results
                        if not any(hasattr(w, "file_name") and w.file_name == wiki_id 
                                for w in merged_result["wiki_results"]["results"]):
                            merged_result["wiki_results"]["results"].append(wiki_item)
        
        # Update status based on merged content
        if not merged_result["code_results"]["contents"]:
            merged_result["status"] = "error"
        
        return merged_result

    def post(self):
        """Streaming chat endpoint"""
        data = request.get_json()
        query = request.args.get('query')
        repositories = request.args.get('repositories', "")
        is_deep_research = request.args.get('is_deep_research', default='false').lower() == 'true'
        repo_list = [r.strip() for r in repositories.split(",")] if repositories else []

        if not data or 'messages' not in data:
            return {"error": "Message is required in request body"}, 400

        messages = data['messages']

        if is_deep_research:
            # Create a generator function for streaming the deep research results
            def generate_deep_research_stream():
                # Get the user's original question
                user_question = messages[-1]['content']
                
                # Start iterative deep research process
                max_iterations = 5
                current_messages = messages.copy()
                accumulated_context = ""
                keywords = set()
                
                # First yield the initial processing message
                yield self.format_sse_response({
                    "event": "processing",
                    "message": "Starting deep research process...",
                })
                
                for iteration in range(1, max_iterations + 1):
                    print(f"\n=== Starting Deep Research Iteration {iteration}/{max_iterations} ===")
                    
                    # Notify user about current iteration
                    yield self.format_sse_response({
                        "event": "processing",
                        "message": f"Deep Research Iteration {iteration}/{max_iterations}...",
                    })
                    
                    # Step 1: Call deep_research with current messages
                    deep_research_response = self.ai_agent.deep_research(
                        messages=current_messages
                    )

                    if deep_research_response.get("status") == "error":
                        error_msg = f"Deep research failed in iteration {iteration}. Error: {deep_research_response.get('error')}"
                        print(error_msg)
                        yield self.format_sse_response({
                            "event": "processing", 
                            "message": error_msg,
                        })
                        break
                    
                    # Step 2: Run quality check to get top keywords
                    print(f"Running quality check for iteration {iteration}")
                    quality_check_result = self.ai_agent.quality_check(
                        question=user_question,
                        deep_research_response=deep_research_response,
                        top_n=3  # Get top 3 keywords by default
                    )

                    if quality_check_result.get("status") != "success":
                        error_msg = f"Quality check failed in iteration {iteration}. Error: {quality_check_result.get('error')}"
                        print(error_msg)
                        yield self.format_sse_response({
                            "event": "processing",
                            "message": error_msg,
                        })
                        break
                    
                    # Skip to next iteration if no relevant keywords
                    if not quality_check_result.get("top_relevance_keywords"):
                        msg = f"No additional relevant keywords found in iteration {iteration}."
                        print(msg)
                        yield self.format_sse_response({
                            "event": "processing",
                            "message": msg,
                        })
                        break
                    
                    # Step 3: Search for each top keyword
                    print(f"Searching for keywords in iteration {iteration}")
                    
                    # Report the keywords we're searching for
                    current_keywords = [k.get("keyword") for k in quality_check_result["top_relevance_keywords"]]
                    new_keywords = [k for k in current_keywords if k not in keywords]
                    yield self.format_sse_response({
                        "event": "processing",
                        "message": f"Searching for keywords: {', '.join(new_keywords)}",
                    })
                    
                    search_results_list = []
                    for keyword_result in quality_check_result["top_relevance_keywords"]:
                        keyword = keyword_result.get("keyword")

                        if keyword in keywords:
                            print(f"Keyword '{keyword}' already searched. Skipping.")
                            continue
                        keywords.add(keyword)

                        print(f"Searching for keyword: {keyword}")
                        # Get search results for this keyword
                        search_result = self.search_utilities.combine_search_results_with_wiki_sync(
                            query=keyword,
                            repositories=repo_list,
                            include_wiki=True,
                            agent_search=True,
                            max_length=1000000
                        )
                        search_results_list.append(search_result)
                    
                    # If we found search results, merge them
                    if search_results_list:
                        merged_results = self.merge_search_results(search_results_list)
                        # Format the context from merged search results
                        iteration_context = self.search_utilities.format_content_context(merged_results)
                        accumulated_context += f"\n--- Context from Iteration {iteration} ---\n{iteration_context}\n"
                        
                        # Yield interim findings for this iteration
                        yield self.format_sse_response({
                            "event": "processing",
                            "message": f"Iteration {iteration} findings: Found relevant information about {', '.join(new_keywords)}.",
                        })
                        
                        current_messages.append({
                            "role": "assistant",
                            "content": f"Please continue researching my question: {user_question}. Use the additional context to improve your answer. Additional research findings: {iteration_context}"
                        })
                    else:
                        msg = f"No search results found for keywords in iteration {iteration}."
                        print(msg)
                        yield self.format_sse_response({
                            "event": "processing",
                            "message": msg,
                        })
                        break
                
                # After all iterations, generate final comprehensive response
                print("Generating final comprehensive response after all iterations")
                yield self.format_sse_response({
                    "event": "processing",
                    "message": "Research complete. Generating final answer...",
                })
                
                final_prompt = f"""
                Based on the extensive research across multiple iterations:
                
                Original question: {user_question}
                
                The following context was gathered during research:
                {accumulated_context}
                
                Please provide a comprehensive, well-structured answer to the original question 
                that integrates all the information gathered through the iterative research process.
                """

                final_messages = messages.copy()
                final_messages.append({
                    "role": "user",
                    "content": final_prompt
                })
                
                # Stream the final comprehensive response using the AI service
                yield from self.ai_service.stream_chat(messages=final_messages)

            # Return the streaming response
            return Response(
                generate_deep_research_stream(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Content-Type': 'text/event-stream',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no'
                }
            )

        # For regular chat (non-deep-research), return the formatted stream
        return Response(
            self.ai_service.stream_chat(messages=data['messages']),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Content-Type': 'text/event-stream',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )