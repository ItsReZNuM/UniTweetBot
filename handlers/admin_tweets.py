import os
import tempfile
from telebot import TeleBot
from telebot.types import CallbackQuery, Message
from database import db_manager
from utils.keyboards import tweet_action_markup, confirm_rejection_markup, edit_tweet_markup, tweet_hours_markup
from config import ADMIN_USER_IDS
import json

STATE = {}

TEMP_DIR = os.path.join(tempfile.gettempdir(), "tweet_bot_temp")
os.makedirs(TEMP_DIR, exist_ok=True)


# ==========================
# ✅ نسخه‌ی جدید و ساده‌شده‌ی ارسال مدیا
# ==========================
def _send_media_to_user(bot: TeleBot, user_id: int, message: Message):
    """
    ارسال پیام یا مدیا از ادمین به کاربر.
    با استفاده از copy_message — سریع، تمیز و بدون دانلود فایل.
    """
    try:
        bot.copy_message(user_id, message.chat.id, message.message_id)
        bot.send_message(message.chat.id, "✅ پیام شما با موفقیت به کاربر ارسال شد.")
        return True
    except Exception as e:
        print(f"[!] خطا در ارسال پیام یا مدیا: {e}")
        bot.send_message(message.chat.id, f"⚠️ ارسال پیام به کاربر انجام نشد:\n{e}")
        return False


