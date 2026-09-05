from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import db_manager
from config import CHANNEL_USERNAME
from states import S, set_state, get_state, reset
from utils.keyboards import (
    admin_management_markup,
    admin_del_list_markup,
    confirm_admin_del_markup
)
import json

SEPARATOR = "\n\n✎﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏\n\n"
MAX_TG_MSG_LEN = 4096

def _hours_list_markup(hours):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(f"ساعت {h}:00 ⏰", callback_data=f"view_hour_{h}") for h in hours]
    if buttons:
        for i in range(0, len(buttons), 2):
            markup.row(*buttons[i:i+2])
    return markup

def _build_preview_block(texts):
    header = "#توییت\n\n"
    body = SEPARATOR.join(texts) if texts else "موردی ثبت نشده است."
    footer = f"\n\n🆔 {CHANNEL_USERNAME}"
    return header + body + footer

def _chunk_and_send_preview(bot: TeleBot, chat_id: int, full_text: str, reply_to_message_id=None):
    if len(full_text) <= MAX_TG_MSG_LEN:
        bot.edit_message_text(full_text, chat_id, reply_to_message_id, parse_mode='HTML') if reply_to_message_id else bot.send_message(chat_id, full_text, parse_mode='HTML')
        return

    if reply_to_message_id:
        bot.edit_message_text("پیش‌نمایش طولانی است؛ در چند پیام ارسال می‌شود…", chat_id, reply_to_message_id)

    parts = []
    start = 0
    while start < len(full_text):
        end = min(start + MAX_TG_MSG_LEN, len(full_text))
        if end < len(full_text):
            sep_idx = full_text.rfind(SEPARATOR.strip(), start, end)
            if sep_idx != -1 and sep_idx > start:
                end = sep_idx + len(SEPARATOR.strip())
        parts.append(full_text[start:end])
        start = end

    for idx, p in enumerate(parts, 1):
        prefix = "" if idx == 1 else f"(بخش {idx} از {len(parts)})\n\n"
        bot.send_message(chat_id, prefix + p, parse_mode='HTML')

