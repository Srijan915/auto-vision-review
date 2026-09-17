import os
from dotenv import load_dotenv

load_dotenv()


def get_gemini_api_key() -> str | None:
    """Return the configured key without exposing it or requiring Gemini globally."""
    return os.getenv("GEMINI_API_KEY")
