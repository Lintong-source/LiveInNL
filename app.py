"""Compatibility entry point for Flask CLI and existing deployment tooling."""

from expatus import create_app


app = create_app()


if __name__ == "__main__":
    import os

    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )
