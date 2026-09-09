import os
import tempfile
import datetime
from telebot import TeleBot
from telebot.types import CallbackQuery, Message
from database import db_manager
from utils.keyboards import (
    tweet_action_markup,
    tweet_done_markup,
    confirm_rejection_markup,
    edit_tweet_markup,
    tweet_hours_markup,
    is_reply_keyboard_command,
    confirm_unapprove_markup,
    tweet_removed_markup,
)

STATE = {}

TEMP_DIR = os.path.join(tempfile.gettempdir(), "tweet_bot_temp")
os.makedirs(TEMP_DIR, exist_ok=True)

def _get_admin_tag(user) -> str:
    """دریافت تگ ادمین (یوزرنیم یا نام کاربری)"""
    if user.username:
        return f"@{user.username}"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return full_name if full_name else f"ادمین ({user.id})"

def _format_admin_tweet_message(user_id: int, tweet_text: str) -> str:
    conn = db_manager.get_db_connection()
    row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    username = row["username"] if row and row["username"] else user_id
    return f"<b>✨ توییت جدید</b> از کاربر: @{username}\n\n{tweet_text}"

def _refresh_all_admin_messages(bot: TeleBot, tweet_id: int):
    """
    پیام توییت را در چت تمامی ادمین‌ها به‌روزرسانی می‌کند و نشان می‌دهد
    کدام ادمین توییت را تایید، رد یا ویرایش کرده است.
    """
    tweet = db_manager.get_tweet_by_id(tweet_id)
    if not tweet:
        return

    base = _format_admin_tweet_message(tweet["user_id"], tweet["text"])

    if tweet.get("reply_info"):
        base += f"\n\n💬 <b>پاسخ ارسال‌شده به کاربر:</b>\n«{tweet['reply_info']}»"

    handled_by = tweet.get("handled_by")
    handled_str = f" (توسط {handled_by})" if handled_by else ""

    if tweet["status"] == "approved":
        base += (
            f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>وضعیت:</b> ✅ تأیید شد{handled_str}\n"
            f"🕒 <b>ساعت انتشار:</b> {tweet['approved_hour']}:00 ⏰"
        )
        reply_kb = tweet_done_markup(tweet_id)
    elif tweet["status"] == "rejected":
        reason = tweet["rejection_reason"] or "دلیلی ثبت نشده است."
        base += (
            f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>وضعیت:</b> ❌ رد شد{handled_str}\n"
            f"✍️ <b>دلیل رد:</b> {reason}"
        )
        reply_kb = tweet_done_markup(tweet_id)
    elif tweet["status"] == "removed":
        hour = tweet.get("approved_hour")
        hour_str = f"{hour:02d}:00" if hour is not None else "نامشخص"
        base += (
            f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>وضعیت:</b> 🗑️ توییت با موفقیت از ساعت <b>{hour_str}</b> حذف شد.{handled_str}"
        )
        reply_kb = tweet_removed_markup(tweet_id)
    elif tweet["status"] == "sent":
        base += f"\n\n━━━━━━━━━━━━━━━━━━━━\n<b>وضعیت:</b> 📤 در کانال ارسال شد"
        reply_kb = None
    else:
        # در حالت pending اگر متن ویرایش شده باشد، ثبت می‌شود
        if handled_by:
            base += f"\n\n━━━━━━━━━━━━━━━━━━━━\n✏️ <b>آخرین ویرایش:</b> توسط {handled_by}"
        reply_kb = tweet_action_markup(tweet_id)

    # ادیت پیام در صفحه تمام ادمین‌هایی که این توییت برایشان ارسال شده بود
    admin_messages = db_manager.get_tweet_admin_messages(tweet_id)
    for adm in admin_messages:
        try:
            bot.edit_message_text(
                base,
                adm["admin_id"],
                adm["message_id"],
                parse_mode="HTML",
                reply_markup=reply_kb
            )
        except Exception:
            pass

