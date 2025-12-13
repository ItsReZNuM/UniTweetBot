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
from config import ADMIN_USER_IDS

STATE = {}

TEMP_DIR = os.path.join(tempfile.gettempdir(), "tweet_bot_temp")
os.makedirs(TEMP_DIR, exist_ok=True)


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
        data, arg = call.data.split('_', 1)

        # استخراج tweet_id از callback_data
        try:
            data, arg = call.data.split('_', 1)

            tweet_id = None
            if not data.startswith('hour'):
                try:
                    tweet_id = int(arg.split('_')[-1])
                except:
                    pass

        except:
            bot.answer_callback_query(call.id, "شناسه توییت نامعتبر است.")
            return

        # دریافت توییت از دیتابیس (مستقل از message_id)
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



        # =========================
        # ❌ رد توییت (مرحله اول)
        # =========================
        if data == 'reject':
            bot.send_message(
                call.message.chat.id,
                "❌ آیا مطمئن هستید که می‌خواهید این توییت را رد کنید؟",
                reply_markup=confirm_rejection_markup(tweet_id)
            )

        # =========================
        # 🔙 لغو عملیات
        # =========================
        elif data.startswith('cancel'):
            bot.send_message(
                call.message.chat.id,
                "🔙 عملیات لغو شد. می‌توانید دوباره از منوی توییت اقدام کنید."
            )
            STATE.pop(call.message.chat.id, None)

        # =========================
        # ❌ تایید رد → گرفتن دلیل
        # =========================
        elif data == 'confirm' and arg.startswith('reject'):
            bot.send_message(
                call.message.chat.id,
                "✍️ لطفاً <b>دلیل رد</b> توییت را ارسال کنید:",
                parse_mode='HTML'
            )
            STATE[call.message.chat.id] = {
                'mode': 'awaiting_rejection_reason',
                'tweet_id': tweet_id,
                'user_id': tweet['user_id']
            }

        # =========================
        # ✅ تایید توییت → انتخاب ساعت
        # =========================
        elif data == 'approve':
            hours = db_manager.get_all_scheduler_hours()
            bot.send_message(
                call.message.chat.id,
                "⏰ ساعت ارسال توییت را انتخاب کنید:",
                reply_markup=tweet_hours_markup(hours, tweet_id)
            )
            STATE[call.message.chat.id] = {
                'mode': 'awaiting_hour_selection',
                'tweet_id': tweet_id
            }

        # =========================
        # ⏰ انتخاب ساعت ارسال
        # =========================
        elif data == 'hour':
            try:
                hour = int(arg)
            except:
                bot.answer_callback_query(call.id, "ساعت نامعتبر است.")
                return

            state = STATE.get(call.message.chat.id)
            if not state or state.get('mode') != 'awaiting_hour_selection':
                bot.answer_callback_query(call.id, "عملیات منقضی شده است.")
                return

            tweet_id = state['tweet_id']

            # گرفتن user_id مستقیماً از دیتابیس
            conn = db_manager.get_db_connection()
            row = conn.execute(
                "SELECT user_id FROM tweets WHERE id = ?", (tweet_id,)
            ).fetchone()
            conn.close()

            if not row:
                bot.answer_callback_query(call.id, "توییت یافت نشد.")
                return

            user_id = row['user_id']

            # فقط یک بار approve
            db_manager.approve_tweet(tweet_id, hour)

            # پیام به ادمین
            bot.send_message(
                call.message.chat.id,
                f"✅ توییت در ساعت <b>{hour}:00</b> زمان‌بندی شد.",
                parse_mode='HTML'
            )

            # پیام به کاربر ✅
            try:
                bot.send_message(
                    user_id,
                    f"✅ توییت شما <b>تأیید شد</b> و در ساعت <b>{hour}:00</b> منتشر خواهد شد ⏰",
                    parse_mode='HTML'
                )
            except:
                pass

            STATE.pop(call.message.chat.id, None)

        # =========================
        # ↩️ پاسخ به کاربر
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
                'user_id': tweet['user_id']
            }

        # =========================
        # 📝 ویرایش توییت
        # =========================
        elif data == 'edit':
            bot.send_message(
                call.message.chat.id,
                f"📝 <b>متن فعلی توییت</b>:\n\n<code>{tweet['text']}</code>\n\n"
                "✍️ متن جدید را ارسال کنید:",
                parse_mode='HTML',
                reply_markup=edit_tweet_markup(tweet_id)
            )
            STATE[call.message.chat.id] = {
                'mode': 'editing',
                'tweet_id': tweet_id
            }

        # =========================
        # ✅ تایید ویرایش
        # =========================
        elif data == 'confirm' and arg.startswith('edit'):
            state = STATE.get(call.message.chat.id)
            if not state or 'new_text' not in state:
                return

            db_manager.update_tweet_text(tweet_id, state['new_text'])

            bot.send_message(
                call.message.chat.id,
                "✅ متن توییت با موفقیت ویرایش شد."
            )
            STATE.pop(call.message.chat.id, None)

        bot.answer_callback_query(call.id)

    # =====================================================
    # MESSAGE HANDLER (ورودی ادمین)
    # =====================================================
    @bot.message_handler(
        func=lambda m: m.chat.id in ADMIN_USER_IDS and m.chat.id in STATE,
        content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'animation']
    )
    def handle_admin_input(message: Message):

        state = STATE.get(message.chat.id)

        # ❌ دریافت دلیل رد
        if state['mode'] == 'awaiting_rejection_reason':
            reason = message.text
            tweet_id = state['tweet_id']
            user_id = state['user_id']

            db_manager.reject_tweet(tweet_id, reason)

            try:
                bot.send_message(
                    user_id,
                    f"❌ متأسفانه توییت شما رد شد.\n\n<b>دلیل:</b>\n{reason}",
                    parse_mode='HTML'
                )
            except:
                pass

            bot.send_message(
                message.chat.id,
                "❌ توییت با موفقیت رد شد."
            )
            STATE.pop(message.chat.id, None)

        # ↩️ ارسال پیام/مدیا به کاربر
        elif state['mode'] == 'awaiting_reply_content':
            _send_media_to_user(bot, state['user_id'], message)
            STATE.pop(message.chat.id, None)

        # 📝 دریافت متن جدید برای ویرایش
        elif state['mode'] == 'editing':
            STATE[message.chat.id]['new_text'] = message.text
            bot.send_message(
                message.chat.id,
                f"📝 متن جدید ذخیره شد:\n\n<code>{message.text}</code>\n\n"
                "برای اعمال تغییر، دکمه «تایید ویرایش» را بزنید.",
                parse_mode='HTML'
            )
