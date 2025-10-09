from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from pytz import timezone
from config import DEFAULT_TWEET_HOURS, CHANNEL_USERNAME
from database import db_manager
from telebot import TeleBot
import json

scheduler = BackgroundScheduler(timezone=timezone('Asia/Tehran'))
separator = "\n\n✎﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏\n\n"

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
    scheduler.start()

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

    tweets_text = []
    all_tweets = cursor.execute(f"SELECT id, user_id, text FROM tweets WHERE id IN ({','.join(['?'] * len(tweet_ids))})", tweet_ids).fetchall()

    if not all_tweets:
        bot.send_message(admin_id, f"❌ توییت‌های ساعت {current_hour}:00 خالی بود و چیزی ارسال نشد.")
        conn.close()
        return

    tweets_text = [f"{idx}) {tweet['text']}" for idx, tweet in enumerate(all_tweets, start=1)]

    final_message = "#توییت\n\n" + separator.join(tweets_text) + f"\n\n🆔 {CHANNEL_USERNAME}"

    try:
        # ارسال توییت‌ها به کانال
        bot.send_message(CHANNEL_USERNAME, final_message, parse_mode='HTML')
        
        # به‌روزرسانی وضعیت توییت‌ها و آمار
        for tweet in all_tweets:
            conn.execute("UPDATE tweets SET status = 'sent' WHERE id = ?", (tweet['id'],))
            conn.execute("UPDATE users SET success_tweets = success_tweets + 1 WHERE id = ?", (tweet['user_id'],))
        
        # خالی کردن لیست توییت‌های این ساعت
        conn.execute("UPDATE scheduler SET tweet_ids = '[]' WHERE hour = ?", (current_hour,))
        
        bot.send_message(admin_id, f"✅ *{len(tweet_ids)}* توییت در ساعت *{current_hour}:00* در کانال ارسال شد.")
        
    except Exception as e:
        bot.send_message(admin_id, f"⚠️ خطای ارسال توییت به کانال: {e}")

    conn.commit()
    conn.close()