from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    TINVEST_TOKEN: str

    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    LOG_LEVEL: str = "INFO"

    DAYS_TO_MATURITY_MAX: int
    ASK_MIN_ANNUAL_YIELD: float
    ASK_MAX_ANNUAL_YIELD: float
    BID_MIN_ANNUAL_YIELD: float
    BID_MAX_ANNUAL_YIELD: float
    TOTAL_MAX_SUM_PER_BOND: float
    ASK_MAX_SUM_PER_PURCHASE: float
    BID_MAX_SUM_PER_BOND: float
    ASK_COOLDOWN_SECONDS: float = 300
    BID_COOLDOWN_SECONDS: float = 300
    BLACK_LISTED_TICKERS: set[str]

    BOND_REFRESH_INTERVAL_HOURS: int = 4
    BID_REGISTRY_SYNC_INTERVAL_SECONDS: int = 1800

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def BOND_REFRESH_INTERVAL_SECONDS(self) -> int:
        return self.BOND_REFRESH_INTERVAL_HOURS * 3600

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore
