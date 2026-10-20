import os


def database_url() -> str:
    # Tests and Docker set DATABASE_URL. Locally we just use a file under ./data.
    return os.environ.get("DATABASE_URL", "sqlite:///./data/tracker.db")
