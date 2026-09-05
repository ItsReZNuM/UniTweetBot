import os
import json
import jdatetime
from datetime import datetime
from pytz import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from telebot import TeleBot

from config import DEFAULT_TWEET_HOURS, CHANNEL_USERNAME, DATABASE_NAME, ADMIN_ID
from database import db_manager

scheduler = BackgroundScheduler(timezone=timezone('Asia/Tehran'))
separator = "\n\n✎﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏\n\n"

CHARTS_DB_PATH = "charts.db"
BACKUP_JOB_ID = "scheduled_backup_job"

INTERVAL_MAP = {
    'daily': ('روزانه (هر ۲۴ ساعت)', {'days': 1}),
    '3days': ('سه روز یکبار', {'days': 3}),
    'weekly': ('هفتگی (هر ۷ روز)', {'weeks': 1}),
    'monthly': ('ماهانه (هر ۳۰ روز)', {'days': 30}),
}

def init_scheduler(bot: TeleBot, admin_id: int):
    db_hours = db_manager.get_all_scheduler_hours()
    for hour in DEFAULT_TWEET_HOURS:
        if hour not in db_hours:
            db_manager.add_schedule_hour(hour)
            
    scheduler.add_job(
        send_scheduled_tweets,
        CronTrigger(minute=0, hour=','.join(map(str, DEFAULT_TWEET_HOURS))),
        args=[bot, admin_id],
        id="scheduled_tweet_job"
    )

    # راه‌اندازی جاب بکاپ در زمان استارت ربات طبق تنظیمات ذخیره شده
    init_backup_scheduler(bot)

    if not scheduler.running:
        scheduler.start()

# ==========================================
# ارسال خودکار توییت‌ها به کانال
# ==========================================
def send_scheduled_tweets(bot: TeleBot, admin_id: int):
    current_hour = datetime.now(timezone('Asia/Tehran')).hour
    conn = db_manager.get_db_connection()
    cursor = conn.cursor()
    
    row = cursor.execute("SELECT tweet_ids FROM scheduler WHERE hour = ?", (current_hour,)).fetchone()
    
    if not row or not row['tweet_ids']:
        bot.send_message(admin_id, f"❌ توییت‌های ساعت {current_hour}:00 خالی بود و چیزی ارسال نشد.")
        conn.close()
        return

    tweet_ids = json.loads(row['tweet_ids'])
    
    if not tweet_ids:
        bot.send_message(admin_id, f"❌ توییت‌های ساعت {current_hour}:00 خالی بود و چیزی ارسال نشد.")
        conn.close()
        return

    all_tweets = cursor.execute(f"SELECT id, user_id, text FROM tweets WHERE id IN ({','.join(['?'] * len(tweet_ids))})", tweet_ids).fetchall()

    if not all_tweets:
        bot.send_message(admin_id, f"❌ توییت‌های ساعت {current_hour}:00 خالی بود و چیزی ارسال نشد.")
        conn.close()
        return

    tweets_text = [f"{idx}) {tweet['text']}" for idx, tweet in enumerate(all_tweets, start=1)]
    final_message = "#توییت\n\n" + separator.join(tweets_text) + f"\n\n🆔 {CHANNEL_USERNAME}"

    try:
        bot.send_message(CHANNEL_USERNAME, final_message, parse_mode='HTML')
        for tweet in all_tweets:
            conn.execute("UPDATE tweets SET status = 'sent' WHERE id = ?", (tweet['id'],))
            conn.execute("UPDATE users SET success_tweets = success_tweets + 1 WHERE id = ?", (tweet['user_id'],))
        conn.execute("UPDATE scheduler SET tweet_ids = '[]' WHERE hour = ?", (current_hour,))
        bot.send_message(admin_id, f"✅ *{len(tweet_ids)}* توییت در ساعت *{current_hour}:00* در کانال ارسال شد.")
    except Exception as e:
        bot.send_message(admin_id, f"⚠️ خطای ارسال توییت به کانال: {e}")

    conn.commit()
    conn.close()

