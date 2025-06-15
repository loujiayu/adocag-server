#!/usr/bin/env python
"""
Script to clone the AdsAppsCampaignUI repository using ManagedIdentityCredential.
"""

import os
import subprocess
import logging
import tempfile
import argparse
from pathlib import Path
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clone_ads_campaign_ui(target_dir=None, client_id=None):
    """
    Clone the AdsAppsCampaignUI repository using ManagedIdentityCredential.
    
    Args:
        target_dir: Optional directory where to clone the repository.
                   If not specified, will create a directory in the current path.
        client_id: Optional client ID for the managed identity.
    
    Returns:
        The path to the cloned repository
    """
    # Azure DevOps organization URL
    organization_url = "https://msasg.visualstudio.com"
    
    # Project and repository names
    project_name = "Bing_Ads"
    repo_name = "AdsAppsCampaignUI"
    
    # Create default target directory if not provided
    if not target_dir:
        current_dir = Path.cwd()
        target_dir = os.path.join(current_dir, repo_name)
        logger.info(f"No target directory provided, will use: {target_dir}")
    
    try:
        # Get token using ManagedIdentityCredential
        logger.info("Attempting to authenticate using ManagedIdentityCredential...")
        try:
            # Try to get a Managed Identity Credential first
            if client_id:
                credential = ManagedIdentityCredential(client_id=client_id)
            else:
                credential = ManagedIdentityCredential(client_id=os.getenv('CLIENT_ID'))
                
            # Azure DevOps resource scope
            token = credential.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default")
            logger.info("Successfully authenticated using ManagedIdentityCredential")
        except Exception as e:
            logger.warning(f"Failed to use ManagedIdentityCredential: {e}. Falling back to DefaultAzureCredential.")
            credential = DefaultAzureCredential()
            token = credential.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default")
            logger.info("Successfully authenticated using DefaultAzureCredential")
        
        # Format the URL with the token
        git_url = f"https://:{token.token}@msasg.visualstudio.com/Bing_Ads/_git/AdsAppsCampaignUI"
        
        # Ensure the target directory exists
        os.makedirs(target_dir, exist_ok=True)
        
        # Clone the repository
        logger.info(f"Cloning AdsAppsCampaignUI repository to {target_dir}..., git_url={git_url})")
        result = subprocess.run(
            ["git", "clone", git_url, target_dir],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Successfully cloned repository to {target_dir}")
        
        # Try to get repository information
        try:
            # Create connection with the obtained token
            credentials = BasicAuthentication('', token.token)
            connection = Connection(base_url=organization_url, creds=credentials)
            
            # Get git client and repository info
            git_client = connection.clients.get_git_client()
            repo = git_client.get_repository(repo_name, project_name)
            
            # Display repository information
            logger.info("Repository information:")
            logger.info(f"ID: {repo.id}")
            logger.info(f"Name: {repo.name}")
            logger.info(f"URL: {repo.web_url}")
            logger.info(f"Default Branch: {repo.default_branch}")
            logger.info(f"Size: {repo.size}")
            logger.info(f"Project: {repo.project.name}")
        except Exception as e:
            logger.warning(f"Could not retrieve detailed repository information: {e}")
        
        return target_dir
        
    except Exception as e:
        logger.error(f"Failed to clone repository: {str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clone AdsAppsCampaignUI repository')
    parser.add_argument('--dir', help='Target directory for cloning (optional)')
    parser.add_argument('--client-id', help='Client ID for Managed Identity (optional)')
    args = parser.parse_args()
    
    try:
        repo_path = clone_ads_campaign_ui(args.dir, args.client_id)
        print(f"Repository cloned successfully to: {repo_path}")
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)
