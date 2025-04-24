from flask_restful import Resource
from flask import request, jsonify
from src.services.ai_service_factory import AIServiceFactory
from src.services.agents import AIAgent
from src.services.azure_devops_search import AzureDevOpsSearch
import time

class NoteResource(Resource):
    def __init__(self, azure_devops_client):
        """Initialize the note resource
        
        This resource handles operations for user notes including:
        - Creating new notes
        - Getting existing notes
        - Updating notes
        - Deleting notes
        """
        # Store notes in memory for now (in a production app, you'd use a database)
        self.notes = {}
        self.azure_devops_client: AzureDevOpsSearch = azure_devops_client
        self.ai_service = AIServiceFactory.create_service(request.args)
        self.ai_agent = AIAgent(ai_service=self.ai_service)
        
    def get(self, note_id=None):
        """Get one note by ID or all notes"""
        if note_id:
            # Get a specific note
            if note_id in self.notes:
                return self.notes[note_id]
            return {"status": "error", "message": "Note not found"}, 404
        else:
            # Get all notes
            return {"status": "success", "notes": list(self.notes.values())}
    
    def post(self):
        """Create a new note"""
        try:
            data = request.get_json()
            
            if not data or 'content' not in data:
                return {"status": "error", "message": "Content is required"}, 400
                
            response = self.ai_agent.note_name(data['content'])
            if response.get("status") == "error":
                return {"status": "error", "message": response.get("error")}, 500
            
            note_name = response.get("response", "Untitled Note")

            save_res = self.azure_devops_client.save_wiki_page(note_name, data['content'])

            if save_res.get("status") == "error":
                return {"status": "error", "message": save_res.get("error")}, 500
            
            return {"status": "success", "id": save_res['page'].page.id, "title": note_name}, 201
            
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500
    
    def put(self, note_id):
        """Update an existing note"""
        if note_id not in self.notes:
            return {"status": "error", "message": "Note not found"}, 404
            
        try:
            data = request.get_json()
            
            if not data:
                return {"status": "error", "message": "No data provided"}, 400
                
            # Update note fields
            if 'content' in data:
                self.notes[note_id]['content'] = data['content']
                
            if 'title' in data:
                self.notes[note_id]['title'] = data['title']
                
            # Update timestamp
            self.notes[note_id]['updated_at'] = int(time.time())
            
            return {"status": "success", "note": self.notes[note_id]}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500
    
    def delete(self, note_id):
        """Delete a note"""
        if note_id not in self.notes:
            return {"status": "error", "message": "Note not found"}, 404
        
        res = self.azure_devops_client.delete_wiki_page(note_id)

        if res.get("status") == "error":
            return {"status": "error", "message": res.get("error")}, 500
            
        return {"status": "success", "message": "Note deleted"}, 200