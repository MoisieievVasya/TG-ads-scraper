from apscheduler.schedulers.asyncio import AsyncIOScheduler
from facebook.scraper import scrape_all

def start():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scrape_all, 'interval', hours=1)
    print("Запущено автоматичний скрапінг")
    scheduler.start()