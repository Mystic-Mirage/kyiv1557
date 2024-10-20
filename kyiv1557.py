from configparser import ConfigParser
from typing import NamedTuple

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from universalasync import async_to_sync_wraps, get_event_loop

__all__ = ["Kyiv1557"]


class _AddressData(NamedTuple):
    id: str
    name: str


class Kyiv1557:
    _URL = "https://1557.kyiv.ua"
    _SELECT_ID = "address-select"
    _MESSAGE_BLOCK_CLASS = "claim-message-block"
    _MESSAGE_ITEM_CLASS = "claim-message-item"
    _DEFAULT_CONFIG_FILENAME = "1557.ini"
    _CONFIG_SECTION = "1557"

    def __init__(self):
        self._addresses: dict[str, _AddressData] | None = None
        self._current_address: _AddressData | None = None
        self._messages: list[str] | None = None

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
            self._addresses = {}
            for option in options:
                name = option.text.strip()
                address_data = _AddressData(option["value"], name)
                self._addresses[name] = address_data
                if option.has_attr("selected"):
                    self._current_address = address_data
            if not self._current_address:
                self._current_address = next(iter(self._addresses.values()))

        if blocks := bs.find_all("div", {"class": self._MESSAGE_BLOCK_CLASS}):
            self._messages = []
            for block in blocks:
                items = block.find_all("div", {"class": self._MESSAGE_ITEM_CLASS})
                message = "\n".join(
                    [
                        " ".join(line.strip() for line in tag.text.split())
                        for tag in items
                    ]
                )
                self._messages.append(message)

    @property
    def addresses(self):
        return list(self._addresses)

    @property
    def current_address(self):
        return self._current_address.name

    @property
    def current_address_id(self):
        return self._current_address.id

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
        config = ConfigParser()
        config.read(filename)

        phone = config.get(self._CONFIG_SECTION, "phone")
        password = config.get(self._CONFIG_SECTION, "pass")

        await self.login(phone, password)

    @async_to_sync_wraps
    async def select_address(self, address):
        url = self._url()

        if self._addresses:
            if addr_data := self._addresses.get(address):
                async with self._session.post(
                    url, data={"main-address": addr_data.id}
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
