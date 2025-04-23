from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from flask_restful import Api
from app.services.azure_devops_search import AzureDevOpsSearch
import logging
import os

logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s "
)

def create_app():
    load_dotenv()
    app = Flask(__name__)
    CORS(app, supports_credentials=True)  # Allow credentials and all origins

    api = Api(app)
    from app.config import Config
    app.config.from_object(Config)

    # Initialize services
    azure_devops_client = AzureDevOpsSearch(
        organization=os.getenv('AZURE_DEVOPS_ORG'),
        project=os.getenv('AZURE_DEVOPS_PROJECT')
    )

    # Register resources
    from app.resources.search import DocumentSearchResource
    from app.resources.chat import ChatResource
    from app.resources.note import NoteResource
    from app.resources.health import HealthResource
    
    # File list endpoint
    api.add_resource(DocumentSearchResource,
                     '/api/search/filelist',
                     endpoint='filelist',
                     resource_class_kwargs={
                         'method_type': 'filelist',
                         'azure_devops_client': azure_devops_client
                     })
    
    # Full content search endpoint
    api.add_resource(DocumentSearchResource,
                     '/api/search/chat',
                     endpoint='chat',
                     resource_class_kwargs={
                         'method_type': 'chat',
                         'azure_devops_client': azure_devops_client
                     })

    # Add streaming chat endpoint
    api.add_resource(ChatResource,
                     '/api/chat',
                     resource_class_kwargs={
                         'azure_devops_client': azure_devops_client
                     })

    # Add note endpoint
    api.add_resource(NoteResource,
                     '/api/note',
                     '/api/note/<string:note_id>',
                     resource_class_kwargs={
                         'azure_devops_client': azure_devops_client
                     })

    # Add health check endpoint
    api.add_resource(HealthResource,
                     '/api/health',
                     resource_class_kwargs={
                         'azure_devops_client': azure_devops_client
                     })

    return app