import os


def _load_dotenv() -> None:
    """Local (non-Docker) convenience: load the repo-root .env without overriding real env vars."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


_load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.api_keys = [k.strip() for k in os.getenv("LLM_API_KEYS", "").split(",") if k.strip()]
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        self.allowed_origins = [
            o.strip().rstrip("/")
            for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
            if o.strip()
        ]
        self.enable_failure_simulation = _bool("ENABLE_FAILURE_SIMULATION")
        self.model = os.getenv("LLM_MODEL", "openrouter/google/gemini-3.1-flash-lite")
        self.default_system_prompt = os.getenv(
            "DEFAULT_SYSTEM_PROMPT", "You are a helpful, concise assistant."
        )
        self.request_timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    @property
    def db_path(self) -> str:
        url = self.database_url
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        return url


def get_settings() -> Settings:
    return Settings()
