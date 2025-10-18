from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TINVEST_TOKEN: str

    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()  # type: ignore
