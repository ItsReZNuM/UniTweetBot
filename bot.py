import telebot
import logging
from config import BOT_TOKEN, ADMIN_USER_IDS, ADMIN_ID
from database import db_manager
from handlers import user_tweets, admin_tweets, admin_panel
from utils import job_scheduler
from handlers.chart_handlers import register_chart_handlers

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set in .env file.")
    exit()

db_manager.init_db()

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

user_tweets.register_user_handlers(bot)
admin_tweets.register_admin_handlers(bot)
admin_panel.register_admin_panel_handlers(bot)
register_chart_handlers(bot)

if ADMIN_ID:
    job_scheduler.init_scheduler(bot, ADMIN_ID)

logger.info("Bot is starting...")

if __name__ == '__main__':
    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        logger.error(f"Bot failed: {e}")