import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings:
    def __init__(self):
        self.DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'ecommerce.db'}")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
        self.MAX_REFLECTION_RETRIES = int(os.getenv("MAX_REFLECTION_RETRIES", "3"))
        self.ENABLE_NEMO_GUARDRAILS = os.getenv("ENABLE_NEMO_GUARDRAILS", "true").lower() in ("true", "1", "yes")
        self.STRICT_AST_CHECK = os.getenv("STRICT_AST_CHECK", "true").lower() in ("true", "1", "yes")
        self.BASE_DIR = BASE_DIR
        self.DATA_DIR = BASE_DIR / "data"

settings = Settings()
