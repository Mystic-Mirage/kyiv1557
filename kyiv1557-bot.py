import asyncio
from asyncio import get_event_loop
from configparser import ConfigParser
from hashlib import sha256
from pathlib import Path

from aiohttp import ClientSession

from kyiv1557 import Kyiv1557


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
        chat = self._admin if admin else self._chat
        response = await self._session.post(
            self._url, data={"chat_id": chat, "text": message}
        )
        response.raise_for_status()


class HashFile:
    def __init__(self, name):
        self._path = Path(f"{name}.dat")
        self._old_hash = self._path.read_bytes() if self._path.exists() else b""
        self._new_hash = b""

    def check(self, data):
        self._new_hash = sha256(repr(data).encode()).digest()
        return self._old_hash != self._new_hash

    def save(self):
        self._path.write_bytes(self._new_hash)


async def main():
    kyiv1557 = Kyiv1557()
    tg = Telegram()

    try:
        await kyiv1557.login_from_file()
        assert kyiv1557.current_address, "Can't parse current address"
        assert kyiv1557.messages, "Can't parse messages"
    except Exception as e:
        await tg.send(repr(e), admin=True)
        return

    hash_file = HashFile(kyiv1557.current_address.id)

    if hash_file.check(kyiv1557.messages):
        for message in kyiv1557.messages:
            await tg.send(message)

        hash_file.save()


if __name__ == "__main__":
    asyncio.run(main())
