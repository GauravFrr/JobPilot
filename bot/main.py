import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from handlers.commands import router as commands_router
from handlers.callbacks import router as callbacks_router
from listener import start_event_listener

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bot.main")

async def main():
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not configured in settings/environment. Telegram Bot cannot start. Standing by...")
        # Keep process alive so Docker doesn't crash-loop restart
        while True:
            await asyncio.sleep(3600)
            
    logger.info("Starting JobPilot Telegram Bot...")
    
    # Initialize bot with default parse mode markdown
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    
    # Initialize dispatcher and include routers
    dp = Dispatcher()
    dp.include_router(commands_router)
    dp.include_router(callbacks_router)
    
    # Run polling and Redis pub/sub listener tasks concurrently
    listener_task = asyncio.create_task(start_event_listener(bot))
    polling_task = asyncio.create_task(dp.start_polling(bot))
    
    logger.info("Bot polling and Redis listener started successfully.")
    await asyncio.gather(polling_task, listener_task)

if __name__ == "__main__":
    asyncio.run(main())
