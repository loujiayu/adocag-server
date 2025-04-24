from typing import Dict
import os
import hashlib
from src.services.cache_manager import CacheManager

class SearchUtilities:
    """
    Utility class for performing code searches and processing search results.
    This class provides reusable methods for searching code repositories and 
    processing the results to extract file contents.
    """
    
    def __init__(self, search_client, ai_agent=None, rating_threshold=7, cache_enabled=True, cache_ttl=3600):
        """
        Initialize search utilities with required clients
        
        Args:
            search_client: Client for performing searches (e.g., AzureDevOpsSearch)
            ai_agent: Optional AI agent for rating search results
            rating_threshold: Minimum rating threshold for including files in results
            cache_enabled: Whether to enable caching of search results
            cache_ttl: Time-to-live for cached items in seconds (default: 1 hour)
        """
        self.search_client = search_client
        self.ai_agent = ai_agent
        self.rating_threshold = rating_threshold # Minimum rating to consider a file relevant
        self.cache_enabled = cache_enabled
        self.content_cache_ttl = 3600 * 24 * 7  # Cache file content for 7 days
        self.rate_cache_ttl = 3600 * 24 * 10  # Cache rating for 7 days
        
        # Initialize cache if enabled
        self.cache = None
        if self.cache_enabled:
            cache_manager = CacheManager()
            self.cache = cache_manager.get_cache()
            print(f"Cache initialized with type: {cache_manager.get_cache_type()}")

    def search_repositories(self, query: str, repositories=None, agent_search=False) -> Dict:
        """
        Search across one or more repositories
        
        Args:
            query: Search query text
            repositories: List of repository names to search
            agent_search: Whether this search is initiated by an agent (affects path filtering)
            
        Returns:
            Dictionary with search results and status
        """
                
        # Initialize combined results
        combined_results = {
            "status": "success",
            "results": [],
            "count": 0,
            "search_text": query
        }
        
        # Search each repository separately and combine results
        for repo in repositories:
            if not repo:
                continue
                
            search_results = self.search_client.search_code(
                search_text=query,
                repository=repo,
                agent_search=agent_search
            )
            
            if search_results["status"] == "success":
                combined_results["results"].extend(search_results["results"])
                combined_results["count"] += search_results["count"]

        # Sort results by relevance
        if combined_results["results"]:
            combined_results["results"].sort(
                key=lambda x: (
                    -int(query.lower() in x.path.lower()),  # Priority to files with search text in path
                    -len(x.matches.get('content', []))      # Secondary sort by content matches
                )
            )
        return combined_results

    def get_file_content_from_results(self, results: Dict, query: str, max_length: int) -> Dict:
        """
        Get the content of files from search results and sort them by content length
        
        Args:
            results: Search results from search_code or search_repositories
            query: Optional search query to use for file rating
            max_length: Maximum number of characters to retrieve (default: 3000000)
            
        Returns:
            Dictionary containing the sorted file contents and status
        """
        if results["status"] != "success" or results["count"] == 0:
            return {
                "status": "error",
                "message": "No results found or search failed",
                "search_text": results.get("search_text", "")
            }
        
        # Process all results
        file_contents = []
        total_length = 0
        processed_count = 0
        
        print(f"Processing {len(results['results'])} search results")

        for result in results["results"]:
            # Extract repository name, file path, and branch
            repository = result.repository.name if hasattr(result, 'repository') and hasattr(result.repository, 'name') else None
            file_path = result.path if hasattr(result, 'path') else None
            branch = getattr(result, 'branch', 'master')
            
            if not repository or not file_path:
                # Skip this result if repository or file path is missing
                continue
            
            # Use file path directly as cache key, nothing else
            cache_key = file_path
            content_result = None
            
            if self.cache_enabled and self.cache:
                # Try to get file content from cache
                content_result = self.cache.get(cache_key)
                if content_result:
                    print(f"Cache hit for file: {cache_key}")
                else:
                    print(f"Cache miss for file: {cache_key}")
                    # Get file content from repository
                    content_result = self.search_client.get_file_content(repository, file_path, branch)
                    # Cache file content
                    if content_result["status"] == "success":
                        self.cache.set(cache_key, content_result, self.content_cache_ttl)
                        print(f"Cached file content for: {cache_key}")
            else:
                # Get file content from repository
                content_result = self.search_client.get_file_content(repository, file_path, branch)
            
            # Rate the file if AI agent is available
            rate = self.rating_threshold  # Default rating if no AI agent
            rating_cache_key = f"{query}-rate:{file_path}"
            
            if self.ai_agent and query:
                # Try to get rating from cache first
                if self.cache_enabled and self.cache:
                    cached_rating = self.cache.get(rating_cache_key)
                    if cached_rating is not None:
                        print(f"Cache hit for rating: {rating_cache_key}")
                        rate = cached_rating
                    else:
                        # Get rating from AI agent
                        rating_result = self.ai_agent.rate_single_file(content_result, query=query)
                        try:
                            rate = int(rating_result.get("response", "0"))
                            # Cache the rating
                            self.cache.set(rating_cache_key, rate, self.rate_cache_ttl)
                            print(f"Cached rating for: {rating_cache_key}")
                        except (ValueError, TypeError):
                            rate = 0
                else:
                    # Get rating directly from AI agent
                    rating_result = self.ai_agent.rate_single_file(content_result, query=query)
                    try:
                        rate = int(rating_result.get("response", "0"))
                    except (ValueError, TypeError):
                        rate = 0

            if rate < self.rating_threshold:
                print(f"Skipping file {file_path} with rating {rate}")
                continue

            print(f"Processing file {file_path} with rating {rate}")
            processed_count += 1
            
            if content_result["status"] == "success":
                content_length = len(content_result["content"])
                
                # Skip files larger than 200K characters
                if content_length > 200000:
                    print(f"Skipping large file {file_path}: {content_length} characters")
                    continue
                
                # Check if adding this file would exceed the length limit
                if total_length + content_length > max_length:
                    print(f"Length limit reached ({total_length}/{max_length}). Stopping content retrieval.")
                    break
                
                total_length += content_length
                print(f"Total Length: {total_length}/{max_length}, Files: {processed_count}")
                
                # Add file path to content result for reference
                content_result["file_path"] = file_path
                content_result["repository"] = repository
                content_result["branch"] = branch
                file_contents.append(content_result)
            else:
                # Log the error for this file
                print(f"Error fetching content for {file_path}: {content_result.get('message', 'Unknown error')}")
        
        # Sort file_contents by content length in descending order
        file_contents.sort(key=lambda x: len(x.get("content", "")) if "content" in x else 0, reverse=True)
        
        result = {
            "status": "success" if file_contents else "error",
            "message": "" if file_contents else "Could not extract content from any of the results",
            "content_count": len(file_contents),
            "contents": file_contents,
            "total_length": total_length,
            "max_length": max_length,
            "search_text": results.get("search_text", "")
        }
        
        return result

    def combine_search_results_with_wiki(self, query: str, repositories=None, include_wiki=True, agent_search=False, max_length: int = 3000000) -> Dict:
        """
        Perform a comprehensive search including code repositories and wiki
        
        Args:
            query: Search query
            repositories: Optional list of repositories to search
            include_wiki: Whether to include wiki results
            agent_search: Whether this is an agent search (ignores included_paths)
            
        Returns:
            Dictionary with combined search results and file contents
        """
        # Get code search results
        code_results = self.search_repositories(query, repositories, agent_search=agent_search)
        
        agent_mode_limit = 50
        if code_results["count"] > agent_mode_limit and agent_search:
            # Limit the number of results to 100 for non-agent searches
            code_results["results"] = code_results["results"][:agent_mode_limit]
            
        # Get file contents
        file_content = self.get_file_content_from_results(code_results, query, max_length=max_length)
        
        # Add wiki results if requested
        wiki_results = None
        if include_wiki and hasattr(self.search_client, 'search_wiki'):
            wiki_results = self.search_client.search_wiki(query)
        
        return {
            "status": "success" if file_content.get("status") == "success" or (wiki_results and wiki_results.get("status") == "success") else "error",
            "code_results": file_content,
            "wiki_results": wiki_results
        }

    @staticmethod
    def format_content_context(search_results: Dict) -> str:
        """
        Format search results into a context string for AI processing
        
        Args:
            search_results: Results from combine_search_results_with_wiki
            
        Returns:
            Formatted context string
        """
        context = "\n\nContext from codebase:\n"
        
        # Add code content
        code_results = search_results.get("code_results", {})
        if code_results and code_results.get("status") == "success":
            for content in code_results.get('contents', []):
                context += f"\nFile: {content.get('file_path', 'Unknown')}\n```\n{content.get('content', '')}\n```\n"

        # Add wiki content
        wiki_results = search_results.get("wiki_results", {})
        if wiki_results and wiki_results.get("status") == "success":
            context += "\n\nContext from Wiki:\n"
            for result in wiki_results.get("results", []):
                if hasattr(result, "content") and result.content:
                    context += f"\nWiki Page: {result.file_name}\n{result.content}\n"
        
        return context