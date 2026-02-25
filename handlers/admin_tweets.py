import os
import tempfile
from telebot import TeleBot
from telebot.types import CallbackQuery, Message
from database import db_manager
from utils.keyboards import (
    tweet_action_markup,
    confirm_rejection_markup,
    edit_tweet_markup,
    tweet_hours_markup
)
import jdatetime
from config import ADMIN_USER_IDS

STATE = {}

TEMP_DIR = os.path.join(tempfile.gettempdir(), "tweet_bot_temp")
os.makedirs(TEMP_DIR, exist_ok=True)


# ==========================
# ساخت متن پیام ادمین با همان فرمت اولیه
# ==========================
def _format_admin_tweet_message(user_id: int, tweet_text: str) -> str:
    conn = db_manager.get_db_connection()
    row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    username = row["username"] if row and row["username"] else user_id
    return f"<b>✨ توییت جدید</b> از کاربر: @{username}\n\n{tweet_text}"


def _status_label(status: str) -> str:
    return {
        "approved": "✅ تایید شد",
        "rejected": "❌ رد شد",
        "sent": "📤 ارسال شد"
    }.get(status, "")


def _approved_time_block(approved_hour: int) -> str:
    return (
        f"\n\n"
        f"🕒 ساعت ارسال: {approved_hour}:00"
    )


def _refresh_admin_message(bot: TeleBot, admin_chat_id: int, tweet_id: int, message_id: int = None):
    """
    پیام اصلی توییت رو با وضعیت جدید آپدیت می‌کنه.
    اگر message_id داده نشه، از admin_msg_id دیتابیس استفاده می‌کنه.
    """
    conn = db_manager.get_db_connection()
    tweet = conn.execute("""
        SELECT user_id, text, status, approved_hour, admin_msg_id
        FROM tweets WHERE id = ?
    """, (tweet_id,)).fetchone()
    conn.close()

    if not tweet:
        return

    target_msg_id = message_id or tweet["admin_msg_id"]
    if not target_msg_id:
        return

    base = _format_admin_tweet_message(tweet["user_id"], tweet["text"])
    status_line = _status_label(tweet["status"])

    if status_line:
        base += f"\n\n━━━━━━━━━━\n<b>وضعیت:</b> {status_line}"

    if tweet["status"] == "approved" and tweet["approved_hour"] is not None:
        base += _approved_time_block(tweet["approved_hour"])

    try:
        bot.edit_message_text(
            base,
            admin_chat_id,
            target_msg_id,
            parse_mode="HTML",
            reply_markup=tweet_action_markup(tweet_id)
        )
    except Exception:
        pass


# ==========================
# ارسال پیام یا مدیا از ادمین به کاربر
# ==========================
def _send_media_to_user(bot: TeleBot, user_id: int, message: Message):
    try:
        bot.copy_message(user_id, message.chat.id, message.message_id)
        bot.send_message(message.chat.id, "✅ پیام با موفقیت برای کاربر ارسال شد.")
        return True
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ خطا در ارسال پیام:\n{e}")
        return False


