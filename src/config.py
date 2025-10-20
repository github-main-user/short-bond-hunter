from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TINVEST_TOKEN: str

    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str

    FEE_PERCENT: float
    DAYS_TO_MATURITY_MAX: int
    ANNUAL_YIELD_MIN: float
    ANNUAL_YIELD_MAX: float
    BOND_SUM_MAX: float
    BOND_SUM_MAX_SINGLE: float

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore
