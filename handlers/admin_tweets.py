import os
import tempfile
from telebot import TeleBot
from telebot.types import CallbackQuery, Message
from database import db_manager
from utils.keyboards import (
    tweet_action_markup,
    tweet_done_markup,
    confirm_rejection_markup,
    edit_tweet_markup,
    tweet_hours_markup
)

STATE = {}

TEMP_DIR = os.path.join(tempfile.gettempdir(), "tweet_bot_temp")
os.makedirs(TEMP_DIR, exist_ok=True)

def _format_admin_tweet_message(user_id: int, tweet_text: str) -> str:
    conn = db_manager.get_db_connection()
    row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    username = row["username"] if row and row["username"] else user_id
    return f"<b>✨ توییت جدید</b> از کاربر: @{username}\n\n{tweet_text}"

def _hide_tweet_from_other_admins(bot: TeleBot, tweet_id: int, current_admin_id: int):
    other_msgs = db_manager.get_other_admin_messages(tweet_id, current_admin_id)
    for item in other_msgs:
        try:
            bot.delete_message(item['admin_id'], item['message_id'])
        except Exception:
            try:
                bot.edit_message_text(
                    "⚠️ <i>این توییت توسط ادمین دیگری بررسی و تعیین تکلیف شد.</i>",
                    item['admin_id'],
                    item['message_id'],
                    parse_mode="HTML",
                    reply_markup=None
                )
            except Exception:
                pass

def _refresh_admin_message(bot: TeleBot, admin_chat_id: int, tweet_id: int, message_id: int = None):
    conn = db_manager.get_db_connection()
    tweet = conn.execute("""
        SELECT user_id, text, status, approved_hour, admin_msg_id, rejection_reason
        FROM tweets WHERE id = ?
    """, (tweet_id,)).fetchone()
    conn.close()

    if not tweet:
        return

    target_msg_id = message_id or tweet["admin_msg_id"]
    if not target_msg_id:
        return

    # مشخصات کامل توییت حفظ می‌شود
    base = _format_admin_tweet_message(tweet["user_id"], tweet["text"])

    # وضعیت تایید یا رد همراه با جزئیات کامل در انتهای پیام
    if tweet["status"] == "approved":
        base += (
            f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>وضعیت:</b> ✅ تأیید شد\n"
            f"🕒 <b>ساعت انتشار:</b> {tweet['approved_hour']}:00 ⏰"
        )
        reply_kb = tweet_done_markup(tweet_id)
    elif tweet["status"] == "rejected":
        reason = tweet["rejection_reason"] or "دلیلی ثبت نشده است."
        base += (
            f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>وضعیت:</b> ❌ رد شد\n"
            f"✍️ <b>دلیل رد:</b> {reason}"
        )
        reply_kb = tweet_done_markup(tweet_id)
    elif tweet["status"] == "sent":
        base += f"\n\n━━━━━━━━━━━━━━━━━━━━\n<b>وضعیت:</b> 📤 در کانال ارسال شد"
        reply_kb = None
    else:
        reply_kb = tweet_action_markup(tweet_id)

    try:
        bot.edit_message_text(
            base,
            admin_chat_id,
            target_msg_id,
            parse_mode="HTML",
            reply_markup=reply_kb
        )
    except Exception:
        pass

def _send_media_to_user(bot: TeleBot, user_id: int, message: Message):
    try:
        bot.copy_message(user_id, message.chat.id, message.message_id)
        bot.send_message(message.chat.id, "✅ پیام با موفقیت برای کاربر ارسال شد.")
        return True
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ خطا در ارسال پیام:\n{e}")
        return False

