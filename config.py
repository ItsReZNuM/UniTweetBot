import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
ADMIN_USER_IDS = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip().isdigit()]

ADMIN_ID = ADMIN_USER_IDS[0] if ADMIN_USER_IDS else None

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
DATABASE_NAME = os.getenv("DATABASE_NAME")
DEFAULT_TWEET_HOURS = [int(x.strip()) for x in os.getenv("DEFAULT_TWEET_HOURS", "9,12,15,18,21,0").split(',') if x.strip().isdigit()]