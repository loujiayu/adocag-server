# Repository search configurations
from dataclasses import dataclass
from typing import List

@dataclass
class RepositorySearchConfig:
    """Configuration for repository-specific search settings"""
    name: str
    search_prefix: str = ""
    excluded_paths: List[str] = None
    included_paths: List[str] = None
    project: str = ""
    organization: str = ""

    def __post_init__(self):
        if self.excluded_paths is None:
            self.excluded_paths = []
        if self.included_paths is None:
            self.included_paths = []

    def apply_prefix(self, search_text: str) -> str:
        """Apply repository-specific prefix to search text"""
        if not self.search_prefix:
            return search_text
        return f"{self.search_prefix} {search_text}"

    def should_exclude_path(self, path: str, agent_search: bool = False) -> bool:
        """Check if the path should be excluded based on repository rules"""
        path_lower = path.lower()
        
        # If included_paths is specified and agent_search is False, path must match one of them
        if self.included_paths and not agent_search:
            if not any(included in path_lower for included in self.included_paths):
                return True
                
        # Check excluded paths
        return any(excluded in path_lower for excluded in self.excluded_paths)

# Repository configuration definitions
REPOSITORY_CONFIGS = {
    "AdsAppsMT": RepositorySearchConfig(
        name="AdsAppsMT",
        organization="msasg",
        project="Bing_Ads",
        search_prefix="(ext:cs)",
        excluded_paths=['test', 'proxy', 'proxies', 'campaignservice.cs'],
    ),
    "AdsAppsDB": RepositorySearchConfig(
        name="AdsAppsDB",
        organization="msasg",
        project="Bing_Ads",
        search_prefix="(ext:sql)",
        included_paths=['prc_public']
    ),
    "AdsAppsCampaignUI": RepositorySearchConfig(
        name="AdsAppsCampaignUI",
        organization="msasg",
        project="Bing_Ads",
        search_prefix="(ext:js OR ext:ts OR ext:jsx OR ext:tsx)",
        excluded_paths=['test', 'suite', 'tapi', 'demo']
    ),
    "AdsAppUISharedComponents": RepositorySearchConfig(
        name="AdsAppUISharedComponents",
        organization="msasg",
        project="Bing_Ads",
        search_prefix="(ext:js OR ext:ts OR ext:jsx OR ext:tsx OR ext:es)",
        excluded_paths=['test', 'suite', 'tapi', 'demo']
    ),
    "AdsAppUI": RepositorySearchConfig(
        name="AdsAppUI",
        organization="msasg",
        project="Bing_Ads",
        search_prefix="(ext:js OR ext:ts OR ext:jsx OR ext:tsx)",
        excluded_paths=['test', 'suite', 'tapi', 'demo']
    ),
    "msnews-experiences": RepositorySearchConfig(
        name="msnews-experiences",
        organization="msasg",
        project="ContentServices",
        search_prefix="(ext:js OR ext:ts OR ext:jsx OR ext:tsx)",
        excluded_paths=['test', 'undefined']
    ),
    "coreux-components": RepositorySearchConfig(
        name="coreux-components",
        organization="msasg",
        project="ContentServices",
        search_prefix="(ext:js OR ext:ts OR ext:jsx OR ext:tsx)",
        excluded_paths=[]
    ),
}

def get_repository_config(repository_name: str) -> RepositorySearchConfig:
    """Get repository configuration from REPOSITORY_CONFIGS
    
    Args:
        repository_name: Name of the repository to get configuration for
        
    Returns:
        RepositorySearchConfig: The configuration for the specified repository
        
    Raises:
        ValueError: If the repository is not configured in REPOSITORY_CONFIGS
    """
    if repository_name not in REPOSITORY_CONFIGS:
        raise ValueError(f"Repository '{repository_name}' is not configured in REPOSITORY_CONFIGS")
    return REPOSITORY_CONFIGS[repository_name]