def register_admin_handlers(bot: TeleBot):

    @bot.callback_query_handler(func=lambda call: call.data.startswith((
        'approve_', 'reject_', 'confirm_reject_', 'cancel_reject_',
        'reply_', 'edit_', 'confirm_edit_', 'cancel_edit_',
        'hour_', 'back_to_actions_'
    )) and db_manager.is_admin(call.message.chat.id))
    def callback_admin_actions(call: CallbackQuery):
        origin_msg_id = call.message.message_id

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

        tweet = None
        if data != 'hour':
            tweet = db_manager.get_tweet_by_id(tweet_id)
            if not tweet:
                bot.answer_callback_query(call.id, "توییت یافت نشد.", show_alert=True)
                try:
                    bot.delete_message(call.message.chat.id, origin_msg_id)
                except Exception:
                    pass
                return

            if tweet['status'] in ['approved', 'rejected', 'sent'] and not data.startswith(('reply', 'cancel')):
                bot.answer_callback_query(call.id, "⚠️ این توییت قبلاً توسط ادمین دیگری بررسی شده است.", show_alert=True)
                try:
                    bot.delete_message(call.message.chat.id, origin_msg_id)
                except Exception:
                    bot.edit_message_reply_markup(call.message.chat.id, origin_msg_id, reply_markup=None)
                return

        if data == 'reject':
            bot.edit_message_text(
                f"{_format_admin_tweet_message(tweet['user_id'], tweet['text'])}\n\n"
                "❓ آیا مطمئن هستید که می‌خواهید این توییت را رد کنید؟",
                call.message.chat.id,
                origin_msg_id,
                parse_mode='HTML',
                reply_markup=confirm_rejection_markup(tweet_id)
            )

        elif data.startswith('cancel'):
            STATE.pop(call.message.chat.id, None)
            base = _format_admin_tweet_message(tweet['user_id'], tweet['text'])
            bot.edit_message_text(
                base,
                call.message.chat.id,
                origin_msg_id,
                parse_mode='HTML',
                reply_markup=tweet_action_markup(tweet_id)
            )

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
                'origin_msg_id': origin_msg_id
            }

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
                'origin_msg_id': origin_msg_id
            }

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

            tweet = db_manager.get_tweet_by_id(tweet_id)
            if not tweet or tweet['status'] in ['approved', 'rejected', 'sent']:
                bot.answer_callback_query(call.id, "⚠️ این توییت قبلاً توسط ادمین دیگری تعیین تکلیف شده است.", show_alert=True)
                try:
                    bot.delete_message(call.message.chat.id, saved_origin_msg_id)
                except Exception:
                    pass
                STATE.pop(call.message.chat.id, None)
                return

            db_manager.approve_tweet(tweet_id, hour)

            try:
                bot.send_message(
                    tweet['user_id'],
                    f"✅ توییت شما <b>تأیید شد</b> و در ساعت <b>{hour}:00</b> منتشر خواهد شد ⏰",
                    parse_mode='HTML'
                )
            except Exception:
                pass

            STATE.pop(call.message.chat.id, None)
            _refresh_admin_message(bot, call.message.chat.id, tweet_id, saved_origin_msg_id)
            _hide_tweet_from_other_admins(bot, tweet_id, call.message.chat.id)

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
                'origin_msg_id': origin_msg_id
            }

        elif data == 'confirm' and arg.startswith('edit'):
            state = STATE.get(call.message.chat.id)
            if not state or 'new_text' not in state:
                bot.answer_callback_query(call.id, "ابتدا متن جدید را ارسال کنید.")
                return

            saved_origin_msg_id = state.get('origin_msg_id', origin_msg_id)
            db_manager.update_tweet_text(tweet_id, state['new_text'])
            STATE.pop(call.message.chat.id, None)

            _refresh_admin_message(bot, call.message.chat.id, tweet_id, saved_origin_msg_id)
            _hide_tweet_from_other_admins(bot, tweet_id, call.message.chat.id)

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

    @bot.message_handler(
        func=lambda m: db_manager.is_admin(m.chat.id) and m.chat.id in STATE,
        content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'animation']
    )
    def handle_admin_input(message: Message):
        state = STATE.get(message.chat.id)
        if not state:
            return

        if state['mode'] == 'awaiting_rejection_reason':
            reason = message.text
            tweet_id = state['tweet_id']
            user_id = state['user_id']
            origin_msg_id = state.get('origin_msg_id')

            db_manager.reject_tweet(tweet_id, reason)

            try:
                bot.send_message(
                    user_id,
                    f"❌ متأسفانه توییت شما رد شد.\n\n<b>دلیل:</b>\n{reason}",
                    parse_mode='HTML'
                )
            except Exception:
                pass

            STATE.pop(message.chat.id, None)
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass

            _refresh_admin_message(bot, message.chat.id, tweet_id, origin_msg_id)
            _hide_tweet_from_other_admins(bot, tweet_id, message.chat.id)

        elif state['mode'] == 'awaiting_reply_content':
            _send_media_to_user(bot, state['user_id'], message)
            STATE.pop(message.chat.id, None)

        elif state['mode'] == 'editing':
            STATE[message.chat.id]['new_text'] = message.text
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass

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