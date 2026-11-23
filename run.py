"""Development entry point for the InternShield Flask application."""

import os

from dotenv import load_dotenv

load_dotenv()

from internshield import create_app


app = create_app(os.getenv("FLASK_CONFIG", "development"))


if __name__ == "__main__":
    # The built-in server is for local development only. Use a production WSGI
    # server when deploying the application.
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=app.config.get("DEBUG", False),
    )
