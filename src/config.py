from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    TINVEST_TOKEN: str

    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    DAYS_TO_MATURITY_MAX: int
    ASK_MIN_ANNUAL_YIELD: float
    ASK_MAX_ANNUAL_YIELD: float
    BID_MIN_ANNUAL_YIELD: float
    BID_MAX_ANNUAL_YIELD: float
    TOTAL_MAX_SUM_PER_BOND: float
    ASK_MAX_SUM_PER_PURCHASE: float
    BID_MAX_SUM_PER_BOND: float
    BLACK_LIST_TICKERS: set[str]

    BOND_REFRESH_INTERVAL_HOURS: int = 4

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{BASE_DIR}/stats.db"

    @property
    def BOND_REFRESH_INTERVAL_SECONDS(self) -> int:
        return self.BOND_REFRESH_INTERVAL_HOURS * 3600

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore
