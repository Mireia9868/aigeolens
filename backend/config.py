"""
GEO MVP - Configuration
Multi-AI model support: DeepSeek (primary), future: ChatGPT/Gemini/Perplexity/Claude
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === DeepSeek API ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# === Future AI Models (placeholders) ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")

# === App Settings ===
FLASK_PORT = int(os.getenv("PORT", 5000))
DEBUG_MODE = os.getenv("DEBUG", "true").lower() == "true"

# === Analysis Settings ===
MAX_CONTENT_LENGTH = 8000  # chars sent to AI per request
CRAWL_TIMEOUT = 15  # seconds
AI_TEMPERATURE = 0.3  # low temperature for consistent analysis
AI_MAX_TOKENS = 4000

# === Demo Mode ===
DEMO_MODE = not DEEPSEEK_API_KEY  # auto-enable demo mode if no API key
