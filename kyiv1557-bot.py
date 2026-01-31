import asyncio
import difflib
import json
from asyncio import get_event_loop
from configparser import ConfigParser
from dataclasses import asdict
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from aiohttp import ClientError, ClientSession

from kyiv1557 import Kyiv1557, Kyiv1557Message


class Telegram:
    def __init__(self):
        config = ConfigParser()
        config.read("1557.ini")

        token = config.get("telegram", "token")
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"

        self._chat = config.get("telegram", "chat")
        self._admin = config.get("telegram", "admin")

        self._session = ClientSession()

    def __del__(self):
        get_event_loop().create_task(self._session.close())

    async def send(self, message, *, admin=False):
        icon = ""
        if isinstance(message, Kyiv1557Message):
            text = f"{message.title}\n\n{message.text}"
            icon = "⚠️" if message.warn else "✅"
        else:
            text = message
        if admin:
            icon = "⛔"
        chat = self._admin if admin else self._chat
        response = await self._session.post(
            self._url, data={"chat_id": chat, "parse_mode": "HTML", "text": " ".join((icon, text))}
        )
        response.raise_for_status()


class HashFile:
    def __init__(self, name, *, mtime=False):
        self._path = Path(f"{name}.dat")
        self._mtime = mtime
        self._old_hash = self._path.read_bytes() if self._path.exists() else b""
        self._new_hash = b""

    def check(self, data) -> bool:
        if self._mtime:
            if not self._path.exists():
                return True
            mtime = datetime.fromtimestamp(self._path.stat().st_mtime)
            if datetime.now() - mtime > timedelta(hours=1):
                return True
        self._new_hash = sha256(repr(data).encode()).digest()
        return self._old_hash != self._new_hash

    def save(self):
        self._path.write_bytes(self._new_hash)


class CacheFile:
    def __init__(self, name):
        self._path = Path(f"{name}_cache.json")
        self._cache: list[Kyiv1557Message] = (
            [
                Kyiv1557Message(**args) for args in json.loads(self._path.read_text())
            ] if self._path.exists()
            else []
        )

    def diff(self, messages: list[Kyiv1557Message]) -> list[tuple[Kyiv1557Message, Kyiv1557Message]]:
        result = []
        for old, new in zip(self._cache, messages):
            if old != new:
                result.append((old, new))
        self._cache = messages
        return result

    def save(self):
        self._path.write_text(
            json.dumps(
                [asdict(message) for message in self._cache],
                indent=2,
                ensure_ascii=False,
            )
        )


def diff_message(old: Kyiv1557Message, new: Kyiv1557Message) -> Kyiv1557Message:
    if old.warn != new.warn:
        return new

    old_lines = old.text.splitlines()
    new_lines = new.text.splitlines()

    diff = difflib.SequenceMatcher(a=old_lines, b=new_lines)

    result = []
    for tag, i1, i2, j1, j2 in diff.get_opcodes():
        if tag == "equal":
            for line in new_lines[j1:j2]:
                result.append(line)
        elif tag == "replace":
            for line in old_lines[i1:i2]:
                result.append(f"<s>{line}</s>")
            for line in new_lines[j1:j2]:
                result.append(f"<i>{line}</i>")
        elif tag == "delete":
            for line in old_lines[i1:i2]:
                result.append(f"<s>{line}</s>")
        elif tag == "insert":
            for line in new_lines[j1:j2]:
                result.append(f"<b>{line}</b>")

    return Kyiv1557Message(title=new.title, text="\n".join(result), warn=new.warn)


async def main():
    kyiv1557 = Kyiv1557()
    tg = Telegram()

    try:
        if not await kyiv1557.load_session():
            await kyiv1557.login_from_file()
            kyiv1557.save_session()
        assert kyiv1557.current_address, "Can't parse current address"
        assert kyiv1557.messages, "Can't parse messages"
    except Exception as e:
        error_file = HashFile("error", mtime=True)
        exception = str(e) if isinstance(e, ClientError) else e
        if error_file.check(exception):
            await tg.send(repr(e), admin=True)
        error_file.save()
        return

    cache_file = CacheFile(kyiv1557.current_address.id)

    for old, new in cache_file.diff(kyiv1557.messages):
        message = diff_message(old, new)
        await tg.send(message)

        cache_file.save()


if __name__ == "__main__":
    asyncio.run(main())
