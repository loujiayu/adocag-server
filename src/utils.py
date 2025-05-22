"""
Utility functions for various services in the application
"""
import re
from typing import List, Optional

def is_raw_query(search_text: str) -> bool:
    """
    Check if a search query is without special filters like path:, ext:, or def:
    
    Args:
        search_text: The search query text
        
    Returns:
        Boolean indicating whether the query has no special filter syntax
    """
    # Regular expression to match common Azure DevOps search filters
    filter_patterns = [
        r'ext:', 
        r'file:',
        r'path:', 
        r'proj:', 
        r'repo:', 
        r'basetype:',
        r'class:',
        r'comment:',
        r'decl:',
        r'def:', 
        r'enum:', 
        r'field:', 
        r'interface:', 
        r'macro:', 
        r'method:', 
        r'namespace:', 
        r'ref:', 
        r'strlit:', 
        r'type:',
    ]
    
    # Check if any filter pattern exists in the search text
    for pattern in filter_patterns:
        if re.search(pattern, search_text, re.IGNORECASE):
            return False
    
    return True
