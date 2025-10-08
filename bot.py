import telebot
import logging
from config import BOT_TOKEN, ADMIN_USER_IDS, ADMIN_ID
from database import db_manager
from handlers import user_tweets, admin_tweets, admin_panel
from utils import job_scheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set in .env file.")
    exit()

if ADMIN_ID is None:
    # این هشدار در حالتی که ADMIN_USER_IDS در .env خالی باشد ظاهر می‌شود.
    logger.warning("ADMIN_USER_IDS is not set correctly in .env file. Admin features will be disabled.")

# مطمئن می‌شویم که دیتابیس قبل از رجیستر شدن هندلرها آماده است.
db_manager.init_db()

# تنظیم parse_mode پیش‌فرض بر روی HTML
# این کار از خطاهای تجزیه Markdown (مثل خطای 400 قبلی) در بسیاری از موارد جلوگیری می‌کند.
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ثبت هندلرها: فقط در صورتی که ادمین به درستی تنظیم شده باشد.
if ADMIN_USER_IDS:
    # 1. رجیستر کردن هندلرهای کاربر و ارسال ADMIN_ID
    user_tweets.register_user_handlers(bot, ADMIN_ID)
    
    # 2. رجیستر کردن هندلرهای ادمین و ارسال ADMIN_ID (رفع خطای TypeError)
    admin_tweets.register_admin_handlers(bot, ADMIN_ID)
    
    # 3. رجیستر کردن پنل ادمین (این تابع نیازی به ADMIN_ID به عنوان آرگومان ندارد)
    admin_panel.register_admin_panel_handlers(bot)
    
    # 4. مقداردهی اولیه زمان‌بندی و ارسال ADMIN_ID برای گزارش‌های زمان‌بندی
    job_scheduler.init_scheduler(bot, ADMIN_ID)

logger.info("Bot is starting...")

if __name__ == '__main__':
    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        logger.error(f"Bot failed: {e}")