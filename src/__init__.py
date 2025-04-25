from flask import Flask, jsonify
from dotenv import load_dotenv
import asyncio
from src.services.azure_devops_search import AzureDevOpsSearch
import logging
import os
from flask_cors import CORS

logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s "
)

def create_app():
    load_dotenv()
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes

    from src.config import Config
    app.config.from_object(Config)

    @app.route('/check-asgi')
    async def check_asgi():
        import inspect
        
        # If this works, we're in ASGI mode
        if inspect.iscoroutinefunction(check_asgi):
            await asyncio.sleep(0.1)
            return jsonify({
                "asgi_mode": True,
                "message": "Application is running in ASGI mode"
            })
        
        # This shouldn't execute in ASGI mode
        return jsonify({
            "asgi_mode": False,
            "message": "Application is NOT running in ASGI mode"
        })
    
    # Initialize Azure DevOps client
    azure_devops_client = AzureDevOpsSearch(
        organization=os.getenv('AZURE_DEVOPS_ORG'),
        project=os.getenv('AZURE_DEVOPS_PROJECT')
    )
    
    # Register routes for resources
    from src.resources.health import HealthResource
    from src.resources.home import HomeResource
    from src.resources.search import DocumentSearchResource
    from src.resources.chat import ChatResource
    from src.resources.note import NoteResource
    
    # Register health check endpoint
    app.add_url_rule('/api/health', view_func=HealthResource.as_view('health', azure_devops_client))
    
    # Register home endpoint
    app.add_url_rule('/', view_func=HomeResource.as_view('home', azure_devops_client))
    
    # Register search endpoint
    app.add_url_rule('/api/search', view_func=DocumentSearchResource.as_view('search_chat', azure_devops_client))
    
    # Register chat endpoint
    app.add_url_rule('/api/chat', view_func=ChatResource.as_view('chat', azure_devops_client))
    
    # Register note endpoints
    note_view = NoteResource.as_view('note', azure_devops_client)
    app.add_url_rule('/api/note', view_func=note_view, methods=['GET', 'POST'])
    app.add_url_rule('/api/note/<note_id>', view_func=note_view, methods=['GET', 'PUT', 'DELETE'])

    return app