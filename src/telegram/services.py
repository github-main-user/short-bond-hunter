import logging

import aiohttp

from src.config import settings

from .utils import escape_markdown_v2_special_chars

logger = logging.getLogger(__name__)


async def send_telegram_message(message: str):
    """
    Sends message to telegram bot.
    Doesn't send if TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID isn't set.
    Requires telegram bot token and telegram chat id to be set in settings.
    Raises exception for status.
    """
    if settings.TELEGRAM_BOT_TOKEN is None or settings.TELEGRAM_CHAT_ID is None:
        logger.warning(
            "Tried to send a telegram message, but bot token or chat ID is not set."
        )
        return

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": escape_markdown_v2_special_chars(message),
        "parse_mode": "MarkdownV2",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as response:
            response.raise_for_status()
