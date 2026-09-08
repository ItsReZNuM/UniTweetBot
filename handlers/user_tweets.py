import logging
from telebot import TeleBot
from telebot.types import Message
from database import db_manager
from utils.keyboards import tweet_action_markup, main_menu_markup, is_reply_keyboard_command
from utils.rate_limit import check_rate_limit, is_message_valid
from states import S, get_state, set_state, reset

logger = logging.getLogger(__name__)

def register_user_handlers(bot: TeleBot):
    
    @bot.message_handler(commands=['start'])
    def handle_start(message: Message):
        db_manager.save_user(message.from_user)
        set_state(message.from_user.id, S.MAIN_MENU, {})

        bot.send_message(
            message.chat.id,
            "👋 سلام!\n\nلطفاً یکی از گزینه‌های زیر رو انتخاب کن 👇",
            reply_markup=main_menu_markup(message.from_user.id)
        )

    @bot.message_handler(func=lambda m: m.chat.type == "private" and m.text == "🐦 ارسال توییت")
    def choose_tweet_mode(message: Message):
        # خروج از هر حالت انتظاری قبلی و ورود به حالت توییت
        try:
            from handlers.admin_tweets import STATE as _ats
            _ats.pop(message.chat.id, None)
        except Exception:
            pass
        # اگر در حالت چارت بود، ریست شود
        if get_state(message.from_user.id) in [S.USER_WAIT_MAJOR, S.USER_SHOW_RESULTS, S.ADMIN_MENU, S.ADMIN_ADD_WAIT_MAJOR, S.ADMIN_ADD_WAIT_FILE, S.ADMIN_DEL_WAIT_QUERY]:
            reset(message.from_user.id)
        set_state(message.from_user.id, S.TWEET_MODE, {})
        bot.send_message(message.chat.id, "✍️ متن توییتت رو ارسال کن:")

    @bot.message_handler(func=lambda m: m.chat.type == "private" and m.text == "📊 دریافت چارت")
    def choose_chart_mode(message: Message):
        try:
            from handlers.admin_tweets import STATE as _ats
            _ats.pop(message.chat.id, None)
        except Exception:
            pass
        if get_state(message.from_user.id) == S.TWEET_MODE:
            reset(message.from_user.id)
        set_state(message.from_user.id, S.USER_WAIT_MAJOR, {})
        bot.send_message(message.chat.id, "🎓 لطفاً نام رشته‌ات رو وارد کن تا چارتش رو پیدا کنم:")

    @bot.message_handler(func=lambda message: (
        message.chat.type == "private"
        and message.text is not None
        and get_state(message.from_user.id) == S.TWEET_MODE
        and not is_reply_keyboard_command(message.text)
        and not message.text.startswith("/")
    ))
    def handle_new_tweet(message: Message):
        all_admins = db_manager.get_all_admins()
        if not all_admins:
            bot.send_message(message.chat.id, "⚠️ متأسفانه ادمینی برای این ربات تعریف نشده است.")
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
            
            tweet_id = db_manager.submit_tweet(message.chat.id, message.text, 0)
            
            for adm_id in all_admins:
                try:
                    sent = bot.send_message(
                        adm_id,
                        tweet_text,
                        parse_mode='HTML',
                        reply_markup=tweet_action_markup(tweet_id)
                    )
                    db_manager.save_tweet_admin_message(tweet_id, adm_id, sent.message_id)
                except Exception as ex:
                    logger.error(f"Failed to send tweet {tweet_id} to admin {adm_id}: {ex}")

            set_state(message.from_user.id, S.MAIN_MENU, {})
            bot.send_message(message.chat.id, "📨 توییت شما با موفقیت برای ادمین ارسال شد و در انتظار تایید است. از صبوری شما سپاسگزاریم.")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ متأسفانه هنگام ارسال توییت خطایی رخ داد: {e}")