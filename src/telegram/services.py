import re

import aiohttp

from src.config import settings


def _escape_markdown_v2_special_chars(text: str) -> str:
    """
    Escapes special characters for Telegram's MarkdownV2 parse mode,
    ignoring characters inside code blocks (`...`).
    """
    escape_chars = r"([_*\[\]()~>#\+\-=|{}.!])"
    parts = text.split("`")

    processed_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            processed_parts.append(re.sub(escape_chars, r"\\\1", part))
        else:
            processed_parts.append(part)

    return "`".join(processed_parts)


async def send_telegram_message(message: str):
    """
    Sends message to telegram bot.
    Requires telegram bot token and telegram chat id to be set in settings.
    Raises exception for status.
    """
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": _escape_markdown_v2_special_chars(message),
        "parse_mode": "MarkdownV2",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as response:
            response.raise_for_status()
