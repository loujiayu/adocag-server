from typing import Dict, List, Any, Optional
import os
from src.services.azure_devops_search import AzureDevOpsSearch
import asyncio
from src.services.cache_manager import CacheManager
from pydantic import BaseModel

class SearchSource(BaseModel):
    repositories: List[str]
    query: Optional[str] = None

class SearchUtilities:
    """
    Utility class for performing code searches and processing search results.
    This class provides reusable methods for searching code repositories and 
    processing the results to extract file contents.
    """
    
    def __init__(self, search_client: AzureDevOpsSearch, ai_agent=None, rating_threshold=7, cache_enabled=True):
        """
        Initialize search utilities with required clients
        
        Args:
            search_client: Client for performing searches (e.g., AzureDevOpsSearch)
            ai_agent: Optional AI agent for rating search results
            rating_threshold: Minimum rating threshold for including files in results
            cache_enabled: Whether to enable caching of search results
        """
        self.search_client = search_client
        self.ai_agent = ai_agent
        self.rating_threshold = rating_threshold
        self.cache_enabled = cache_enabled
        self.content_cache_ttl = 3600 * 24 * 14  # Cache file content for 7 days
        self.rate_cache_ttl = 3600 * 24 * 20  # Cache rating for 7 days
        
        content_semaphore_limit = 100
        rating_semaphore_limit = 5

        # Initialize semaphores for concurrent operations
        self.content_semaphore = asyncio.Semaphore(content_semaphore_limit)
        self.rating_semaphore = asyncio.Semaphore(rating_semaphore_limit)
        
        # Initialize cache if enabled
        self.cache = None
        if self.cache_enabled:
            cache_manager = CacheManager()
            self.cache = cache_manager.get_cache()
            print(f"Cache initialized with type: {cache_manager.get_cache_type()}")

    def search_repositories(self, sources: List[SearchSource], agent_search=False) -> Dict:
        """
        Search across one or more repositories with different queries
        
        Args:
            sources: List of search sources, each containing query and repositories
            agent_search: Whether this search is initiated by an agent
            
        Returns:
            Dictionary with search results and status
        """
        # Initialize combined results
        combined_results = {
            "status": "success",
            "results": [],
            "count": 0,
        }
        
        # Search for each source's query in its repositories
        for source in sources:
            if not source.query or not source.repositories:
                continue
                
            for repo in source.repositories:
                if not repo:
                    continue
                    
                search_results = self.search_client.search_code(
                    search_text=source.query,
                    repository=repo,
                    agent_search=agent_search
                )
                if search_results["status"] == "success":
                    # Add the query to each result for better sorting later
                    for result in search_results["results"]:
                        result.search_query = source.query
                    combined_results["results"].extend(search_results["results"])
                    combined_results["count"] += search_results["count"]        # Sort results by relevance using each result's own query
        if combined_results["results"]:
            # First sort by content matches
            combined_results["results"].sort(
                key=lambda x: -len(x.matches.get('content', []))
            )
            
            # Then group files by whether their query appears in path
            # while maintaining relative order within each group
            path_matches = []
            other_results = []
            
            for result in combined_results["results"]:
                query = getattr(result, 'search_query', '').lower()
                if query and query in result.path.lower():
                    path_matches.append(result)
                else:
                    other_results.append(result)
            
            # Combine the results maintaining the sort within each group
            combined_results["results"] = path_matches + other_results
        
        return combined_results

    async def get_file_content_from_results(self, results: Dict, max_length: int, with_rating: bool = True) -> Dict:
        """
        Get the content of files from search results and sort them by content length
        
        Args:
            results: Search results from search_code or search_repositories, each result should have search_query
            max_length: Maximum number of characters to retrieve (default: 3000000)
            
        Returns:
            Dictionary containing the sorted file contents and status
        """
        if results["status"] != "success" or results["count"] == 0:
            return {
                "status": "error",
                "message": "No results found or search failed",
            }
        
        # Process all results
        file_contents = []
        processed_count = 0
        
        print(f"Processing {len(results['results'])} search results")

        # Create a shared length counter and max length reached event
        length_lock = asyncio.Lock()
        max_length_reached = asyncio.Event()
        # Use a list with one element to store the current length, as lists are mutable
        current_length = [0]

        # Create tasks for all files to process them concurrently
        tasks = []
        for result in results["results"]:
            # Extract repository name, file path, and branch
            repository = result.repository.name if hasattr(result, 'repository') and hasattr(result.repository, 'name') else None
            file_path = result.path if hasattr(result, 'path') else None
            branch = getattr(result, 'branch', None)
            
            if not repository or not file_path:
                # Skip this result if repository or file path is missing
                continue
                
            # Get the search query for this result
            search_query = getattr(result, 'search_query', '')
            
            # Create task to process this file
            tasks.append(self._process_file_content(
                repository, file_path, branch, search_query, 
                max_length, length_lock, max_length_reached, current_length, with_rating
            ))
        
        # Wait for all processing tasks to complete
        file_results = await asyncio.gather(*tasks)
        
        # Process valid results
        for file_result in file_results:
            if not file_result:
                continue
                
            content_result = file_result['content_result']
            file_path = file_result['file_path']
            repository = file_result['repository']
            branch = file_result['branch']
            
            processed_count += 1
            
            if content_result["status"] == "success":
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
            "total_length": sum(len(x.get("content", "")) for x in file_contents),
            "max_length": max_length,
        }
        
        return result

    async def _process_file_content(self, repository, file_path, branch, search_query, 
                                  max_length, length_lock, max_length_reached, current_length, with_rating):
        """
        Helper method to process a single file's content and rating with semaphores
        
        Args:
            repository: Repository name
            file_path: Path to the file
            branch: Branch name
            search_query: Search query used to find this file
            max_length: Maximum total length allowed
            length_lock: Lock for updating the shared length counter
            max_length_reached: Event that is set when max length is reached
            current_length: List with a single element [total_length] to track current length
        """
        # Check if max length has already been reached
        if max_length_reached.is_set():
            print(f"Skipping file {file_path}: max length already reached")
            return None
            
        # Use file path directly as cache key, nothing else
        cache_key = file_path
        
        # Fetch content with content semaphore
        async with self.content_semaphore:
            content_result = await self.get_file_content(repository, file_path, branch, cache_key)

        # Check if content retrieval was successful
        if not content_result or content_result["status"] != "success":
            print(f"Error fetching content for {file_path}")
            return None
            
        # Check file size before continuing with more processing
        content_length = len(content_result["content"])
        
        # Skip files larger than 200K characters
        if content_length > 200000:
            print(f"Skipping large file {file_path}: {content_length} characters")
            return None
            
        # Rate the file if AI agent is available
        rating_cache_key = f"{search_query.lower()}-rate:{file_path}"

        if max_length_reached.is_set():
            print(f"Skipping file {file_path}: max length already reached")
            return None
        
        if with_rating:
            # Use rating semaphore for rating operations
            async with self.rating_semaphore:
                rate = await self.rate_file_content(content_result, search_query, rating_cache_key)

            if rate < self.rating_threshold:
                print(f"Skipping file {file_path} with rating {rate}")
                return None
        
        # Check if adding this file would exceed the length limit
        async with length_lock:
            # Check again if max length has been reached while we were waiting for the lock
            if max_length_reached.is_set():
                return None
                
            new_total_length = current_length[0] + content_length
            if new_total_length > max_length:
                print(f"Length limit reached ({current_length[0]}/{max_length}). Skipping file {file_path}")
                max_length_reached.set()
                return None
                
            # Update the current length
            current_length[0] = new_total_length
            print(f"Updated total length: {current_length[0]}/{max_length}, processing file {file_path}")

        return {
            'content_result': content_result,
            'file_path': file_path,
            'repository': repository,
            'branch': branch,
        }
        
    async def rate_file_content(self, content_result, search_query, cache_key=None):
        """
        Rate file content relevance to the search query
        
        Args:
            content_result: Dictionary containing file content and status
            search_query: Query to rate the content against
            cache_key: Optional cache key for rating, defaults to None
            
        Returns:
            Integer rating of the content
        """
        # Set default rating if AI agent is not available
        rate = self.rating_threshold
        
        # If no cache key provided, use a default format
        if cache_key is None and search_query:
            file_path = content_result.get("file_path", "unknown")
            cache_key = f"{search_query.lower()}-rate:{file_path}"
            
        # Try to get rating from cache if cache is enabled
        if self.cache:
            cached_rating = await self.cache.get(cache_key)
            if cached_rating is not None:
                print(f"Cache hit for rating: {cache_key}")
                return cached_rating
        
        # If AI agent is available, get rating
        if self.ai_agent:
            try:
                # Get rating from AI agent
                rating_result = await self.ai_agent.rate_single_file(content_result, query=search_query)
                try:
                    rate = int(rating_result.get("response", "0"))
                    # Cache the rating if cache is enabled
                    if self.cache:
                        await self.cache.set(cache_key, rate, self.rate_cache_ttl)
                        print(f"Cached rating for: {cache_key}")
                except (ValueError, TypeError):
                    print(f"Error parsing rating result: {rating_result}")
                    rate = 0
            except Exception as e:
                print(f"Error getting rating: {str(e)}")
                rate = 0
                
        return rate

    async def get_file_content(self, repository, file_path, branch, cache_key=None):
        """
        Get file content from cache or from repository
        
        Args:
            repository: Repository name
            file_path: Path to the file
            branch: Branch name
            cache_key: Optional cache key, defaults to file_path if not provided
            
        Returns:
            Dictionary containing file content and status
        """
        if cache_key is None:
            cache_key = file_path
            
        # Try to get file content from cache if cache is enabled
        content_result = None
        if self.cache:
            content_result = await self.cache.get(cache_key)
            
            if content_result:
                print(f"Cache hit for file: {cache_key}")
                return content_result
            else:
                print(f"Cache miss for file: {cache_key}")
        
        # Get file content from repository using the async method
        content_result = await self.search_client.get_file_content_rest(
            repository, file_path, branch
        )
        
        # Cache file content if retrieval was successful and cache is enabled
        if content_result and content_result["status"] == "success":
            await self.cache.set(cache_key, content_result, self.content_cache_ttl)
            print(f"Cached file content for: {cache_key}")
            
        return content_result

    async def combine_search_results_with_wiki(self, sources: List[SearchSource], include_wiki=True, agent_search=False, max_length: int = 3000000) -> Dict:
        """
        Perform comprehensive searches including code repositories and wiki for multiple sources
        
        Args:
            sources: List of search sources, each containing query and repositories
            include_wiki: Whether to include wiki results
            agent_search: Whether this search is initiated by an agent
            max_length: Maximum content length to retrieve
            
        Returns:
            Dictionary with combined search results and file contents
        """
        # Get code search results
        code_results = self.search_repositories(sources, agent_search=agent_search)
        
        agent_mode_limit = 50
        if code_results["count"] > agent_mode_limit and agent_search:
            # Limit the number of results for agent searches
            code_results["results"] = code_results["results"][:agent_mode_limit]
            
        # Get file contents
        file_content = await self.get_file_content_from_results(code_results, max_length=max_length)
        
        # Add wiki results if requested - search wiki with all queries
        wiki_results = None
        if include_wiki and hasattr(self.search_client, 'search_wiki'):
            wiki_combined = {
                "status": "success",
                "results": [],
                "count": 0
            }
            
            for source in sources:
                if source.query:
                    wiki_result = self.search_client.search_wiki(source.query)
                    if wiki_result and wiki_result.get("status") == "success":
                        # Add unique wiki results
                        for result in wiki_result.get("results", []):
                            if not any(existing.file_name == result.file_name 
                                    for existing in wiki_combined["results"] 
                                    if hasattr(existing, "file_name")):
                                wiki_combined["results"].append(result)
                                wiki_combined["count"] += 1
            
            if wiki_combined["count"] > 0:
                wiki_results = wiki_combined
        
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