import asyncio
from configparser import ConfigParser
from pathlib import Path

from telethon import TelegramClient, events


async def main():
    config = ConfigParser()
    config_path = Path(__file__).with_name("1557_tg.ini")
    if not config.read(config_path):
        raise FileNotFoundError(f"Telegram configuration not found: {config_path}")

    telegram_config = config["telegram"]
    api_id = int(telegram_config["api_id"])
    api_hash = telegram_config["api_hash"]
    bot_username = telegram_config["bot"]
    address = telegram_config["address"]
    session_name = telegram_config["session"]
    request_text = telegram_config["request"]
    timeout = telegram_config.getfloat("wait_timeout_seconds")

    async with TelegramClient(session_name, api_id, api_hash) as client:
        bot = await client.get_entity(bot_username)
        queue = asyncio.Queue()

        async def on_update(event):
            await queue.put(event.message)

        client.add_event_handler(
            on_update, events.NewMessage(from_users=bot)
        )
        client.add_event_handler(
            on_update, events.MessageEdited(from_users=bot)
        )

        async def wait_message():
            return await asyncio.wait_for(queue.get(), timeout=timeout)

        async def wait_button(text):
            while True:
                button_message = await wait_message()
                if any(
                    button.text == text
                    for row in (button_message.buttons or [])
                    for button in row
                ):
                    return button_message

        request = await client.send_message(bot, request_text)

        response = await wait_button(address)
        await response.click(text=address)

        await request.delete()

        result = await wait_message()
        return result.raw_text


if __name__ == "__main__":
    print(asyncio.run(main()))
