from flask_restful import Resource

class HomeResource(Resource):
    def __init__(self, azure_devops_client):
        """
        Initialize the HomeResource with the Azure DevOps client.
        """
        self.azure_devops_client = azure_devops_client

    def get(self):
        """
        Returns a welcome response for the root endpoint.
        """
        return {
            'message': 'Welcome to the API server',
            'endpoints': {
                '/api/health': 'Health check endpoint',
                '/api/search/filelist': 'File list endpoint',
                '/api/search/chat': 'Full content search endpoint',
                '/api/chat': 'Streaming chat endpoint',
                '/api/note': 'Note management endpoint'
            },
            'status': 'online'
        }