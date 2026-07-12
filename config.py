"""Shared configuration for the whole pipeline."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Search terms we sweep across every collection run.
# Kept broad on purpose -- the ML clustering step (Step 4) will discover the
# *real* role categories from the text itself rather than us guessing them
# with keywords up front.
SEARCH_QUERIES = [
    "data scientist",
    "generative ai engineer",
    "machine learning engineer",
    "applied ai engineer",
    "llm engineer",
    "nlp engineer",
    "ai engineer",
]

LOCATION = "Bangalore"
