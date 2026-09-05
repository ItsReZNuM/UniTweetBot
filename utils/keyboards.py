from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database import db_manager

def tweet_action_markup(tweet_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ تایید توییت", callback_data=f"approve_{tweet_id}"),
        InlineKeyboardButton("❌ رد توییت", callback_data=f"reject_{tweet_id}")
    )
    markup.add(
        InlineKeyboardButton("↩️ پاسخ به کاربر", callback_data=f"reply_{tweet_id}")
    )
    markup.add(
        InlineKeyboardButton("📝 ویرایش توییت", callback_data=f"edit_{tweet_id}")
    )
    return markup

def tweet_done_markup(tweet_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("↩️ ارسال پیام به کاربر", callback_data=f"reply_{tweet_id}"))
    return markup

def confirm_rejection_markup(tweet_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ بله، مطمئنم", callback_data=f"confirm_reject_{tweet_id}"),
        InlineKeyboardButton("❌ خیر، بازگشت", callback_data=f"cancel_reject_{tweet_id}")
    )
    return markup

def edit_tweet_markup(tweet_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ تایید ویرایش", callback_data=f"confirm_edit_{tweet_id}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data=f"cancel_edit_{tweet_id}")
    )
    return markup

def tweet_hours_markup(hours, tweet_id):
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(f"{h}:00 ⏰", callback_data=f"hour_{h}") for h in hours]
    markup.add(*buttons)
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_to_actions_{tweet_id}"))
    return markup

def main_menu_markup(user_id: int):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    is_super = db_manager.is_superadmin(user_id)
    is_adm = db_manager.is_admin(user_id)

    if is_super:
        markup.add(
            KeyboardButton("📊 مشاهده آمار"),
            KeyboardButton("⏰ ساعات توییت"),
        )
        markup.add(
            KeyboardButton("📣 پیام همگانی"),
            KeyboardButton("👥 مدیریت ادمین‌ها"),
        )
        markup.add(
            KeyboardButton("👑 پنل مدیریت چارت"),
            KeyboardButton("💾 مدیریت بکاپ"),
        )
        markup.add(
            KeyboardButton("🐦 ارسال توییت"),
            KeyboardButton("📊 دریافت چارت"),
        )
    elif is_adm:
        markup.add(
            KeyboardButton("📊 مشاهده آمار"),
            KeyboardButton("⏰ ساعات توییت"),
        )
        markup.add(
            KeyboardButton("📣 پیام همگانی"),
            KeyboardButton("👑 پنل مدیریت چارت"),
        )
        markup.add(
            KeyboardButton("🐦 ارسال توییت"),
            KeyboardButton("📊 دریافت چارت"),
        )
    else:
        markup.add(
            KeyboardButton("🐦 ارسال توییت"),
            KeyboardButton("📊 دریافت چارت"),
        )

    return markup

# ====================
# کیبوردهای مدیریت ادمین
# ====================
def admin_management_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ افزودن ادمین", callback_data="admin_mgmt_add"),
        InlineKeyboardButton("➖ حذف ادمین", callback_data="admin_mgmt_del"),
    )
    markup.add(
        InlineKeyboardButton("📋 لیست ادمین‌ها", callback_data="admin_mgmt_list"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="admin_mgmt_back"),
    )
    return markup

def admin_del_list_markup(admins: list):
    markup = InlineKeyboardMarkup(row_width=1)
    for adm in admins:
        name = adm.get('first_name') or adm.get('username') or adm['id']
        markup.add(InlineKeyboardButton(f"❌ حذف {name} ({adm['id']})", callback_data=f"admin_del_pick_{adm['id']}"))
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_mgmt_back"))
    return markup

def confirm_admin_del_markup(admin_id: int):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"admin_del_yes_{admin_id}"),
        InlineKeyboardButton("❌ خیر", callback_data="admin_del_no"),
    )
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_mgmt_del"))
    return markup

# ====================
# کیبوردهای پنل بکاپ
# ====================
def backup_menu_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📥 دریافت آنی دیتابیس‌ها", callback_data="bk_download_now"),
        InlineKeyboardButton("⚙️ تنظیم ارسال خودکار و مکرر", callback_data="bk_schedule_menu"),
        InlineKeyboardButton("🔄 بروزرسانی وضعیت و زمان", callback_data="bk_refresh"),
    )
    return markup

def backup_schedule_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📅 روزانه (۲۴ ساعت)", callback_data="bk_set_daily"),
        InlineKeyboardButton("🗓️ سه روز یکبار", callback_data="bk_set_3days"),
    )
    markup.add(
        InlineKeyboardButton("📆 هفتگی (۷ روز)", callback_data="bk_set_weekly"),
        InlineKeyboardButton("🌙 ماهانه (۳۰ روز)", callback_data="bk_set_monthly"),
    )
    markup.add(
        InlineKeyboardButton("❌ غیرفعال کردن ارسال خودکار", callback_data="bk_set_off"),
    )
    markup.add(
        InlineKeyboardButton("🔙 بازگشت به پنل بکاپ", callback_data="bk_back_main"),
    )
    return markup