def register_admin_panel_handlers(bot: TeleBot):

    @bot.message_handler(commands=['admin'])
    def handle_admin_panel(message: Message):
        if not db_manager.is_admin(message.chat.id):
            return
        bot.send_message(
            message.chat.id,
            "👨‍💻 به <b>پنل ادمین</b> خوش آمدید. یکی از گزینه‌های منو را انتخاب کنید.",
            parse_mode='HTML'
        )

    @bot.message_handler(func=lambda m: db_manager.is_admin(m.chat.id) and m.text in ["📊 مشاهده آمار", "⏰ ساعات توییت"])
    def handle_admin_keyboard(message: Message):
        if message.text == "📊 مشاهده آمار":
            send_stats_menu(bot, message.chat.id)
        elif message.text == "⏰ ساعات توییت":
            hours = db_manager.get_all_scheduler_hours()
            if not hours:
                bot.send_message(message.chat.id, "⏰ هنوز ساعتی تعریف نشده است.")
                return
            bot.send_message(message.chat.id, "⏰ یکی از ساعت‌ها را برای <b>پیش‌نمایش</b> انتخاب کنید:", reply_markup=_hours_list_markup(hours), parse_mode='HTML')

    def _format_preview_for_hour(hour: int) -> str:
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

        qmarks = ",".join(["?"] * len(tweet_ids))
        tweets = conn.execute(f"SELECT id, text FROM tweets WHERE id IN ({qmarks}) ORDER BY id", tweet_ids).fetchall()
        conn.close()
        texts = [t['text'] for t in tweets] if tweets else []
        return _build_preview_block(texts)

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('view_hour_', 'back_to_hours')) and db_manager.is_admin(call.message.chat.id))
    def callback_tweet_hours(call: CallbackQuery):
        if call.data == "back_to_hours":
            hours = db_manager.get_all_scheduler_hours()
            bot.edit_message_text("⏰ یکی از ساعت‌ها را برای <b>پیش‌نمایش</b> انتخاب کنید:", call.message.chat.id, call.message.message_id, reply_markup=_hours_list_markup(hours), parse_mode='HTML')
            bot.answer_callback_query(call.id)
            return

        try:
            _, _, hour_str = call.data.split('_', 2)
            hour = int(hour_str)
        except Exception:
            bot.answer_callback_query(call.id, "ساعت نامعتبر.")
            return

        preview_text = _format_preview_for_hour(hour)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_hours"))

        if len(preview_text) <= MAX_TG_MSG_LEN:
            bot.edit_message_text(f"⏰ <b>پیش‌نمایش ساعت {hour}:00</b>\n\n{preview_text}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
        else:
            bot.edit_message_text(f"⏰ <b>پیش‌نمایش ساعت {hour}:00</b>\n\n(متن طولانی است؛ در چند بخش ارسال می‌شود.)", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
            _chunk_and_send_preview(bot, call.message.chat.id, preview_text)
        bot.answer_callback_query(call.id)

    # =====================================================
    # هندلرهای مدیریت ادمین‌ها (فقط برای سوپرادمین)
    # =====================================================
    @bot.message_handler(func=lambda m: db_manager.is_superadmin(m.chat.id) and m.text == "👥 مدیریت ادمین‌ها")
    @bot.message_handler(commands=['admins'])
    def handle_admins_menu(message: Message):
        if not db_manager.is_superadmin(message.chat.id):
            return
        bot.send_message(
            message.chat.id,
            "👑 <b>بخش مدیریت ادمین‌های ربات</b>\n\nیکی از گزینه‌های زیر را انتخاب کنید:",
            parse_mode='HTML',
            reply_markup=admin_management_markup()
        )

    @bot.callback_query_handler(func=lambda call: call.data == "admin_mgmt_list" and db_manager.is_superadmin(call.message.chat.id))
    def cb_admin_list(call: CallbackQuery):
        superadmins = [str(x) for x in db_manager.ADMIN_USER_IDS]
        db_admins = db_manager.get_db_admins()

        text = "📋 <b>فهرست ادمین‌های ربات:</b>\n\n"
        text += "👑 <b>مدیران ارشد (از فایل env):</b>\n"
        for sa in superadmins:
            text += f"• <code>{sa}</code>\n"

        text += "\n👨‍💻 <b>ادمین‌های اضافه شده:</b>\n"
        if not db_admins:
            text += "<i>هیچ ادمین ثانویه‌ای ثبت نشده است.</i>\n"
        else:
            for da in db_admins:
                username_part = f" (@{da['username']})" if da.get('username') else ""
                name_part = f" - {da['first_name']}" if da.get('first_name') else ""
                text += f"• <code>{da['id']}</code>{username_part}{name_part}\n"

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_mgmt_back"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=markup)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_mgmt_add" and db_manager.is_superadmin(call.message.chat.id))
    def cb_admin_add(call: CallbackQuery):
        set_state(call.message.chat.id, S.ADMIN_WAIT_ADD_ID, {})
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ انصراف", callback_data="admin_mgmt_back"))
        bot.edit_message_text(
            "➕ <b>افزودن ادمین جدید:</b>\n\n"
            "لطفاً <b>آیدی عددی</b> کاربر را بفرستید، یا پیامی از او را به اینجا <b>فوروارد</b> کنید:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_mgmt_del" and db_manager.is_superadmin(call.message.chat.id))
    def cb_admin_del(call: CallbackQuery):
        db_admins = db_manager.get_db_admins()
        if not db_admins:
            bot.answer_callback_query(call.id, "هیچ ادمین ثانویه‌ای برای حذف وجود ندارد.", show_alert=True)
            return

        bot.edit_message_text(
            "🗑️ <b>حذف ادمین:</b>\n\nروی ادمینی که می‌خواهید حذف شود کلیک کنید:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=admin_del_list_markup(db_admins)
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_del_pick_") and db_manager.is_superadmin(call.message.chat.id))
    def cb_admin_del_pick(call: CallbackQuery):
        target_id = int(call.data.split("_")[-1])
        bot.edit_message_text(
            f"⚠️ آیا مطمئن هستید که می‌خواهید کاربر <code>{target_id}</code> از ادمینی حذف شود؟",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=confirm_admin_del_markup(target_id)
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_del_yes_") and db_manager.is_superadmin(call.message.chat.id))
    def cb_admin_del_yes(call: CallbackQuery):
        target_id = int(call.data.split("_")[-1])
        db_manager.remove_admin(target_id)
        try:
            bot.send_message(target_id, "⚠️ دسترسی ادمین شما لغو شد.")
        except Exception:
            pass

        bot.edit_message_text(
            f"✅ ادمین <code>{target_id}</code> با موفقیت حذف شد.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=admin_management_markup()
        )
        bot.answer_callback_query(call.id, "ادمین حذف شد.")

    @bot.callback_query_handler(func=lambda call: (call.data in ["admin_del_no", "admin_mgmt_back"]) and db_manager.is_superadmin(call.message.chat.id))
    def cb_admin_mgmt_back(call: CallbackQuery):
        reset(call.message.chat.id)
        bot.edit_message_text(
            "👑 <b>بخش مدیریت ادمین‌های ربات</b>\n\nیکی از گزینه‌های زیر را انتخاب کنید:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=admin_management_markup()
        )
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: db_manager.is_superadmin(m.chat.id) and get_state(m.chat.id) == S.ADMIN_WAIT_ADD_ID, content_types=['text'])
    def handle_add_admin_input(message: Message):
        target_id = None
        username = None
        first_name = None

        if message.forward_from:
            target_id = message.forward_from.id
            username = message.forward_from.username
            first_name = message.forward_from.first_name
        elif message.text.strip().isdigit():
            target_id = int(message.text.strip())
            user_row = db_manager.get_user_by_id(target_id)
            if user_row:
                username = user_row.get('username')
                first_name = user_row.get('first_name')
        else:
            bot.send_message(message.chat.id, "❌ ورودی نامعتبر است. لطفاً یک عدد (آیدی کاربری) بفرستید یا پیامی از کاربر را فوروارد کنید.")
            return

        if db_manager.is_superadmin(target_id):
            bot.send_message(message.chat.id, "⚠️ این کاربر مدیر ارشد ربات است و نیازی به افزودن ندارد.")
            reset(message.chat.id)
            return

        if db_manager.is_admin(target_id):
            bot.send_message(message.chat.id, "⚠️ این کاربر در حال حاضر ادمین است.")
            reset(message.chat.id)
            return

        ok = db_manager.add_admin(target_id, added_by=message.chat.id, username=username, first_name=first_name)
        reset(message.chat.id)
        if ok:
            bot.send_message(
                message.chat.id,
                f"✅ کاربر <code>{target_id}</code> با موفقیت به عنوان ادمین اضافه شد.",
                parse_mode='HTML',
                reply_markup=admin_management_markup()
            )
            try:
                bot.send_message(
                    target_id,
                    "🎉 <b>تبریک!</b> شما به عنوان ادمین ربات انتخاب شدید.\nبا ارسال دستور /start کیبورد مدیریت برای شما فعال خواهد شد.",
                    parse_mode='HTML'
                )
            except Exception:
                pass
        else:
            bot.send_message(message.chat.id, "❌ مشکلی در افزودن ادمین رخ داد.")

def send_stats_menu(bot: TeleBot, chat_id, message_id=None):
    total_users = len(db_manager.get_all_users_id())
    total_success = db_manager.get_total_success_tweets()
    total_failed = db_manager.get_total_failed_tweets()

    daily = db_manager.get_daily_stats()
    weekly = db_manager.get_weekly_stats()
    monthly = db_manager.get_monthly_stats()

    stats_text = f"📊 <b>آمار کلی ربات</b>:\n"
    stats_text += f"👤 تعداد کل کاربران: {total_users}\n"
    stats_text += f"✅ توییت‌های موفق: {total_success}\n"
    stats_text += f"❌ توییت‌های رد شده: {total_failed}\n\n"

    stats_text += f"📆 <b>آمار زمانی:</b>\n"
    stats_text += f"📅 امروز: {daily}\n"
    stats_text += f"📈 ۷ روز گذشته: {weekly}\n"
    stats_text += f"📊 ۳۰ روز گذشته: {monthly}\n\n"

    if message_id:
        bot.edit_message_text(stats_text, chat_id, message_id, parse_mode='HTML')
    else:
        bot.send_message(chat_id, stats_text, parse_mode='HTML')