from flask_restful import Resource
import datetime
import platform

class HealthResource(Resource):
    def __init__(self, azure_devops_client):
        """
        Initialize the HealthResource with the Azure DevOps client.
        """
        self.azure_devops_client = azure_devops_client

    def get(self):
        """
        Returns a health check response indicating the service is up and running
        with basic system information.
        """
        return {
            'status': 'healthy',
            'timestamp': datetime.datetime.now().isoformat,
            'service': 'server-api',
            'azure_devops_client': {
                'organization': self.azure_devops_client.organization,
                'project': self.azure_devops_client.project,
                'resource_area_identifier': self.azure_devops_client.search_client.resource_area_identifier
            },
            'environment': {
                'python_version': platform.python_version(),
                'system': platform.system(),
                'node': platform.node()
            }
        }