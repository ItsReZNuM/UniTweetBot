from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import db_manager
from config import ADMIN_USER_IDS, CHANNEL_USERNAME

import json
import math

STATE = {}

SEPARATOR = "\n\n✎﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏\n\n"
MAX_TG_MSG_LEN = 4096  # محدودیت پیام تلگرام

def _hours_list_markup(hours):
    """
    فقط فهرست ساعت‌ها (بدون افزودن/حذف/انتقال)
    """
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(f"ساعت {h}:00 ⏰", callback_data=f"view_hour_{h}") for h in hours]
    if buttons:
        # شکستن برای جلوگیری از زیاد بودن در یک ردیف
        for i in range(0, len(buttons), 2):
            markup.row(*buttons[i:i+2])
    return markup

def _build_preview_block(texts):
    """
    خروجی پیش‌نمایش با فرمت خواسته‌شده:
    #توییت

    <tweet 1>

    ✎﹏﹏... (separator)

    <tweet 2>

    ...

    🆔 @channel
    """
    header = "#توییت\n\n"
    body = SEPARATOR.join(texts) if texts else "موردی ثبت نشده است."
    footer = f"\n\n🆔 {CHANNEL_USERNAME}"
    return header + body + footer

def _chunk_and_send_preview(bot: TeleBot, chat_id: int, full_text: str, reply_to_message_id=None):
    """
    اگر متن از 4096 بیشتر شد، در چند پیام ارسال شود.
    """
    if len(full_text) <= MAX_TG_MSG_LEN:
        bot.edit_message_text(full_text, chat_id, reply_to_message_id, parse_mode='HTML') if reply_to_message_id else bot.send_message(chat_id, full_text, parse_mode='HTML')
        return

    # اگر ویرایش غیرممکن است (طولانی), ابتدا پیام فعلی را با توضیح کوتاه عوض می‌کنیم
    if reply_to_message_id:
        bot.edit_message_text("پیش‌نمایش طولانی است؛ در چند پیام ارسال می‌شود…", chat_id, reply_to_message_id)

    # شکستن متن به چند بخش
    parts = []
    start = 0
    while start < len(full_text):
        end = min(start + MAX_TG_MSG_LEN, len(full_text))
        # تلاش برای قطع در نزدیک‌ترین مرز SEPARATOR برای زیبایی
        if end < len(full_text):
            sep_idx = full_text.rfind(SEPARATOR.strip(), start, end)
            if sep_idx != -1 and sep_idx > start:
                end = sep_idx + len(SEPARATOR.strip())
        parts.append(full_text[start:end])
        start = end

    # ارسال قطعات
    for idx, p in enumerate(parts, 1):
        prefix = "" if idx == 1 else f"(بخش {idx} از {len(parts)})\n\n"
        bot.send_message(chat_id, prefix + p, parse_mode='HTML')

