import asyncio
import difflib
import html
import json
from configparser import ConfigParser
from pathlib import Path

from aiohttp import ClientSession

from kyiv1557_tg import main as receive_1557_message


class Telegram:
    def __init__(self):
        config = ConfigParser()
        config.read(Path(__file__).with_name("1557.ini"))

        token = config.get("telegram", "token")
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat = config.get("telegram", "chat")
        self._session = ClientSession()

    async def send(self, message):
        response = await self._session.post(
            self._url,
            data={
                "chat_id": self._chat,
                "parse_mode": "HTML",
                "text": message,
            },
        )
        response.raise_for_status()
        result = await response.json(content_type=None)
        if not result.get("ok"):
            description = result.get("description", "unknown Telegram API error")
            raise RuntimeError(f"Telegram rejected the message: {description}")

    async def close(self):
        await self._session.close()


class CacheFile:
    def __init__(self, path):
        self._path = path
        self._old_message: str | None = (
            json.loads(path.read_text())["message"] if path.exists() else None
        )
        self._new_message: str | None = self._old_message

    def unchanged(self, message):
        return self._old_message == message

    def update(self, message):
        self._new_message = message

    def diff(self, message):
        self.update(message)
        old = (
            normalize_message(self._old_message)
            if self._old_message is not None
            else None
        )
        return diff_message(old, normalize_message(message))

    def save(self):
        self._path.write_text(
            json.dumps({"message": self._new_message}, ensure_ascii=False, indent=2)
        )


def diff_message(old, new):
    if old is None:
        return '\n\n'.join(
            html.escape(line, quote=False) for line in new.splitlines()
        )

    old_lines = old.splitlines()[::-1]
    new_lines = new.splitlines()[::-1]
    diff = difflib.SequenceMatcher(a=old_lines, b=new_lines)

    result = []
    for tag, i1, i2, j1, j2 in diff.get_opcodes():
        if tag == "equal":
            for line in new_lines[j1:j2]:
                result.append(html.escape(line, quote=False))
        elif tag == "replace":
            if len(old_lines[i1:i2]) == len(new_lines[j1:j2]) == 1 and len(old_lines[i1]) == len(new_lines[j1]):
                result.append("\n".join(
                    [
                        f"<s>{html.escape(old_lines[i1], quote=False)}</s>",
                        f"<i>{html.escape(new_lines[j1], quote=False)}</i>",
                    ]
                ))
            else:
                for line in new_lines[j1:j2]:
                    result.append(f"<b>{html.escape(line, quote=False)}</b>")
                for line in old_lines[i1:i2]:
                    result.append(f"<s>{html.escape(line, quote=False)}</s>")
        elif tag == "delete":
            for line in old_lines[i1:i2]:
                result.append(f"<s>{html.escape(line, quote=False)}</s>")
        elif tag == "insert":
            for line in new_lines[j1:j2]:
                result.append(f"<b>{html.escape(line, quote=False)}</b>")

    return '\n\n'.join(result[::-1])


def normalize_message(message) -> str:
    return message.replace("''", "'").replace("\n\n", "\n")


async def main():
    config_path = Path(__file__).with_name("1557_tg.ini")
    config = ConfigParser()
    config.read(config_path)
    cache_path = config_path.parent / config.get("proxy", "cache_file")

    cache_file = CacheFile(cache_path)
    message = await receive_1557_message()
    if not message:
        raise RuntimeError("The 1557 bot returned an empty message")

    if cache_file.unchanged(message):
        cache_file.save()
        return

    if len(message.splitlines()) > 1:
        icon = "⚠️"
        message = cache_file.diff(message)
    else:
        cache_file.update(message)
        icon = "✅"
        message = normalize_message(message)
        if "створіть заявку" in (lines := message.split(", "))[-1]:
            message = ", ".join(lines[:-1])

    telegram = Telegram()
    try:
        await telegram.send(f"{icon} {message}")
    finally:
        await telegram.close()
    cache_file.save()


if __name__ == "__main__":
    asyncio.run(main())
