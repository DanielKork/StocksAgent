import os
from dotenv import load_dotenv

load_dotenv()

# --- AI Engine ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")

# --- Agent Behavior ---
AGENT_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
AGENT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0.3"))
AGENT_CHAT_HISTORY_LIMIT = int(os.getenv("AGENT_CHAT_HISTORY_LIMIT", "30"))
SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", "backend/prompts/system_prompt.md")
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/stocks_agent.db")
CHAT_HISTORY_DEFAULT_LIMIT = int(os.getenv("CHAT_HISTORY_DEFAULT_LIMIT", "50"))

# --- Yahoo Finance / Cache ---
CACHE_QUOTE_TTL = int(os.getenv("CACHE_QUOTE_TTL", "60"))
CACHE_QUOTE_MAXSIZE = int(os.getenv("CACHE_QUOTE_MAXSIZE", "200"))
CACHE_INFO_TTL = int(os.getenv("CACHE_INFO_TTL", "3600"))
CACHE_INFO_MAXSIZE = int(os.getenv("CACHE_INFO_MAXSIZE", "100"))
CACHE_FINANCIALS_TTL = int(os.getenv("CACHE_FINANCIALS_TTL", "3600"))
CACHE_FINANCIALS_MAXSIZE = int(os.getenv("CACHE_FINANCIALS_MAXSIZE", "100"))
YAHOO_MAX_RETRIES = int(os.getenv("YAHOO_MAX_RETRIES", "3"))
YAHOO_RETRY_DELAY = int(os.getenv("YAHOO_RETRY_DELAY", "2"))
MAX_COMPARE_STOCKS = int(os.getenv("MAX_COMPARE_STOCKS", "10"))

# --- Flask ---
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("PORT", os.getenv("FLASK_PORT", "5001")))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