# ==========================
# ثبت هندلرها
# ==========================
def register_admin_handlers(bot: TeleBot, admin_id: int):
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith((
        'approve_', 'reject_', 'confirm_reject_', 'cancel_reject_', 
        'reply_', 'edit_', 'confirm_edit_', 'cancel_edit_', 'hour_')))
    def callback_admin_actions(call: CallbackQuery):
        data, arg = call.data.split('_', 1)
        tweet = db_manager.get_tweet_by_admin_msg_id(call.message.message_id)

        # اگر توییت وجود نداشت
        if not tweet and data not in ['hour']:
            bot.answer_callback_query(call.id, "این توییت در دیتابیس یافت نشد.")
            return

        # 📤 رد توییت
        if data == 'reject':
            bot.edit_message_text(
                "آیا مطمئنید که می‌خواهید این توییت را رد کنید؟",
                call.message.chat.id, call.message.message_id,
                reply_markup=confirm_rejection_markup(tweet['id'])
            )

        # 🔙 لغو رد یا لغو ویرایش
        elif data.startswith('cancel'):
            text_to_display = tweet.get('text') or "متن توییت (نامشخص)"
            if arg.startswith('reject'):
                bot.edit_message_text(
                    f"<b>✨ توییت جدید</b> (بازگشت از رد کردن)\n\n{text_to_display}",
                    call.message.chat.id, call.message.message_id,
                    reply_markup=tweet_action_markup(tweet['id'])
                )
            elif arg.startswith('edit'):
                bot.edit_message_text(
                    f"<b>✨ توییت جدید</b> (بازگشت از ویرایش)\n\n{text_to_display}",
                    call.message.chat.id, call.message.message_id,
                    reply_markup=tweet_action_markup(tweet['id'])
                )
                if call.message.chat.id in STATE and STATE[call.message.chat.id].get('mode') == 'editing':
                    del STATE[call.message.chat.id]

        # ✅ تایید رد یا تایید ویرایش
        elif data == 'confirm':
            if arg.startswith('reject'):
                bot.edit_message_text(
                    "لطفا <b>دلیل</b> خود برای رد کردن این توییت را بنویسید ✍️:",
                    call.message.chat.id, call.message.message_id
                )
                STATE[call.message.chat.id] = {
                    'mode': 'awaiting_rejection_reason',
                    'tweet_id': tweet['id'],
                    'user_id': tweet['user_id'],
                    'admin_msg_id': call.message.message_id
                }

            elif arg.startswith('edit'):
                new_text = STATE[call.message.chat.id].get('new_text') or "❌ متن یافت نشد"
                db_manager.update_tweet_text(tweet['id'], new_text)
                bot.edit_message_text(
                    f"✅ <b>توییت با موفقیت ویرایش شد</b>\n\n{new_text}",
                    call.message.chat.id, call.message.message_id,
                    reply_markup=tweet_action_markup(tweet['id'])
                )
                del STATE[call.message.chat.id]

        # ⏰ تایید و انتخاب ساعت ارسال
        elif data == 'approve':
            hours = db_manager.get_all_scheduler_hours()
            bot.edit_message_text(
                "ساعت ارسال این توییت را انتخاب کنید ⏰:",
                call.message.chat.id, call.message.message_id,
                reply_markup=tweet_hours_markup(hours)
            )
            STATE[call.message.chat.id] = {
                'mode': 'awaiting_hour_selection',
                'tweet_id': tweet['id'],
                'admin_msg_id': call.message.message_id
            }

        # 🕒 انتخاب ساعت مشخص
        elif data == 'hour':
            try:
                hour = int(arg)
            except ValueError:
                bot.answer_callback_query(call.id, "خطای داخلی: ساعت نامعتبر است.")
                return

            if call.message.chat.id in STATE and STATE[call.message.chat.id].get('mode') == 'awaiting_hour_selection':
                tweet_id = STATE[call.message.chat.id]['tweet_id']
                db_manager.approve_tweet(tweet_id, hour)

                # اطلاع به ادمین
                bot.edit_message_text(
                    f"✅ توییت در ساعت <b>{hour}:00</b> ارسال خواهد شد.",
                    call.message.chat.id, call.message.message_id
                )

                # اطلاع‌رسانی به کاربر
                user_id = db_manager.get_user_id_by_tweet(tweet_id)
                if user_id:
                    try:
                        bot.send_message(user_id, f"✅ توییت شما تأیید شد و در ساعت {hour}:00 منتشر خواهد شد ⏰")
                    except Exception:
                        bot.send_message(call.message.chat.id, "⚠️ نتوانستم پیام اطلاع‌رسانی را برای کاربر ارسال کنم.")

                del STATE[call.message.chat.id]

        # ↩️ پاسخ به کاربر
        elif data == 'reply':
            bot.edit_message_text(
                "هر <b>مدیا یا متنی</b> که می‌خواهید به کاربر ارسال کنید، بفرستید (در پاسخ به این پیام) ↩️.\n\n"
                "✅ فایل مستقیماً برای کاربر فوروارد می‌شود.",
                call.message.chat.id, call.message.message_id, parse_mode='HTML'
            )
            STATE[call.message.chat.id] = {
                'mode': 'awaiting_reply_content',
                'tweet_id': tweet['id'],
                'user_id': tweet['user_id'],
                'admin_msg_id': call.message.message_id
            }

        # 📝 ویرایش توییت
        elif data == 'edit':
            tweet_text = tweet.get('text') or "متن توییت (نامشخص)"
            bot.edit_message_text(
                f"📝 <b>توییت اصلی</b>:\n\n<code>{tweet_text}</code>\n\nلطفا متن <b>جدید</b> را ارسال کنید ✍️.",
                call.message.chat.id, call.message.message_id,
                parse_mode='HTML', reply_markup=edit_tweet_markup(tweet['id'])
            )
            STATE[call.message.chat.id] = {
                'mode': 'editing',
                'tweet_id': tweet['id'],
                'admin_msg_id': call.message.message_id,
                'original_text': tweet_text
            }

        bot.answer_callback_query(call.id)

    # 🧠 دریافت پیام/مدیا از ادمین برای پاسخ به کاربر
    @bot.message_handler(func=lambda message: message.chat.id in ADMIN_USER_IDS and message.chat.id in STATE, content_types=[
        'text', 'photo', 'video', 'document', 'audio', 'voice', 'animation'
    ])
    def handle_admin_input(message: Message):
        admin_state = STATE.get(message.chat.id)

        # ✏️ دلیل رد توییت
        if admin_state.get('mode') == 'awaiting_rejection_reason':
            reason = message.text
            tweet_id = admin_state['tweet_id']
            user_id = admin_state['user_id']
            admin_msg_id = admin_state['admin_msg_id']

            db_manager.reject_tweet(tweet_id, reason)

            try:
                bot.send_message(user_id, f"❌ متأسفانه توییت شما <b>رد شد</b>.\n\n<b>دلیل:</b>\n{reason}", parse_mode='HTML')
                bot.send_message(message.chat.id, "✅ پیام شما با موفقیت به کاربر ارسال شد.")
            except Exception:
                bot.send_message(message.chat.id, "⚠️ خطای ارسال پیام به کاربر. احتمالاً کاربر ربات را بلاک کرده است.")

            bot.edit_message_text(
                f"❌ توییت با موفقیت <b>رد شد</b>.\n\n<b>دلیل</b>: {reason}",
                message.chat.id, admin_msg_id, parse_mode='HTML'
            )
            del STATE[message.chat.id]

        # ↩️ پاسخ به کاربر
        elif admin_state.get('mode') == 'awaiting_reply_content':
            user_id = admin_state['user_id']
            admin_msg_id = admin_state['admin_msg_id']

            ok = _send_media_to_user(bot, user_id, message)
            if not ok:
                bot.send_message(message.chat.id, "⚠️ ارسال پیام با خطا مواجه شد (ممکن است کاربر بلاک کرده باشد).")

            tweet = db_manager.get_tweet_by_admin_msg_id(admin_msg_id)
            bot.edit_message_text(
                f"<b>✨ توییت اصلی</b> (پاسخ داده شد)\n\n{tweet['text']}",
                message.chat.id, admin_msg_id,
                reply_markup=tweet_action_markup(tweet['id']), parse_mode='HTML'
            )
            del STATE[message.chat.id]

        # 📝 دریافت متن جدید برای ویرایش
        elif admin_state.get('mode') == 'editing':
            new_text = message.text
            admin_msg_id = admin_state['admin_msg_id']

            STATE[message.chat.id]['new_text'] = new_text

            bot.edit_message_text(
                f"📝 <b>متن جدید</b>:\n\n<code>{new_text}</code>\n\nتایید می‌کنید؟",
                message.chat.id, admin_msg_id,
                parse_mode='HTML', reply_markup=edit_tweet_markup(admin_state['tweet_id'])
            )
