"""Production WSGI entry point for hosted deployments."""

import os

from dotenv import load_dotenv

load_dotenv()

from internshield import create_app


app = create_app(os.getenv("FLASK_CONFIG", "production"))
