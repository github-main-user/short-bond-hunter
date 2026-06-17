import logging

import aiohttp
from aiohttp import ClientError

from src.config import settings

from .exceptions import TelegramNotConfiguredError
from .utils import escape_markdown_v2_special_chars

logger = logging.getLogger(__name__)


async def _send_telegram_message(message: str):
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
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


async def notify(message: str) -> None:
    logger.info(message)
    try:
        await _send_telegram_message(message)
    except (TelegramNotConfiguredError, ClientError) as e:
        logger.error(f"Failed to send telegram message: {e}")
