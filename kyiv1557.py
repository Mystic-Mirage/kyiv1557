from dataclasses import dataclass

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from universalasync import async_to_sync_wraps, get_event_loop

__all__ = ["Kyiv1557", "Kyiv1557Address", "Kyiv1557Message"]


@dataclass
class Kyiv1557Address:
    id: str
    name: str
    selected: bool


@dataclass
class Kyiv1557Message:
    text: str
    warn: bool


class Kyiv1557:
    _URL = "https://1557.kyiv.ua"
    _SELECT_ID = "address-select"
    _MESSAGE_BLOCK_CLASS = "claim-message-block"
    _MESSAGE_ITEM_CLASS = "claim-message-item"
    _MESSAGE_WARN_CLASS = "claim-message-green"
    _DEFAULT_CONFIG_FILENAME = "1557.ini"
    _CONFIG_SECTION = "1557"

    def __init__(self):
        self._addresses: list[Kyiv1557Address] | None = None
        self._current_address: Kyiv1557Address | None = None
        self._messages: list[Kyiv1557Message] | None = None

        loop = get_event_loop()
        self._session = ClientSession(loop=loop)

        if not loop.is_running():
            # fix warnings in sync mode
            from atexit import register

            register(self.__del__)

    def __del__(self):
        get_event_loop().create_task(self._session.close())

    def _url(self, path: str = ""):
        return f"{self._URL}/{path}"

    def _parse(self, text: str):
        self._addresses = None
        self._current_address = None
        self._messages = None

        bs = BeautifulSoup(text, "html.parser")

        if (select := bs.find("select", {"id": self._SELECT_ID})) and (
            options := select.find_all("option")
        ):
            self._addresses = []
            for option in options:
                address = Kyiv1557Address(option["value"], option.text.strip())
                self._addresses.append(address)
                if address.selected:
                    self._current_address = address
            if not self._current_address:
                self._current_address = self._addresses[0]

        if blocks := bs.find_all("div", {"class": self._MESSAGE_BLOCK_CLASS}):
            self._messages = []
            for block in blocks:
                items = block.find_all("div", {"class": self._MESSAGE_ITEM_CLASS})
                message = Kyiv1557Message(
                    "\n".join(
                        [
                            " ".join(line.strip() for line in tag.text.split())
                            for tag in items
                        ]
                    ),
                    self._MESSAGE_WARN_CLASS in block.attrs.get("class", []),
                )
                self._messages.append(message)

    @property
    def addresses(self):
        return self._addresses

    @property
    def current_address(self):
        return self._current_address

    @property
    def messages(self):
        return self._messages

    @async_to_sync_wraps
    async def login(self, phone=None, password=None):
        url = self._url("login")

        async with self._session.post(url, data={"phone": phone}) as response:
            response.raise_for_status()

        async with self._session.post(
            response.url, data={"pass": password}
        ) as response:
            response.raise_for_status()

            self._parse(await response.text())

    @async_to_sync_wraps
    async def login_from_file(self, filename=_DEFAULT_CONFIG_FILENAME):
        from configparser import ConfigParser

        config = ConfigParser()
        config.read(filename)

        phone = config.get(self._CONFIG_SECTION, "phone")
        password = config.get(self._CONFIG_SECTION, "pass")

        await self.login(phone, password)

    @async_to_sync_wraps
    async def select_address(self, address: Kyiv1557Address):
        url = self._url()

        async with self._session.post(
            url, data={"main-address": address.id}
        ) as response:
            response.raise_for_status()

            self._parse(await response.text())


if __name__ == "__main__":
    kyiv1557 = Kyiv1557()
    kyiv1557.login_from_file()

    print(kyiv1557.addresses)

    print(kyiv1557.current_address)
    print(kyiv1557.messages)

    for address in kyiv1557.addresses:
        if kyiv1557.current_address != address:
            kyiv1557.select_address(address)

            print(kyiv1557.current_address)
            print(kyiv1557.messages)