def register_admin_panel_handlers(bot: TeleBot):

    @bot.message_handler(commands=['admin'])
    def handle_admin_panel(message: Message):
        if message.chat.id not in ADMIN_USER_IDS:
            return
        bot.send_message(message.chat.id, "👨‍💻 به <b>پنل ادمین</b> خوش آمدید. یکی از عملیات زیر را انتخاب کنید:\n\n• 📊 مشاهده آمار\n• ⏰ ساعات توییت (پیش‌نمایش فقط)", parse_mode='HTML')

    @bot.message_handler(func=lambda m: m.chat.id in ADMIN_USER_IDS and m.text in ["📊 مشاهده آمار", "⏰ ساعات توییت"])
    def handle_admin_keyboard(message: Message):
        if message.text == "📊 مشاهده آمار":
            send_stats_menu(bot, message.chat.id)
        elif message.text == "⏰ ساعات توییت":
            hours = db_manager.get_all_scheduler_hours()
            if not hours:
                bot.send_message(message.chat.id, "⏰ هنوز ساعتی تعریف نشده است.")
                return
            bot.send_message(message.chat.id, "⏰ یکی از ساعت‌ها را برای <b>پیش‌نمایش</b> انتخاب کنید (فقط نمایش – بدون حذف/انتقال):", reply_markup=_hours_list_markup(hours), parse_mode='HTML')

    def _format_preview_for_hour(hour: int) -> str:
        """
        خروجی پیش‌نمایش با فرمت خواسته‌شده برای یک ساعت مشخص
        """
        conn = db_manager.get_db_connection()
        row = conn.execute("SELECT tweet_ids FROM scheduler WHERE hour = ?", (hour,)).fetchone()

        if not row or not row['tweet_ids']:
            conn.close()
            return _build_preview_block([])

        try:
            tweet_ids = json.loads(row['tweet_ids'])
        except Exception:
            tweet_ids = []

        if not tweet_ids:
            conn.close()
            return _build_preview_block([])

        # گرفتن متن‌ها به ترتیب id
        qmarks = ",".join(["?"] * len(tweet_ids))
        tweets = conn.execute(f"SELECT id, text FROM tweets WHERE id IN ({qmarks}) ORDER BY id", tweet_ids).fetchall()
        conn.close()

        texts = [t['text'] for t in tweets] if tweets else []
        return _build_preview_block(texts)

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('view_hour_', 'back_to_hours')) and call.message.chat.id in ADMIN_USER_IDS)
    def callback_tweet_hours(call: CallbackQuery):
        if call.data == "back_to_hours":
            hours = db_manager.get_all_scheduler_hours()
            bot.edit_message_text("⏰ یکی از ساعت‌ها را برای <b>پیش‌نمایش</b> انتخاب کنید (فقط نمایش – بدون حذف/انتقال):", call.message.chat.id, call.message.message_id, reply_markup=_hours_list_markup(hours), parse_mode='HTML')
            bot.answer_callback_query(call.id)
            return

        # view_hour_{h}
        try:
            _, _, hour_str = call.data.split('_', 2)
            hour = int(hour_str)
        except Exception:
            bot.answer_callback_query(call.id, "ساعت نامعتبر.")
            return

        preview_text = _format_preview_for_hour(hour)

        # مارک‌آپ با دکمهٔ بازگشت
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_hours"))

        # اگر طولانی بود، در چند پیام می‌فرستیم
        if len(preview_text) <= MAX_TG_MSG_LEN:
            bot.edit_message_text(f"⏰ <b>پیش‌نمایش ساعت {hour}:00</b>\n\n{preview_text}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
        else:
            bot.edit_message_text(f"⏰ <b>پیش‌نمایش ساعت {hour}:00</b>\n\n(متن طولانی است؛ در چند بخش ارسال می‌شود.)", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
            _chunk_and_send_preview(bot, call.message.chat.id, preview_text)

        bot.answer_callback_query(call.id)

def send_stats_menu(bot: TeleBot, chat_id, message_id=None):
    # آمار کلی
    total_users = len(db_manager.get_all_users_id())
    total_success = db_manager.get_total_success_tweets()
    total_failed = db_manager.get_total_failed_tweets()

    # آمار زمانی
    daily = db_manager.get_daily_stats()
    weekly = db_manager.get_weekly_stats()
    monthly = db_manager.get_monthly_stats()

    # کاربران برتر
    top_users = db_manager.get_top_users()

    stats_text = f"📊 <b>آمار کلی ربات</b>:\n"
    stats_text += f"👤 تعداد کل کاربران: {total_users}\n"
    stats_text += f"✅ توییت‌های موفق: {total_success}\n"
    stats_text += f"❌ توییت‌های رد شده: {total_failed}\n\n"

    stats_text += f"📆 <b>آمار زمانی:</b>\n"
    stats_text += f"📅 امروز: {daily}\n"
    stats_text += f"📈 ۷ روز گذشته: {weekly}\n"
    stats_text += f"📊 ۳۰ روز گذشته: {monthly}\n\n"

    # ارسال یا ویرایش پیام
    if message_id:
        bot.edit_message_text(stats_text, chat_id, message_id, parse_mode='HTML')
    else:
        bot.send_message(chat_id, stats_text, parse_mode='HTML')



