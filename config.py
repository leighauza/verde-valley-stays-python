import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# --- Google Calendar ---
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "google_token.json")

# --- Model ---
CLAUDE_MODEL = "claude-sonnet-4-20250514"
EMBEDDING_MODEL = "text-embedding-3-small"

# --- Context Window ---
CONTEXT_MESSAGE_LIMIT = 10

# --- Property → Google Calendar ID Map ---
CALENDAR_MAP = {
    "The Glasshouse": "d3e9120b63d2b7995beab066baca2774799e455fc6dea0449b9c691272695d45@group.calendar.google.com",
    "The River Cottage": "4772fc4ce0e1eb2299339b0d2f6795acb2cc6b131c2c3ade92dde98eac5c29c2@group.calendar.google.com",
    "The Olive Lodge": "60932cd3efb70be070b1739b4907f44a633a5f4b35ebb0582fbfcc5d13a5fb6d@group.calendar.google.com",
    "The Barn Loft": "62a9c034c27d264733e4e91f8798d15b400fbd8edbd031109ff47ad1b87ce39c@group.calendar.google.com",
    "The Potter's Cabin": "8e8072d46292d0a7c0eb4e137d27f2ddd672d44b800eef410e59c985ffc85098@group.calendar.google.com",
    "The Stargazer's Pod": "6a0a5f989f29ab88ff5d3e9e2010dd32505fe871a467760b73b25fbfe84b4eb5@group.calendar.google.com",
}

PROPERTY_NAMES = list(CALENDAR_MAP.keys())


def validate():
    """Call at startup to catch missing env vars early."""
    required = {
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SERVICE_KEY": SUPABASE_SERVICE_KEY,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")