# ==========================================
# سیستم پشتیبان‌گیری (Backup)
# ==========================================
def send_backup_files(bot: TeleBot, target_chat_id: int = None) -> bool:
    """ارسال هر دو فایل دیتابیس به چت مشخص یا ادمین اصلی"""
    chat_id = target_chat_id or ADMIN_ID
    if not chat_id:
        return False

    now_str = jdatetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    success = False

    # دیتابیس اول: توییت‌ها و کاربران
    if os.path.exists(DATABASE_NAME):
        try:
            with open(DATABASE_NAME, 'rb') as f:
                bot.send_document(
                    chat_id,
                    (f"tweets_db_{now_str}.db", f),
                    caption=f"📦 <b>بکاپ دیتابیس اصلی (توییت‌ها و کاربران)</b>\n📅 زمان: <code>{now_str}</code>",
                    parse_mode='HTML'
                )
            success = True
        except Exception:
            pass

    # دیتابیس دوم: چارت‌ها
    if os.path.exists(CHARTS_DB_PATH):
        try:
            with open(CHARTS_DB_PATH, 'rb') as f:
                bot.send_document(
                    chat_id,
                    (f"charts_db_{now_str}.db", f),
                    caption=f"📊 <b>بکاپ دیتابیس چارت‌های درسی</b>\n📅 زمان: <code>{now_str}</code>",
                    parse_mode='HTML'
                )
            success = True
        except Exception:
            pass

    return success

def init_backup_scheduler(bot: TeleBot):
    """لود وضعیت زمان‌بندی از دیتابیس و زمان‌بندی جاب"""
    saved_interval = db_manager.get_setting("backup_interval", "off")
    if saved_interval in INTERVAL_MAP:
        trigger_kwargs = INTERVAL_MAP[saved_interval][1]
        scheduler.add_job(
            send_backup_files,
            IntervalTrigger(**trigger_kwargs, timezone=timezone('Asia/Tehran')),
            args=[bot, None],
            id=BACKUP_JOB_ID,
            replace_existing=True
        )

def update_backup_schedule(bot: TeleBot, interval_type: str):
    """تغییر وضعیت زمان‌بندی بکاپ و ثبت در دیتابیس"""
    if interval_type == "off":
        if scheduler.get_job(BACKUP_JOB_ID):
            scheduler.remove_job(BACKUP_JOB_ID)
        db_manager.set_setting("backup_interval", "off")
        return

    if interval_type in INTERVAL_MAP:
        trigger_kwargs = INTERVAL_MAP[interval_type][1]
        scheduler.add_job(
            send_backup_files,
            IntervalTrigger(**trigger_kwargs, timezone=timezone('Asia/Tehran')),
            args=[bot, None],
            id=BACKUP_JOB_ID,
            replace_existing=True
        )
        db_manager.set_setting("backup_interval", interval_type)

def get_backup_status():
    """دریافت گزارش کامل از وضعیت زمان‌بندی و محاسبه زمان باقی‌مانده"""
    saved_interval = db_manager.get_setting("backup_interval", "off")
    
    if saved_interval == "off" or saved_interval not in INTERVAL_MAP:
        return {
            'status_fa': "❌ غیرفعال",
            'remaining_fa': "زمان‌بندی مکرر تنظیم نشده است.",
            'next_run_fa': "تنظیم نشده"
        }

    status_name = INTERVAL_MAP[saved_interval][0]
    job = scheduler.get_job(BACKUP_JOB_ID)

    if not job or not job.next_run_time:
        return {
            'status_fa': f"✅ {status_name}",
            'remaining_fa': "در صف اجرا...",
            'next_run_fa': "به‌زودی"
        }

    now = datetime.now(timezone('Asia/Tehran'))
    diff = job.next_run_time - now
    total_seconds = int(diff.total_seconds())

    if total_seconds <= 0:
        remaining_fa = "در حال ارسال هم‌اکنون..."
    else:
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days} روز")
        if hours > 0:
            parts.append(f"{hours} ساعت")
        if minutes > 0 or not parts:
            parts.append(f"{minutes} دقیقه")

        remaining_fa = " و ".join(parts) + " دیگر"

    # تبدیل به تاریخ شمسی
    jdate = jdatetime.datetime.fromtimestamp(job.next_run_time.timestamp())
    next_run_fa = jdate.strftime("%Y/%m/%d ساعت %H:%M")

    return {
        'status_fa': f"✅ {status_name}",
        'remaining_fa': remaining_fa,
        'next_run_fa': next_run_fa
    }