#!/usr/bin/env python
"""
Repository cloner utility for Azure DevOps repositories using ManagedIdentityCredential.
This script allows cloning repositories from Azure DevOps using a managed identity for authentication.
"""

import os
import subprocess
import tempfile
from typing import Optional, Dict, Any
import logging

from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

logger = logging.getLogger(__name__)

class RepoCloner:
    """
    Class to handle cloning repositories from Azure DevOps using ManagedIdentityCredential.
    """
    def __init__(self, organization_url: str, client_id: Optional[str] = None):
        """
        Initialize the RepoCloner with the Azure DevOps organization URL and optional client ID.
        
        Args:
            organization_url: The URL of the Azure DevOps organization
            client_id: Optional client ID for the managed identity
        """
        self.organization_url = organization_url
        try:
            # Try to get a Managed Identity Credential first
            if client_id:
                self.credential = ManagedIdentityCredential(client_id=client_id)
            else:
                self.credential = DefaultAzureCredential()
                
            # Test credential (will raise exception if invalid)
            token = self.credential.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default")
            
            # Create PAT-based authentication for Azure DevOps
            self.credentials = BasicAuthentication('', token.token)
            self.connection = Connection(base_url=organization_url, creds=self.credentials)
            logger.info(f"Successfully authenticated to Azure DevOps using ManagedIdentity")
        
        except Exception as e:
            logger.warning(f"Failed to use ManagedIdentityCredential: {e}. Falling back to DefaultAzureCredential.")
            # Fallback to DefaultAzureCredential if ManagedIdentity fails
            self.credential = DefaultAzureCredential()
            token = self.credential.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default")
            self.credentials = BasicAuthentication('', token.token)
            self.connection = Connection(base_url=organization_url, creds=self.credentials)

    def clone_repository(self, project_name: str, repo_name: str, target_dir: Optional[str] = None) -> str:
        """
        Clone a repository from Azure DevOps using git.
        
        Args:
            project_name: Name of the Azure DevOps project
            repo_name: Name of the repository to clone
            target_dir: Optional directory where to clone the repository
                       (if not provided, a temporary directory will be created)
                       
        Returns:
            The path to the cloned repository
        
        Raises:
            Exception: If cloning fails
        """
        # Get a token for Azure DevOps
        token = self.credential.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default")
        
        # Format the URL with the PAT
        git_url = f"https://:{token.token}@{self.organization_url.replace('https://', '')}/{project_name}/_git/{repo_name}"
        
        # Create target directory if not specified
        if not target_dir:
            target_dir = tempfile.mkdtemp(prefix=f"{repo_name}_")
            logger.info(f"Created temporary directory for repository: {target_dir}")
        else:
            os.makedirs(target_dir, exist_ok=True)
        
        # Clone the repository
        try:
            logger.info(f"Cloning repository {repo_name} from project {project_name}...")
            result = subprocess.run(
                ["git", "clone", git_url, target_dir],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Successfully cloned repository to {target_dir}")
            return target_dir
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to clone repository: {e.stderr}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def get_repo_info(self, project_name: str, repo_name: str) -> Dict[Any, Any]:
        """
        Get information about a repository.
        
        Args:
            project_name: Name of the Azure DevOps project
            repo_name: Name of the repository
            
        Returns:
            Dictionary containing repository information
        """
        git_client = self.connection.clients.get_git_client()
        repo = git_client.get_repository(repo_name, project_name)
        return {
            "id": repo.id,
            "name": repo.name,
            "url": repo.web_url,
            "default_branch": repo.default_branch,
            "size": repo.size,
            "project": repo.project.name
        }


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description='Clone Azure DevOps repository using Managed Identity')
    parser.add_argument('--org', required=True, help='Azure DevOps organization URL (e.g., https://msasg.visualstudio.com)')
    parser.add_argument('--project', required=True, help='Azure DevOps project name')
    parser.add_argument('--repo', required=True, help='Repository name')
    parser.add_argument('--dir', help='Target directory for cloning (optional)')
    parser.add_argument('--client-id', help='Client ID for Managed Identity (optional)')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    try:
        cloner = RepoCloner(args.org, client_id=args.client_id)
        repo_path = cloner.clone_repository(args.project, args.repo, args.dir)
        print(f"Repository cloned successfully to: {repo_path}")
        
        # Get and print repo info
        repo_info = cloner.get_repo_info(args.project, args.repo)
        print("\nRepository Information:")
        for key, value in repo_info.items():
            print(f"{key}: {value}")
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)
