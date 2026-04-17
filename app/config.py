from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Woodland Chess"
    database_url: str = ""
    default_history_days: int = 90
    recent_games_limit: int = 20
    chess_com_usernames: str = ""
    chess_com_user_agent: str = "woodland-chess/0.1 (+club analytics app)"
    ingest_month_limit: int = 24
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-haiku-20240307"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def chess_usernames(self) -> list[str]:
        if not self.chess_com_usernames.strip():
            return []
        return [u.strip().lower() for u in self.chess_com_usernames.split(",") if u.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
