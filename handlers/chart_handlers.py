# -*- coding: utf-8 -*-

import telebot
from telebot.types import Message, CallbackQuery
from handlers.chart_keyboards import user_no_result_kb
from telebot import TeleBot

from config import BOT_TOKEN, ADMIN_ID, MIN_SIMILARITY
import handlers.chart_db as chart_db
from states import S, get_state, set_state, get_data, update_data, reset
from handlers.chart_keyboards import (
    back_btn, user_results_kb,
    admin_menu_kb, admin_del_results_kb, confirm_delete_kb
)
from handlers.chart_fuzzy_search import fuzzy_match

# ---------------------------
# ابزارهای کمکی
# ---------------------------


def register_chart_handlers(bot: TeleBot):
    chart_db.init_db()
    
    def is_admin(user_id: int) -> bool:
        return user_id == ADMIN_ID


    def go_home(message_or_call, text: str | None = None):

        uid = message_or_call.from_user.id

        if is_admin(uid):
            set_state(uid, S.ADMIN_MENU, {})
            msg = text or "👑 <b>پنل ادمین</b>\n\nیکی از گزینه‌ها رو انتخاب کن:"
            if isinstance(message_or_call, CallbackQuery):
                bot.edit_message_text(msg, chat_id=message_or_call.message.chat.id,
                                    message_id=message_or_call.message.message_id,
                                    reply_markup=admin_menu_kb())
            else:
                bot.send_message(message_or_call.chat.id, msg, reply_markup=admin_menu_kb())
        else:
            set_state(uid, S.USER_WAIT_MAJOR, {})
            msg = text or "👋 سلام!\n\n🎓 لطفاً <b>نام رشته</b>‌ات رو وارد کن تا چارتش رو پیدا کنم:"
            if isinstance(message_or_call, CallbackQuery):
                bot.edit_message_text(msg, chat_id=message_or_call.message.chat.id,
                                    message_id=message_or_call.message.message_id,
                                    reply_markup=back_btn("BACK"))
            else:
                bot.send_message(message_or_call.chat.id, msg, reply_markup=back_btn("BACK"))
    
    # ---------------------------
    # /start
    # ---------------------------
    @bot.message_handler(commands=["start"])
    def start_cmd(message: Message):
        if is_admin(message.from_user.id):
            go_home(message, "👋 سلام ادمین عزیز!\n\n👑 به پنل مدیریت چارت‌ها خوش اومدی.")
        else:
            go_home(message, "👋 سلام!\n\n😊 به ربات <b>چارت رشته‌ها</b> خوش اومدی.\n🎓 اسم رشته‌ات رو بنویس تا چارت مربوطه رو برات بیارم.")


    # ---------------------------
    # Callback: BACK و منوها
    # ---------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "BACK")
    def cb_back(call: CallbackQuery):
        go_home(call)


    @bot.callback_query_handler(func=lambda c: c.data == "A_ADD")
    def cb_admin_add(call: CallbackQuery):
        uid = call.from_user.id
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "⛔ دسترسی نداری!")
            return

        set_state(uid, S.ADMIN_ADD_WAIT_MAJOR, {})
        bot.edit_message_text(
            "➕ <b>اضافه کردن چارت</b>\n\n✍️ لطفاً <b>نام رشته</b> رو ارسال کن:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back_btn("BACK")
        )


    @bot.callback_query_handler(func=lambda c: c.data == "A_DEL")
    def cb_admin_del(call: CallbackQuery):
        uid = call.from_user.id
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "⛔ دسترسی نداری!")
            return

        set_state(uid, S.ADMIN_DEL_WAIT_QUERY, {})
        bot.edit_message_text(
            "🗑️ <b>حذف چارت</b>\n\n🔎 لطفاً نام رشته رو بنویس تا جستجو کنم:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back_btn("BACK")
        )


    # ---------------------------
    # سناریوی کاربر: انتخاب رشته
    # ---------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("U_PICK:"))
    def cb_user_pick(call: CallbackQuery):
        uid = call.from_user.id
        if is_admin(uid):
            bot.answer_callback_query(call.id, "⚠️ این بخش مخصوص کاربرهاست.")
            return

        chart_id = int(call.data.split(":")[1])
        chart = chart_db.get_chart_by_id(chart_id)
        if not chart:
            bot.answer_callback_query(call.id, "❌ این چارت پیدا نشد.")
            go_home(call, "❌ چارت مورد نظر پیدا نشد.\n\n🎓 دوباره نام رشته رو وارد کن:")
            return

        # ارسال فایل با copy_message تا نام آپلودکننده نمایش داده نشود ✅
        bot.copy_message(
            chat_id=call.message.chat.id,
            from_chat_id=chart["chat_id"],
            message_id=chart["message_id"]
        )

        bot.answer_callback_query(call.id, "✅ ارسال شد!")
        go_home(call, "✅ چارت برات ارسال شد.\n\n🎓 اگه رشته‌ی دیگه‌ای می‌خوای، اسمش رو بنویس:")


    @bot.callback_query_handler(func=lambda c: c.data == "U_NOT_MINE")
    def cb_user_not_mine(call: CallbackQuery):
        uid = call.from_user.id
        if is_admin(uid):
            bot.answer_callback_query(call.id, "⚠️ این بخش مخصوص کاربرهاست.")
            return

        set_state(uid, S.USER_WAIT_MAJOR, {})
        bot.edit_message_text(
            "😕 اشکالی نداره!\n\n🎓 اگه چارت درسیت توی ربات نیست ، میتونی با آیدی ادمین @sedayedaneshjoolu_admin در ارتباط باشی که مشکلت رو برطرف کنه 😊",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=back_btn("BACK")
        )


    # ---------------------------
    # سناریوی ادمین: انتخاب نتیجه برای حذف + تایید
    # ---------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("A_DEL_PICK:"))
    def cb_admin_del_pick(call: CallbackQuery):
        uid = call.from_user.id
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "⛔ دسترسی نداری!")
            return

        chart_id = int(call.data.split(":")[1])
        chart = chart_db.get_chart_by_id(chart_id)
        if not chart:
            bot.answer_callback_query(call.id, "❌ موردی پیدا نشد.")
            go_home(call, "❌ چارت پیدا نشد.\n\n🔎 دوباره تلاش کن:")
            return

        set_state(uid, S.ADMIN_DEL_CONFIRM, {"chart_id": chart_id})
        bot.edit_message_text(
            f"⚠️ آیا مطمئنی می‌خوای این چارت حذف بشه؟\n\n"
            f"📌 <b>{chart['major_name']}</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=confirm_delete_kb(chart_id)
        )


    @bot.callback_query_handler(func=lambda c: c.data.startswith("A_DEL_YES:"))
    def cb_admin_del_yes(call: CallbackQuery):
        uid = call.from_user.id
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "⛔ دسترسی نداری!")
            return

        chart_id = int(call.data.split(":")[1])
        ok = chart_db.delete_chart(chart_id)

        if ok:
            bot.answer_callback_query(call.id, "✅ حذف شد!")
            go_home(call, "✅ چارت با موفقیت حذف شد.\n\n👑 برگشتیم به پنل ادمین:")
        else:
            bot.answer_callback_query(call.id, "❌ حذف انجام نشد.")
            go_home(call, "❌ حذف انجام نشد (شاید قبلاً حذف شده).\n\n👑 پنل ادمین:")


    @bot.callback_query_handler(func=lambda c: c.data == "A_DEL_NO")
    def cb_admin_del_no(call: CallbackQuery):
        uid = call.from_user.id
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "⛔ دسترسی نداری!")
            return

        bot.answer_callback_query(call.id, "👌 باشه، کنسل شد.")
        go_home(call, "👌 عملیات حذف لغو شد.\n\n👑 پنل ادمین:")


    # ---------------------------
    # دریافت پیام‌های متنی (طبق State)
    # ---------------------------
    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def on_text(message: Message):
        uid = message.from_user.id
        st = get_state(uid)
        txt = message.text.strip()

        # اگر کاربر /start نزده بود هم هدایتش کنیم
        if st == S.IDLE:
            go_home(message)
            return

        # ---------- کاربر عادی: جستجوی رشته ----------
        if not is_admin(uid) and st == S.USER_WAIT_MAJOR:
            all_items = chart_db.get_all_for_search()
            results = fuzzy_match(txt, all_items, min_score=MIN_SIMILARITY, limit=10)

            if not results:
                set_state(uid, S.USER_SHOW_RESULTS, {"last_query": txt})

                bot.send_message(
                    message.chat.id,
                    "😕 متأسفانه چارت مشابهی پیدا نکردم.\n\n"
                    "❓ اگر فکر می‌کنی این چارت مربوط به رشته‌ی تو نیست، از گزینه‌ی زیر استفاده کن:",
                    reply_markup=user_no_result_kb()
                )
                return

            set_state(uid, S.USER_SHOW_RESULTS, {"last_query": txt})
            bot.send_message(
                message.chat.id,
                "✅ چند تا نتیجه پیدا کردم! یکی رو انتخاب کن 👇",
                reply_markup=user_results_kb(results)
            )
            return

        # ---------- ادمین: اضافه کردن چارت ----------
        if is_admin(uid) and st == S.ADMIN_ADD_WAIT_MAJOR:
            update_data(uid, major_name=txt)
            set_state(uid, S.ADMIN_ADD_WAIT_FILE, get_data(uid))
            bot.send_message(
                message.chat.id,
                "📎 عالی!\n\nحالا <b>فایل چارت</b> رو ارسال کن (به صورت فایل/داکیومنت).",
                reply_markup=back_btn("BACK")
            )
            return

        # ---------- ادمین: حذف چارت (جستجو) ----------
        if is_admin(uid) and st == S.ADMIN_DEL_WAIT_QUERY:
            all_items = chart_db.get_all_for_search()
            results = fuzzy_match(txt, all_items, min_score=MIN_SIMILARITY, limit=10)

            if not results:
                bot.send_message(
                    message.chat.id,
                    "😕 چیزی با شباهت بالای ۸۵٪ برای حذف پیدا نکردم.\n\n🔎 دوباره نام رشته رو بنویس:",
                    reply_markup=back_btn("BACK")
                )
                return

            set_state(uid, S.ADMIN_DEL_SHOW_RESULTS, {"last_query": txt})
            bot.send_message(
                message.chat.id,
                "🗑️ موردی که می‌خوای حذف کنی رو انتخاب کن 👇",
                reply_markup=admin_del_results_kb(results)
            )
            return

        # اگر در وضعیت دیگری متن فرستاد، به خانه برگردیم
        go_home(message, "🙂 برای ادامه، از منو استفاده کن یا نام رشته رو وارد کن:")
        return


    # ---------------------------
    # دریافت فایل (ادمین هنگام Add)
    # ---------------------------
    @bot.message_handler(content_types=["document"])
    def on_document(message: Message):
        uid = message.from_user.id
        st = get_state(uid)

        if not is_admin(uid):
            bot.send_message(message.chat.id, "⛔ فقط ادمین می‌تونه فایل چارت اضافه کنه.")
            return

        if st != S.ADMIN_ADD_WAIT_FILE:
            bot.send_message(message.chat.id, "🙂 الان در مرحله‌ی دریافت فایل نیستیم. از پنل ادمین شروع کن.", reply_markup=admin_menu_kb())
            return

        data = get_data(uid)
        major_name = data.get("major_name")

        if not major_name:
            set_state(uid, S.ADMIN_ADD_WAIT_MAJOR, {})
            bot.send_message(message.chat.id, "⚠️ مشکلی پیش اومد. دوباره نام رشته رو بفرست:", reply_markup=back_btn("BACK"))
            return

        file_id = message.document.file_id
        chat_id = message.chat.id
        message_id = message.message_id

        new_id = chart_db.add_chart(major_name=major_name, file_id=file_id, chat_id=chat_id, message_id=message_id)

        bot.send_message(
            message.chat.id,
            f"✅ چارت ذخیره شد!\n\n🆔 شناسه: <b>{new_id}</b>\n📌 رشته: <b>{major_name}</b>",
            reply_markup=admin_menu_kb()
        )
        set_state(uid, S.ADMIN_MENU, {})
        return


