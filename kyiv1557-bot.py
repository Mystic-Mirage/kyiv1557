import asyncio
import json
from asyncio import get_event_loop
from configparser import ConfigParser
from dataclasses import asdict
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from aiohttp import ClientSession

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
            self._url, data={"chat_id": chat, "text": " ".join((icon, text))}
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
        self._cache: set[Kyiv1557Message] = (
            {
                Kyiv1557Message(**args) for args in json.loads(self._path.read_text())
            } if self._path.exists()
            else set()
        )

    def diff(self, messages: set[Kyiv1557Message]):
        new_messages = messages - self._cache
        self._cache = messages
        return new_messages

    def save(self):
        self._path.write_text(
            json.dumps(
                [asdict(message) for message in self._cache],
                indent=2,
                ensure_ascii=False,
            )
        )


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
        if error_file.check(e):
            await tg.send(repr(e), admin=True)
            error_file.save()
        return

    cache_file = CacheFile(kyiv1557.current_address.id)

    for message in sorted(cache_file.diff(set(kyiv1557.messages))):
        await tg.send(message)

        cache_file.save()


if __name__ == "__main__":
    asyncio.run(main())
