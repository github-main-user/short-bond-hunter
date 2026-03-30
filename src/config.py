from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    TINVEST_TOKEN: str

    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    DAYS_TO_MATURITY_MAX: int
    ANNUAL_YIELD_MIN: float
    ANNUAL_YIELD_MAX: float
    BOND_SUM_MAX: float
    BOND_SUM_MAX_SINGLE: float
    BLACK_LIST_TICKERS: set[str]

    BOND_REFRESH_INTERVAL_HOURS: int = 4
    MISSED_REPAYMENTS_LOOKBACK_DAYS: int = 14

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{BASE_DIR}/stats.db"

    @property
    def BOND_REFRESH_INTERVAL_SECONDS(self) -> int:
        return self.BOND_REFRESH_INTERVAL_HOURS * 3600

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore
