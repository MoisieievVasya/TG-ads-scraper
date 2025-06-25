import os
from dotenv import load_dotenv

load_dotenv()

POSTGRESQl_LINK = os.getenv("POSTGRESQl_LINK")
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')