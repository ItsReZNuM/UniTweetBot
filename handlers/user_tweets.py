from telebot import TeleBot
from telebot.types import Message
from telebot import util
from database import db_manager
from utils.keyboards import tweet_action_markup
from utils.rate_limit import check_rate_limit, is_message_valid
from config import ADMIN_USER_IDS

def register_user_handlers(bot: TeleBot, admin_id: int):
    
    @bot.message_handler(commands=['start'])
    def handle_start(message: Message):
        db_manager.save_user(message.from_user)
        
        if message.chat.id in ADMIN_USER_IDS:
            from utils.keyboards import admin_panel_markup
            bot.send_message(message.chat.id, "👋 سلام ادمین! به ربات خوش اومدی 🙌", reply_markup=admin_panel_markup())
        else:
            bot.send_message(message.chat.id, "👋 سلام! اینجا می‌تونید توییت‌های دانشگاهی خودتون رو به صورت <b>ناشناس</b> برای ما ارسال کنید. پیام شما پس از بررسی توسط ادمین در کانال منتشر میشه.")

        
    @bot.message_handler(func=lambda message: message.chat.type == 'private' and message.text is not None and message.chat.id not in ADMIN_USER_IDS)
    def handle_new_tweet(message: Message):
        if admin_id is None:
            bot.send_message(message.chat.id, "⚠️ متأسفانه ادمین برای این ربات تعریف نشده است.")
            return

        if not is_message_valid(message):
            return
            
        is_allowed, error_msg = check_rate_limit(message.chat.id)
        if not is_allowed:
            bot.send_message(message.chat.id, error_msg)
            return

        db_manager.save_user(message.from_user)
        
        try:
            tweet_text = f"<b>✨ توییت جدید</b> از کاربر: @{message.from_user.username or message.from_user.id}\n\n{message.text}"
            sent_to_admin = bot.send_message(admin_id, tweet_text, parse_mode='HTML')
            
            tweet_id = db_manager.submit_tweet(message.chat.id, message.text, sent_to_admin.message_id)
            
            bot.edit_message_reply_markup(admin_id, sent_to_admin.message_id, reply_markup=tweet_action_markup(tweet_id))
            
            bot.send_message(message.chat.id, "📨 توییت شما با موفقیت برای ادمین ارسال شد و در انتظار تایید است. از صبوری شما سپاسگزاریم.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ متأسفانه هنگام ارسال توییت خطایی رخ داد: {e}")