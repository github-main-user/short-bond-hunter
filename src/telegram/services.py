import requests

from src.config import settings


def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "MarkdownV2",
    }

    requests.post(url, params=params)
