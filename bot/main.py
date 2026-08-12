import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot.main")

async def main():
    logger.info("Telegram Bot skeleton started. Waiting for messages...")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
