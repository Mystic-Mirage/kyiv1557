from configparser import ConfigParser
from typing import NamedTuple

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from universalasync import async_to_sync_wraps, get_event_loop

__all__ = ["Kyiv1557"]


class _AddressData(NamedTuple):
    id: str
    selected: bool


class Kyiv1557:
    _URL = "https://1557.kyiv.ua"
    _SELECT_ID = "address-select"
    _MESSAGE_BLOCK_CLASS = "claim-message-block"
    _MESSAGE_ITEM_CLASS = "claim-message-item"
    _DEFAULT_CONFIG_FILENAME = "1557.ini"
    _CONFIG_SECTION = "1557"

    def __init__(self):
        self._bs = None

        loop = get_event_loop()
        self._session = ClientSession(loop=loop)

        if not loop.is_running():
            from atexit import register

            register(self.__del__)

    def __del__(self):
        get_event_loop().create_task(self._session.close())

    def _url(self, path=""):
        return f"{self._URL}/{path}"

    @async_to_sync_wraps
    async def login(self, phone=None, password=None):
        url = self._url("login")

        async with self._session.post(url, data={"phone": phone}) as response:
            response.raise_for_status()

        async with self._session.post(response.url, data={"pass": password}) as response:
            response.raise_for_status()

            self._bs = BeautifulSoup(await response.text(), "html.parser")

    @async_to_sync_wraps
    async def login_from_file(self, filename=_DEFAULT_CONFIG_FILENAME):
        config = ConfigParser()
        config.read(filename)

        phone = config.get(self._CONFIG_SECTION, "phone")
        password = config.get(self._CONFIG_SECTION, "pass")

        await self.login(phone, password)

    def __addresses(self):
        select = self._bs.find("select", {"id": self._SELECT_ID})
        options = select.find_all("option")
        return {
            option.text.strip(): _AddressData(
                option["value"], option.has_attr("selected")
            )
            for option in options
        }

    @property
    def addresses(self):
        return list(self.__addresses())

    @property
    def current_address(self):
        if addresses := self.__addresses():
            return (
                next(
                    (
                        addr
                        for addr, addr_data in addresses.items()
                        if addr_data.selected
                    ),
                    None,
                )
                or tuple(addresses)[0]
            )

    @property
    def current_address_id(self):
        if addresses := self.__addresses():
            return (
                next(
                    (
                        addr_data
                        for addr, addr_data in addresses.items()
                        if addr == self.current_address
                    ),
                    None,
                )
                or tuple(addresses)[0]
            ).id

    @async_to_sync_wraps
    async def select_address(self, address):
        url = self._url()

        if addr_data := self.__addresses().get(address):
            async with self._session.post(url, data={"main-address": addr_data.id}) as response:
                response.raise_for_status()

                self._bs = BeautifulSoup(await response.text(), "html.parser")

    @property
    def messages(self):
        messages = []
        blocks = self._bs.find_all("div", {"class": self._MESSAGE_BLOCK_CLASS})
        for block in blocks:
            items = block.find_all("div", {"class": self._MESSAGE_ITEM_CLASS})
            message = "\n".join(
                [" ".join(line.strip() for line in tag.text.split()) for tag in items]
            )
            messages.append(message)
        return messages


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
