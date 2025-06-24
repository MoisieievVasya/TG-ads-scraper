import asyncio
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Bot, Dispatcher

import shared_state
from bot.handlers import router
from config import BOT_TOKEN
from scheduler.updater import start as start_scheduler

# --- ЗМІНІТЬ ЦЕЙ РЯДОК ІМПОРТУ ---
from database.models import Base, engine # Правильний шлях для вашої структури
# --- КІНЕЦЬ ЗМІНИ ---

async def main():
    # --- Цей блок залишається без змін ---
    # Гарантовано скидаємо замок при кожному запуску
    shared_state.is_scraping = False
    print("ℹ️ Статус скрапінгу скинуто на 'вільно'.")
    print("Ensuring database tables exist...")
    Base.metadata.create_all(engine) # Цей рядок створить таблиці, якщо їх немає
    print("Database tables checked/created.")
    # --- Кінець блоку ---

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    start_scheduler()
    print('✅ Бот запущено, очікую повідомлення...')
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())