def _refresh_single_admin_message(bot: TeleBot, admin_chat_id: int, tweet_id: int, message_id: int):
    """به‌روزرسانی موقت پیام برای همان ادمین در حین کار با دکمه‌ها"""
    tweet = db_manager.get_tweet_by_id(tweet_id)
    if not tweet:
        return

    base = _format_admin_tweet_message(tweet["user_id"], tweet["text"])
    if tweet.get("reply_info"):
        base += f"\n\n💬 <b>پاسخ ارسال‌شده به کاربر:</b>\n«{tweet['reply_info']}»"

    handled_str = f" (توسط {tweet['handled_by']})" if tweet.get("handled_by") else ""
    if tweet["status"] == "approved":
        base += f"\n\n━━━━━━━━━━━━━━━━━━━━\n<b>وضعیت:</b> ✅ تأیید شد{handled_str}\n🕒 ساعت ارسال: {tweet['approved_hour']}:00"
        kb = tweet_done_markup(tweet_id)
    elif tweet["status"] == "rejected":
        base += f"\n\n━━━━━━━━━━━━━━━━━━━━\n<b>وضعیت:</b> ❌ رد شد{handled_str}\n✍️ دلیل رد: {tweet['rejection_reason']}"
        kb = tweet_done_markup(tweet_id)
    elif tweet["status"] == "removed":
        hour = tweet.get("approved_hour")
        hour_str = f"{hour:02d}:00" if hour is not None else "نامشخص"
        base += f"\n\n━━━━━━━━━━━━━━━━━━━━\n<b>وضعیت:</b> 🗑️ توییت با موفقیت از ساعت <b>{hour_str}</b> حذف شد.{handled_str}"
        kb = tweet_removed_markup(tweet_id)
    else:
        kb = tweet_action_markup(tweet_id)

    try:
        bot.edit_message_text(base, admin_chat_id, message_id, parse_mode="HTML", reply_markup=kb)
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
        'hour_', 'back_to_actions_',
        'unapprove_ask_', 'unapprove_yes_', 'unapprove_no_',
        'restore_tweet_', 'ignore_action'
    )) and db_manager.is_admin(call.message.chat.id))
    def callback_admin_actions(call: CallbackQuery):
        origin_msg_id = call.message.message_id
        if call.data == "ignore_action":
            bot.answer_callback_query(call.id)
            return

        if call.data.startswith("unapprove_ask_"):
            tweet_id = int(call.data.replace("unapprove_ask_", ""))
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=confirm_unapprove_markup(tweet_id)
            )
            bot.answer_callback_query(call.id)
            return

        if call.data.startswith("unapprove_no_"):
            tweet_id = int(call.data.replace("unapprove_no_", ""))
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=tweet_done_markup(tweet_id)
            )
            bot.answer_callback_query(call.id, "👌 عملیات لغو شد.")
            return

        if call.data.startswith("unapprove_yes_"):
            tweet_id = int(call.data.replace("unapprove_yes_", ""))
            admin_tag = _get_admin_tag(call.from_user)
            hour = db_manager.unapprove_tweet(tweet_id, handled_by=admin_tag)
            hour_str = f"{hour:02d}:00" if hour is not None else ""
            bot.answer_callback_query(call.id, f"🗑️ توییت با موفقیت از ساعت {hour_str} حذف شد.")
            _refresh_all_admin_messages(bot, tweet_id)
            return

        if call.data.startswith("restore_tweet_"):
            tweet_id = int(call.data.replace("restore_tweet_", ""))
            tweet = db_manager.get_tweet_by_id(tweet_id)
            if not tweet or tweet.get("approved_hour") is None:
                bot.answer_callback_query(call.id, "⚠️ ساعت این توییت یافت نشد.", show_alert=True)
                return
            admin_tag = _get_admin_tag(call.from_user)
            hour = tweet["approved_hour"]
            db_manager.approve_tweet(tweet_id, hour, handled_by=admin_tag)
            bot.answer_callback_query(call.id, f"✅ توییت مجدداً به ساعت {hour:02d}:00 بازگردانده شد.")
            _refresh_all_admin_messages(bot, tweet_id)
            return
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
                return

            # در صورتی که توییت قبلاً توسط ادمین دیگری رد یا تایید شده باشد
            if tweet['status'] in ['approved', 'rejected', 'sent'] and not data.startswith(('reply', 'cancel')):
                handled_by = tweet.get("handled_by") or "ادمین دیگری"
                bot.answer_callback_query(call.id, f"⚠️ این توییت قبلاً توسط {handled_by} بررسی شده است.", show_alert=True)
                _refresh_all_admin_messages(bot, tweet_id)
                return

        admin_tag = _get_admin_tag(call.from_user)

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
            _refresh_single_admin_message(bot, call.message.chat.id, tweet_id, origin_msg_id)

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
            tweet = db_manager.get_tweet_by_id(tweet_id)

            if not tweet or tweet['status'] in ['approved', 'rejected', 'sent']:
                handled_by = tweet.get("handled_by") or "ادمین دیگری"
                bot.answer_callback_query(call.id, f"⚠️ این توییت قبلاً توسط {handled_by} تعیین تکلیف شده است.", show_alert=True)
                _refresh_all_admin_messages(bot, tweet_id)
                STATE.pop(call.message.chat.id, None)
                return

            # تایید توییت و ثبت تگ ادمین
            db_manager.approve_tweet(tweet_id, hour, handled_by=admin_tag)

            try:
                bot.send_message(
                    tweet['user_id'],
                    f"✅ توییت شما <b>تأیید شد</b> و در ساعت <b>{hour}:00</b> منتشر خواهد شد ⏰",
                    parse_mode='HTML'
                )
            except Exception:
                pass

            STATE.pop(call.message.chat.id, None)
            # نمایش و ثبت تایید برای تمام ادمین‌ها
            _refresh_all_admin_messages(bot, tweet_id)

        elif data == 'reply':
            prompt_msg = bot.send_message(
                call.message.chat.id,
                "↩️ هر متن یا مدیایی که می‌خواهید به کاربر ارسال کنید، بفرستید:",
                parse_mode='HTML'
            )
            STATE[call.message.chat.id] = {
                'mode': 'awaiting_reply_content',
                'tweet_id': tweet_id,
                'user_id': tweet['user_id'],
                'origin_msg_id': origin_msg_id,
                'prompt_msg_id': prompt_msg.message_id
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

            db_manager.update_tweet_text(tweet_id, state['new_text'], handled_by=admin_tag)
            STATE.pop(call.message.chat.id, None)

            # ویرایش پیام توییت و نمایش نام ویرایش‌کننده برای تمام ادمین‌ها
            _refresh_all_admin_messages(bot, tweet_id)

        elif data == 'back' and arg.startswith('to_actions'):
            STATE.pop(call.message.chat.id, None)
            _refresh_single_admin_message(bot, call.message.chat.id, tweet_id, origin_msg_id)

        bot.answer_callback_query(call.id)

    @bot.message_handler(
        func=lambda m: db_manager.is_admin(m.chat.id) and m.chat.id in STATE and not (m.text and is_reply_keyboard_command(m.text)),
        content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'animation', 'sticker']
    )
    def handle_admin_input(message: Message):
        state = STATE.get(message.chat.id)
        if not state:
            return

        admin_tag = _get_admin_tag(message.from_user)

        if state['mode'] == 'awaiting_rejection_reason':
            reason = message.text
            tweet_id = state['tweet_id']
            user_id = state['user_id']

            # ثبت رد شدن با ذکر نام ادمین
            db_manager.reject_tweet(tweet_id, reason, handled_by=admin_tag)

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

            # نمایش دلیل رد و نام ادمین برای تمام ادمین‌ها
            _refresh_all_admin_messages(bot, tweet_id)

        elif state['mode'] == 'awaiting_reply_content':
            sent_ok = _send_media_to_user(bot, state['user_id'], message)
            if sent_ok:
                if message.text:
                    reply_desc = message.text
                elif message.caption:
                    content_fa = {
                        'photo': 'تصویر',
                        'video': 'ویدیو',
                        'document': 'فایل',
                        'audio': 'صوت',
                        'voice': 'ویس'
                    }.get(message.content_type, 'مدیا')
                    reply_desc = f"[{content_fa}] {message.caption}"
                else:
                    content_fa = {
                        'photo': 'تصویر',
                        'video': 'ویدیو',
                        'document': 'فایل',
                        'audio': 'صوت',
                        'voice': 'پیام صوتی',
                        'sticker': 'استیکر',
                        'animation': 'گیف'
                    }.get(message.content_type, 'مدیا')
                    reply_desc = f"[{content_fa} ارسال شد]"

                time_now = datetime.datetime.now().strftime("%H:%M")
                reply_summary = f"{reply_desc} (توسط {admin_tag} در ساعت {time_now})"

                db_manager.update_tweet_reply(state['tweet_id'], reply_summary, handled_by=admin_tag)
                # نمایش پاسخ ارسال‌شده برای تمام ادمین‌ها
                _refresh_all_admin_messages(bot, state['tweet_id'])

            prompt_msg_id = state.get('prompt_msg_id')
            if prompt_msg_id:
                try:
                    bot.delete_message(message.chat.id, prompt_msg_id)
                except Exception:
                    pass

            STATE.pop(message.chat.id, None)

        elif state['mode'] == 'editing':
            STATE[message.chat.id]['new_text'] = message.text
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass

            origin_msg_id = state.get('origin_msg_id')
            tweet_id = state['tweet_id']

            if origin_msg_id:
                bot.edit_message_text(
                    f"📝 <b>متن جدید پیشنهادی</b>:\n\n<code>{message.text}</code>\n\n"
                    "برای اعمال تغییر و نمایش به سایر ادمین‌ها، دکمه «تایید ویرایش» را بزنید.",
                    message.chat.id,
                    origin_msg_id,
                    parse_mode='HTML',
                    reply_markup=edit_tweet_markup(tweet_id)
                )