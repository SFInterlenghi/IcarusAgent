from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    PRIMARY_MODEL: str = os.getenv(
        "PRIMARY_MODEL",
        "openrouter/meta-llama/llama-3-70b-instruct:free",
    )
    FALLBACK_MODEL: str = os.getenv("FALLBACK_MODEL", "gemini/gemini-flash-latest")
    DB_PATH: Path = Path(os.getenv("DB_PATH", "data/icarus_kb.sqlite"))
    PDF_PATH: Path = Path(os.getenv("PDF_PATH", "AspenIcarusV15_Ref.pdf"))


settings = Settings()
