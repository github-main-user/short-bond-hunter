from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TINVEST_TOKEN: str

    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    FEE_PERCENT: float
    DAYS_TO_MATURITY_MAX: int
    ANNUAL_YIELD_MIN: float
    ANNUAL_YIELD_MAX: float
    BOND_SUM_MAX: float
    BOND_SUM_MAX_SINGLE: float
    BLACK_LIST_TICKERS: set[str]

    BOND_REFRESH_INTERVAL_HOURS: int = 3

    @computed_field
    @property
    def BOND_REFRESH_INTERVAL_SECONDS(self) -> int:
        return self.BOND_REFRESH_INTERVAL_HOURS * 3600

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore
