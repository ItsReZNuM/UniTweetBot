from telebot import TeleBot
from telebot.types import Message
from telebot import util
from database import db_manager
from utils.keyboards import tweet_action_markup
from utils.rate_limit import check_rate_limit, is_message_valid
from config import ADMIN_USER_IDS
from states import S, get_state, set_state
from utils.keyboards import main_menu_markup

def register_user_handlers(bot: TeleBot, admin_id: int):
    
    @bot.message_handler(commands=['start'])
    def handle_start(message: Message):
        db_manager.save_user(message.from_user)

        is_admin = message.chat.id in ADMIN_USER_IDS

        # کاربر را به منوی اصلی ببر
        set_state(message.from_user.id, S.MAIN_MENU, {})

        bot.send_message(
            message.chat.id,
            "👋 سلام!\n\nلطفاً یکی از گزینه‌های زیر رو انتخاب کن 👇",
            reply_markup=main_menu_markup(is_admin=is_admin)
        )

    @bot.message_handler(func=lambda m: m.chat.type=="private" and m.text=="🐦 ارسال توییت" and m.chat.id not in ADMIN_USER_IDS)
    def choose_tweet_mode(message: Message):
        set_state(message.from_user.id, S.TWEET_MODE, {})
        bot.send_message(message.chat.id, "✍️ متن توییتت رو ارسال کن:")


    @bot.message_handler(func=lambda m: m.chat.type == "private" and m.text == "📊 دریافت چارت")
    def choose_chart_mode(message: Message):
        set_state(message.from_user.id, S.USER_WAIT_MAJOR, {})
        bot.send_message(message.chat.id, "🎓 لطفاً نام رشته‌ات رو وارد کن تا چارتش رو پیدا کنم:")

            
    @bot.message_handler(func=lambda message: (message.chat.type == "private" and message.text is not None and  message.chat.id not in ADMIN_USER_IDS and get_state(message.from_user.id) == S.TWEET_MODE))

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