from configparser import ConfigParser
from hashlib import sha256
from pathlib import Path

import requests

from kyiv1557 import Kyiv1557


class Telegram:
    def __init__(self):
        config = ConfigParser()
        config.read("1557.ini")

        token = config.get("telegram", "token")
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"

        self._chat = config.get("telegram", "chat")
        self._admin = config.get("telegram", "admin")

    def send(self, message, *, admin=False):
        chat = self._admin if admin else self._chat
        response = requests.post(self._url, {"chat_id": chat, "text": message})
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


def main():
    kyiv1557 = Kyiv1557()
    tg = Telegram()

    try:
        kyiv1557.login_from_file()
        assert (current := kyiv1557.current_address_id), "Can't parse current address"
        assert (messages := kyiv1557.messages), "Can't parse messages"
    except Exception as e:
        tg.send(repr(e), admin=True)
        return

    hash_file = HashFile(current)

    if hash_file.check(messages):
        for message in kyiv1557.messages:
            tg.send(message)

        hash_file.save()


if __name__ == "__main__":
    main()
