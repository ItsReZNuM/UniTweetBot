import os
import tempfile
from telebot import TeleBot
from telebot.types import CallbackQuery, Message
from database import db_manager
from utils.keyboards import tweet_action_markup, confirm_rejection_markup, edit_tweet_markup, tweet_hours_markup
from config import ADMIN_USER_IDS
import json

STATE = {}

# مسیر پوشهٔ موقت برای ذخیرهٔ فایل‌ها
TEMP_DIR = os.path.join(tempfile.gettempdir(), "tweet_bot_temp")
os.makedirs(TEMP_DIR, exist_ok=True)

def _download_file(bot: TeleBot, file_id: str) -> str:
    """
    دانلود یک فایل تلگرام به مسیر موقت و برگرداندن مسیر فایل
    """
    f = bot.get_file(file_id)
    data = bot.download_file(f.file_path)
    # انتخاب نام فایل از مسیر فایل تلگرام
    filename = os.path.basename(f.file_path)
    local_path = os.path.join(TEMP_DIR, filename)
    with open(local_path, "wb") as out:
        out.write(data)
    return local_path

def _send_media_to_user(bot: TeleBot, user_id: int, message: Message):
    """
    ارسال محتوای پیام ادمین به کاربر با دانلود → ارسال → حذف فایل موقت
    از انواع مدیای رایج پشتیبانی می‌کند.
    """
    # متن ساده
    if message.content_type == 'text':
        bot.send_message(user_id, message.text)
        return True

    # عکس (photo): آرایه‌ای از سایزها
    if message.content_type == 'photo' and message.photo:
        try:
            largest = message.photo[-1]
            local_path = _download_file(bot, largest.file_id)
            with open(local_path, 'rb') as f:
                bot.send_photo(user_id, f, caption=message.caption)
            os.remove(local_path)
            return True
        except Exception:
            return False

    # ویدیو
    if message.content_type == 'video' and message.video:
        try:
            local_path = _download_file(bot, message.video.file_id)
            with open(local_path, 'rb') as f:
                bot.send_video(user_id, f, caption=message.caption)
            os.remove(local_path)
            return True
        except Exception:
            return False

    # داکیومنت (هر نوع فایل عمومی)
    if message.content_type == 'document' and message.document:
        try:
            local_path = _download_file(bot, message.document.file_id)
            with open(local_path, 'rb') as f:
                bot.send_document(user_id, f, caption=message.caption)
            os.remove(local_path)
            return True
        except Exception:
            return False

    # ویس (voice)
    if message.content_type == 'voice' and message.voice:
        try:
            local_path = _download_file(bot, message.voice.file_id)
            with open(local_path, 'rb') as f:
                bot.send_voice(user_id, f, caption=message.caption)
            os.remove(local_path)
            return True
        except Exception:
            return False

    # موسیقی (audio)
    if message.content_type == 'audio' and message.audio:
        try:
            local_path = _download_file(bot, message.audio.file_id)
            with open(local_path, 'rb') as f:
                bot.send_audio(user_id, f, caption=message.caption)
            os.remove(local_path)
            return True
        except Exception:
            return False

    # انیمیشن/گیف (animation)
    if message.content_type == 'animation' and message.animation:
        try:
            local_path = _download_file(bot, message.animation.file_id)
            with open(local_path, 'rb') as f:
                bot.send_animation(user_id, f, caption=message.caption)
            os.remove(local_path)
            return True
        except Exception:
            return False

    # ویدیو نُت / استیکر و ... → تلاش با copy_message
    try:
        bot.copy_message(user_id, message.chat.id, message.message_id)
        return True
    except Exception:
        # اگر هیچ‌کدام نشد و فقط کپشن/متن داریم
        if message.caption:
            bot.send_message(user_id, message.caption)
            return True
        return False

def register_admin_handlers(bot: TeleBot, admin_id: int):
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith((
        'approve_', 'reject_', 'confirm_reject_', 'cancel_reject_', 
        'reply_', 'edit_', 'confirm_edit_', 'cancel_edit_', 'hour_')))
    def callback_admin_actions(call: CallbackQuery):
        data, arg = call.data.split('_', 1)
        tweet = db_manager.get_tweet_by_admin_msg_id(call.message.message_id)

        # اگر توییت وجود نداشت (مگر برای hour_)
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
                "✅ فایل ابتدا روی سرور دانلود می‌شود، سپس برای کاربر ارسال و در نهایت حذف می‌شود.",
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


    # 🧠 هندلر برای ورودی‌های متنی و مدیا از ادمین
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
                bot.send_message(user_id, f"❌ متأسفانه توییت شما <b>رد شد</b>.\n\n<b>دلیل رد شدن</b>:\n{reason}", parse_mode='HTML')
                bot.send_message(message.chat.id, "✅ پیام شما با موفقیت به کاربر ارسال شد.")
            except Exception:
                bot.send_message(message.chat.id, "⚠️ خطای ارسال پیام به کاربر. احتمالاً کاربر ربات را بلاک کرده است.")

            bot.edit_message_text(
                f"❌ توییت با موفقیت <b>رد شد</b>.\n\n<b>دلیل</b>: {reason}",
                message.chat.id, admin_msg_id, parse_mode='HTML'
            )
            del STATE[message.chat.id]

        # ↩️ پاسخ به کاربر (دانلود → ارسال → حذف)
        elif admin_state.get('mode') == 'awaiting_reply_content':
            user_id = admin_state['user_id']
            admin_msg_id = admin_state['admin_msg_id']

            ok = _send_media_to_user(bot, user_id, message)
            if ok:
                bot.send_message(message.chat.id, "✅ پیام شما با موفقیت به کاربر ارسال شد.")
            else:
                bot.send_message(message.chat.id, "⚠️ خطای ارسال پیام به کاربر (احتمالاً بلاک کرده است).")

            tweet = db_manager.get_tweet_by_admin_msg_id(admin_msg_id)
            bot.edit_message_text(
                f"<b>✨ توییت اصلی</b> (پاسخ داده شد)\n\n{tweet['text']}",
                message.chat.id, admin_msg_id,
                reply_markup=tweet_action_markup(tweet['id']), parse_mode='HTML'
            )
            del STATE[message.chat.id]

        # 📝 مرحله دریافت متن جدید برای ویرایش
        elif admin_state.get('mode') == 'editing':
            new_text = message.text
            admin_msg_id = admin_state['admin_msg_id']

            STATE[message.chat.id]['new_text'] = new_text

            bot.edit_message_text(
                f"📝 <b>متن جدید</b>:\n\n<code>{new_text}</code>\n\nتایید می‌کنید؟",
                message.chat.id, admin_msg_id,
                parse_mode='HTML', reply_markup=edit_tweet_markup(admin_state['tweet_id'])
            )
