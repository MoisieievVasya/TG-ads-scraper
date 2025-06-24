import os
from dotenv import load_dotenv

load_dotenv()

DB_USER_NAME = os.getenv("DB_USER_NAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')