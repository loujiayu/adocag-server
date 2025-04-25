from app import app as flask_app
from asgiref.wsgi import WsgiToAsgi

# Convert Flask app to ASGI application
app = WsgiToAsgi(flask_app)