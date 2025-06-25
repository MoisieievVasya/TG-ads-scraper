import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from fake_server import start_fake_server
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from cleanup_service import run_clean_up
import shared_state
from bot.handlers import router
from config import BOT_TOKEN
from database.models import Base, engine
from scheduler.updater import start as start_scheduler


async def main():
    shared_state.is_scraping = False
    logger.info("ℹ️ Статус скрапінгу скинуто на 'вільно'.")
    logger.info("Ensuring database tables exist...")
    Base.metadata.create_all(engine)
    logger.info("Database tables checked/created.")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    start_scheduler()
    logger.info('✅ Бот запущено, очікую повідомлення...')

    asyncio.create_task(run_clean_up())
    await start_fake_server()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())