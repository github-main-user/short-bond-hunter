import re


def escape_markdown_v2_special_chars(text: str) -> str:
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
