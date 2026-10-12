from dataclasses import dataclass
from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    root: Path
    timezone: str
    database_path: Path
    temp_dir: Path
    news_dir: Path
    log_dir: Path
    ollama_url: str
    ollama_model: str | None
    ollama_timeout: float
    telegram_api_id: int | None
    telegram_api_hash: str | None
    telegram_target: str | None
    telegram_session: Path
    max_items: int
    lookback_hours: int
    sources_path: Path
    interests_path: Path

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        def path(key, default):
            value = Path(os.getenv(key, default))
            return value if value.is_absolute() else ROOT / value
        api_id = os.getenv("TELEGRAM_API_ID", "").strip()
        model = os.getenv("OLLAMA_MODEL", "").strip() or None
        return cls(ROOT, os.getenv("TIMEZONE", "Asia/Almaty"), path("DATABASE_PATH", "data/korgan.sqlite3"),
                   path("TEMP_DIR", "data/tmp"), path("NEWS_DIR", "news"), path("LOG_DIR", "data/logs"), os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
                   model, float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90")), int(api_id) if api_id.isdigit() else None,
                   os.getenv("TELEGRAM_API_HASH") or None, os.getenv("TELEGRAM_TARGET") or None,
                   path("TELEGRAM_SESSION", "data/telegram_session"), int(os.getenv("MAX_ITEMS", "12")),
                   int(os.getenv("FETCH_LOOKBACK_HOURS", "36")), ROOT / "config/sources.yaml", ROOT / "config/interests.yaml")

    def source_config(self):
        with self.sources_path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {"sources": []}

    def interest_config(self):
        with self.interests_path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {"categories": {}, "ranking": {}}
