import logging

import aiohttp

from src.config import settings

from .exceptions import TelegramNotConfiguredError
from .utils import escape_markdown_v2_special_chars

logger = logging.getLogger(__name__)


async def send_telegram_message(message: str):
    """
    Sends message to telegram bot.
    Raises TelegramNotConfiguredError if TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID isn't set.
    Raises exception for status.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if None in (token, chat_id):
        raise TelegramNotConfiguredError("Telegram bot token or chat ID is not set.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": escape_markdown_v2_special_chars(message),
        "parse_mode": "MarkdownV2",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as response:
            response.raise_for_status()
