"""
Unit tests for utility functions in the main module
"""
import unittest
import sys
import os
from unittest.mock import MagicMock

# Add the src directory to the path so we can import the modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import extract_auth_token

class TestMainUtils(unittest.TestCase):
    """Test cases for utility functions in main.py"""
    
    def test_extract_auth_token_with_valid_token(self):
        """Test that a valid bearer token is correctly extracted"""
        # Create a mock Request object with a valid Authorization header
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer test-token-123"}
        
        # Extract the token
        token = extract_auth_token(mock_request)
        
        # Verify the token was extracted correctly
        self.assertEqual(token, "test-token-123")
    
    def test_extract_auth_token_with_no_auth_header(self):
        """Test that None is returned when no Authorization header is present"""
        # Create a mock Request object with no Authorization header
        mock_request = MagicMock()
        mock_request.headers = {}
        
        # Extract the token
        token = extract_auth_token(mock_request)
        
        # Verify None is returned
        self.assertIsNone(token)
    
    def test_extract_auth_token_with_invalid_format(self):
        """Test that None is returned when Authorization header doesn't start with 'Bearer '"""
        # Create a mock Request object with an invalid Authorization header format
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        
        # Extract the token
        token = extract_auth_token(mock_request)
        
        # Verify None is returned
        self.assertIsNone(token)
    
    def test_extract_auth_token_with_empty_bearer_token(self):
        """Test that an empty string is returned when bearer token is empty"""
        # Create a mock Request object with an empty bearer token
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer "}
        
        # Extract the token
        token = extract_auth_token(mock_request)
        
        # Verify an empty string is returned
        self.assertEqual(token, "")

if __name__ == '__main__':
    unittest.main()