def register_admin_handlers(bot: TeleBot, admin_id: int):

    # =====================================================
    # CALLBACK HANDLER
    # =====================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith((
        'approve_', 'reject_', 'confirm_reject_', 'cancel_reject_',
        'reply_', 'edit_', 'confirm_edit_', 'cancel_edit_',
        'hour_', 'back_to_actions_'
    )))
    def callback_admin_actions(call: CallbackQuery):

        # استخراج data و arg
        try:
            data, arg = call.data.split('_', 1)

            tweet_id = None
            if not data.startswith('hour'):
                try:
                    tweet_id = int(arg.split('_')[-1])
                except Exception:
                    pass

        except Exception:
            bot.answer_callback_query(call.id, "شناسه توییت نامعتبر است.")
            return

        # دریافت توییت از دیتابیس
        tweet = None
        if data != 'hour':
            conn = db_manager.get_db_connection()
            row = conn.execute(
                "SELECT * FROM tweets WHERE id = ?", (tweet_id,)
            ).fetchone()
            conn.close()

            if not row:
                bot.answer_callback_query(call.id, "توییت یافت نشد.")
                return

            tweet = dict(row)

        # message_id پیامی که کاربر روی دکمه‌اش کلیک کرده
        origin_msg_id = call.message.message_id

        # =========================
        # ❌ رد توییت (مرحله اول) → ادیت همون پیام با دکمه‌های تایید/لغو
        # =========================
        if data == 'reject':
            bot.edit_message_text(
                f"{_format_admin_tweet_message(tweet['user_id'], tweet['text'])}\n\n"
                "❓ آیا مطمئن هستید که می‌خواهید این توییت را رد کنید؟",
                call.message.chat.id,
                origin_msg_id,
                parse_mode='HTML',
                reply_markup=confirm_rejection_markup(tweet_id)
            )

        # =========================
        # 🔙 لغو عملیات → برگشت به پیام اصلی با دکمه‌های اصلی
        # =========================
        elif data.startswith('cancel'):
            STATE.pop(call.message.chat.id, None)
            # بازگشت به پیام اصلی بدون وضعیت
            base = _format_admin_tweet_message(tweet['user_id'], tweet['text'])
            bot.edit_message_text(
                base,
                call.message.chat.id,
                origin_msg_id,
                parse_mode='HTML',
                reply_markup=tweet_action_markup(tweet_id)
            )

        # =========================
        # ❌ تایید رد → گرفتن دلیل از ادمین (پیام جداگانه ضروریه چون input متنیه)
        # =========================
        elif data == 'confirm' and arg.startswith('reject'):
            bot.edit_message_text(
                f"{_format_admin_tweet_message(tweet['user_id'], tweet['text'])}\n\n"
                "✍️ لطفاً <b>دلیل رد</b> توییت را در پیام بعدی ارسال کنید:",
                call.message.chat.id,
                origin_msg_id,
                parse_mode='HTML'
            )
            STATE[call.message.chat.id] = {
                'mode': 'awaiting_rejection_reason',
                'tweet_id': tweet_id,
                'user_id': tweet['user_id'],
                'origin_msg_id': origin_msg_id   # ← ذخیره برای ادیت بعدی
            }

        # =========================
        # ✅ تایید توییت → ادیت همون پیام با منوی ساعت‌ها
        # =========================
        elif data == 'approve':
            hours = db_manager.get_all_scheduler_hours()
            bot.edit_message_text(
                f"{_format_admin_tweet_message(tweet['user_id'], tweet['text'])}\n\n"
                "⏰ ساعت ارسال توییت را انتخاب کنید:",
                call.message.chat.id,
                origin_msg_id,
                parse_mode='HTML',
                reply_markup=tweet_hours_markup(hours, tweet_id)
            )
            STATE[call.message.chat.id] = {
                'mode': 'awaiting_hour_selection',
                'tweet_id': tweet_id,
                'origin_msg_id': origin_msg_id   # ← ذخیره برای ادیت بعدی
            }

        # =========================
        # ⏰ انتخاب ساعت ارسال → ادیت همون پیام با وضعیت نهایی
        # =========================
        elif data == 'hour':
            try:
                hour = int(arg)
            except Exception:
                bot.answer_callback_query(call.id, "ساعت نامعتبر است.")
                return

            state = STATE.get(call.message.chat.id)
            if not state or state.get('mode') != 'awaiting_hour_selection':
                bot.answer_callback_query(call.id, "عملیات منقضی شده است.")
                return

            tweet_id = state['tweet_id']
            saved_origin_msg_id = state.get('origin_msg_id', origin_msg_id)

            # گرفتن user_id از دیتابیس
            conn = db_manager.get_db_connection()
            row = conn.execute(
                "SELECT user_id FROM tweets WHERE id = ?", (tweet_id,)
            ).fetchone()
            conn.close()

            if not row:
                bot.answer_callback_query(call.id, "توییت یافت نشد.")
                return

            user_id = row['user_id']

            # ذخیره تایید در دیتابیس
            db_manager.approve_tweet(tweet_id, hour)

            # پیام به کاربر
            try:
                bot.send_message(
                    user_id,
                    f"✅ توییت شما <b>تأیید شد</b> و در ساعت <b>{hour}:00</b> منتشر خواهد شد ⏰",
                    parse_mode='HTML'
                )
            except Exception:
                pass

            STATE.pop(call.message.chat.id, None)

            # ادیت همون پیام اصلی با وضعیت نهایی
            _refresh_admin_message(bot, call.message.chat.id, tweet_id, saved_origin_msg_id)

        # =========================
        # ↩️ پاسخ به کاربر (input متنی/مدیا → پیام جداگانه ضروریه)
        # =========================
        elif data == 'reply':
            bot.send_message(
                call.message.chat.id,
                "↩️ هر متن یا مدیایی که می‌خواهید به کاربر ارسال کنید، بفرستید:",
                parse_mode='HTML'
            )
            STATE[call.message.chat.id] = {
                'mode': 'awaiting_reply_content',
                'tweet_id': tweet_id,
                'user_id': tweet['user_id'],
                'origin_msg_id': origin_msg_id
            }

        # =========================
        # 📝 ویرایش توییت → ادیت همون پیام با راهنما
        # =========================
        elif data == 'edit':
            bot.edit_message_text(
                f"📝 <b>متن فعلی توییت</b>:\n\n<code>{tweet['text']}</code>\n\n"
                "✍️ متن جدید را در پیام بعدی ارسال کنید:",
                call.message.chat.id,
                origin_msg_id,
                parse_mode='HTML',
                reply_markup=edit_tweet_markup(tweet_id)
            )
            STATE[call.message.chat.id] = {
                'mode': 'editing',
                'tweet_id': tweet_id,
                'origin_msg_id': origin_msg_id   # ← ذخیره برای ادیت بعدی
            }

        # =========================
        # ✅ تایید ویرایش → ادیت همون پیام با متن جدید
        # =========================
        elif data == 'confirm' and arg.startswith('edit'):
            state = STATE.get(call.message.chat.id)
            if not state or 'new_text' not in state:
                bot.answer_callback_query(call.id, "ابتدا متن جدید را ارسال کنید.")
                return

            saved_origin_msg_id = state.get('origin_msg_id', origin_msg_id)
            db_manager.update_tweet_text(tweet_id, state['new_text'])
            STATE.pop(call.message.chat.id, None)

            # ادیت همون پیام اصلی با متن جدید
            _refresh_admin_message(bot, call.message.chat.id, tweet_id, saved_origin_msg_id)

        # =========================
        # 🔙 بازگشت به دکمه‌های اصلی از منوی ساعت
        # =========================
        elif data == 'back' and arg.startswith('to_actions'):
            STATE.pop(call.message.chat.id, None)
            base = _format_admin_tweet_message(tweet['user_id'], tweet['text'])
            bot.edit_message_text(
                base,
                call.message.chat.id,
                origin_msg_id,
                parse_mode='HTML',
                reply_markup=tweet_action_markup(tweet_id)
            )

        bot.answer_callback_query(call.id)

    # =====================================================
    # MESSAGE HANDLER (ورودی متنی ادمین)
    # =====================================================
    @bot.message_handler(
        func=lambda m: m.chat.id in ADMIN_USER_IDS and m.chat.id in STATE,
        content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'animation']
    )
    def handle_admin_input(message: Message):

        state = STATE.get(message.chat.id)
        if not state:
            return

        # ❌ دریافت دلیل رد
        if state['mode'] == 'awaiting_rejection_reason':
            reason = message.text
            tweet_id = state['tweet_id']
            user_id = state['user_id']
            origin_msg_id = state.get('origin_msg_id')

            db_manager.reject_tweet(tweet_id, reason)

            # پیام به کاربر
            try:
                bot.send_message(
                    user_id,
                    f"❌ متأسفانه توییت شما رد شد.\n\n<b>دلیل:</b>\n{reason}",
                    parse_mode='HTML'
                )
            except Exception:
                pass

            STATE.pop(message.chat.id, None)

            # حذف پیام راهنمای ادمین (اختیاری - جلوگیری از شلوغی)
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass

            # ادیت پیام اصلی توییت با وضعیت رد شد
            _refresh_admin_message(bot, message.chat.id, tweet_id, origin_msg_id)

        # ↩️ ارسال پیام/مدیا به کاربر
        elif state['mode'] == 'awaiting_reply_content':
            _send_media_to_user(bot, state['user_id'], message)
            STATE.pop(message.chat.id, None)

        # 📝 دریافت متن جدید برای ویرایش
        elif state['mode'] == 'editing':
            STATE[message.chat.id]['new_text'] = message.text

            # حذف پیام ادمین برای جلوگیری از شلوغی
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass

            # ادیت همون پیام اصلی توییت با راهنمای تایید
            origin_msg_id = state.get('origin_msg_id')
            tweet_id = state['tweet_id']

            conn = db_manager.get_db_connection()
            row = conn.execute("SELECT user_id, text FROM tweets WHERE id = ?", (tweet_id,)).fetchone()
            conn.close()

            if row and origin_msg_id:
                bot.edit_message_text(
                    f"📝 <b>متن جدید</b>:\n\n<code>{message.text}</code>\n\n"
                    "برای اعمال تغییر، دکمه «تایید ویرایش» را بزنید.",
                    message.chat.id,
                    origin_msg_id,
                    parse_mode='HTML',
                    reply_markup=edit_tweet_markup(tweet_id)
                )