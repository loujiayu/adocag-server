from src import create_app
import asyncio
import os

app = create_app()

if __name__ == "__main__":
	# app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

	import hypercorn.asyncio
	import hypercorn.config
	
	config = hypercorn.config.Config()
	port = int(os.environ.get("PORT", 8080))
	config.bind = [f"0.0.0.0:{port}"]
	
	# Import the ASGI application from asgi.py
	from asgi import app as asgi_app
	
	# Run with Hypercorn
	asyncio.run(hypercorn.asyncio.serve(asgi_app, config))