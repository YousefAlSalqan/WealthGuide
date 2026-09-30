import os
from pathlib import Path

from dotenv import load_dotenv, dotenv_values

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def get_api_key() -> str:
    if os.getenv("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"].strip()
    key_file = Path(os.getenv("OPENAI_API_KEY_FILE", str(ROOT / ".env.txt")))
    if not key_file.is_absolute():
        key_file = ROOT / key_file
    if not key_file.is_file():
        return ""
    content = key_file.read_text(encoding="utf-8-sig").strip()
    return content if content.startswith("sk-") and "\n" not in content else (dotenv_values(key_file).get("OPENAI_API_KEY") or "")


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://wealthguide:wealthguide-local-only@localhost:5433/wealthguide")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
AI_ENABLED = os.getenv("AI_ENABLED", "true").lower() == "true"
