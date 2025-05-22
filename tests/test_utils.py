"""
Unit tests for utility functions in the utils module
"""
import unittest
import sys
import os

# Add the src directory to the path so we can import the modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import is_raw_query

class TestUtils(unittest.TestCase):
    """Test cases for utility functions"""
    
    def test_is_raw_query_with_raw_queries(self):
        """Test that plain text queries return True"""
        raw_queries = [
            "search term",
            "another search",
            "code example",
            "function definition",
            "search with spaces",
            "search-with-hyphens",
            "search_with_underscores",
            "123 numbers",
            "mixed123 alphanumeric"
        ]
        
        for query in raw_queries:
            with self.subTest(query=query):
                self.assertTrue(is_raw_query(query), f"Expected '{query}' to be a raw query")
    
    def test_is_raw_query_with_filter_queries(self):
        """Test that queries with filters return False"""
        filter_queries = [
            "ext:py",
            "file:utils.py",
            "path:src/utils.py",
            "proj:adocag-server",
            "repo:adocag-server",
            "class:TestUtils",
            "def:is_raw_query",
            "field:filter_patterns",
            "method:is_raw_query",
            "namespace:src",
            "ref:utils",
            "type:function"
        ]
        
        for query in filter_queries:
            with self.subTest(query=query):
                self.assertFalse(is_raw_query(query), f"Expected '{query}' not to be a raw query")
    
    def test_is_raw_query_with_mixed_content(self):
        """Test queries that contain both raw text and filters"""
        mixed_queries = [
            "search term ext:py",
            "function definition def:is_raw_query",
            "hello path:src/utils.py world",
            "beginning repo:adocag-server ending",
        ]
        
        for query in mixed_queries:
            with self.subTest(query=query):
                self.assertFalse(is_raw_query(query), f"Expected mixed query '{query}' not to be a raw query")
    
    def test_is_raw_query_with_case_insensitivity(self):
        """Test that the function handles case insensitivity correctly"""
        case_insensitive_queries = [
            "EXT:py",
            "File:utils.py",
            "PATH:src/utils.py",
            "DEF:function",
        ]
        
        for query in case_insensitive_queries:
            with self.subTest(query=query):
                self.assertFalse(is_raw_query(query), f"Expected '{query}' not to be a raw query despite case differences")


if __name__ == "__main__":
    unittest.main()
