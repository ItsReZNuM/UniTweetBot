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
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("↩️ ارسال پیام به کاربر", callback_data=f"reply_{tweet_id}"),
        InlineKeyboardButton("🗑️ حذف توییت", callback_data=f"unapprove_ask_{tweet_id}")
    )
    return markup

def confirm_unapprove_markup(tweet_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❓ آیا از حذف شدن این توییت مطمئن هستید؟", callback_data="ignore_action"))
    markup.row(
        InlineKeyboardButton("✅ بله", callback_data=f"unapprove_yes_{tweet_id}"),
        InlineKeyboardButton("❌ خیر", callback_data=f"unapprove_no_{tweet_id}")
    )
    return markup

def tweet_removed_markup(tweet_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("↩️ پشیمون شدم", callback_data=f"restore_tweet_{tweet_id}"),
        InlineKeyboardButton("↩️ ارسال پیام به کاربر", callback_data=f"reply_{tweet_id}")
    )
    return markup

def schedule_preview_detail_markup(hour: int, tweets: list):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(f"🗑️ توییت {idx}", callback_data=f"sched_del_tw_{hour}_{t['id']}")
        for idx, t in enumerate(tweets, start=1)
    ]
    for i in range(0, len(buttons), 2):
        markup.row(*buttons[i:i+2])
    markup.add(InlineKeyboardButton("🔙 بازگشت به لیست ساعت‌ها", callback_data="back_to_hours"))
    markup.add(InlineKeyboardButton("🏠 بازگشت به مدیریت ساعت‌ها", callback_data="sched_back_main"))
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

REPLY_KEYBOARD_COMMANDS = {
    "🐦 ارسال توییت",
    "📊 دریافت چارت",
    "📊 مشاهده آمار",
    "⏰ ساعات توییت",
    "📣 پیام همگانی",
    "👥 مدیریت ادمین‌ها",
    "👑 پنل مدیریت چارت",
    "💾 مدیریت بکاپ",
}

def is_reply_keyboard_command(text: str | None) -> bool:
    return text in REPLY_KEYBOARD_COMMANDS

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
# کیبوردهای مدیریت ساعت‌ها ⏰
# ====================
def schedule_main_markup(has_hours: bool = True):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("👁️ پیش‌نمایش ساعت‌ها", callback_data="sched_preview_menu"),
        InlineKeyboardButton("➕ افزودن ساعت", callback_data="sched_add_menu"),
    )
    markup.add(
        InlineKeyboardButton("🗑️ حذف ساعت", callback_data="sched_del_menu"),
        InlineKeyboardButton("🔄 بروزرسانی", callback_data="sched_refresh"),
    )
    return markup

def schedule_preview_markup(hours: list):
    markup = InlineKeyboardMarkup(row_width=3)
    for h in hours:
        markup.add(InlineKeyboardButton(f"⏰ {h:02d}:00", callback_data=f"view_hour_{h}"))
    # در هر ردیف 3 تا؛ مرتب‌سازی دستی
    # ساخت مجدد با row_width
    # برای سادگی از حلقه بالا استفاده شد؛ دکمه بازگشت جدا
    markup.add(InlineKeyboardButton("🔙 بازگشت به مدیریت ساعت‌ها", callback_data="sched_back_main"))
    return markup

def schedule_hours_grid(hours: list, row_width=3):
    markup = InlineKeyboardMarkup(row_width=row_width)
    buttons = [InlineKeyboardButton(f"⏰ {h:02d}:00", callback_data=f"view_hour_{h}") for h in hours]
    for i in range(0, len(buttons), row_width):
        markup.row(*buttons[i:i+row_width])
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="sched_back_main"))
    return markup

def schedule_add_markup(available_hours: list):
    markup = InlineKeyboardMarkup(row_width=4)
    buttons = [InlineKeyboardButton(f"➕ {h:02d}:00", callback_data=f"sched_add_{h}") for h in available_hours]
    for i in range(0, len(buttons), 4):
        markup.row(*buttons[i:i+4])
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="sched_back_main"))
    return markup

def schedule_del_pick_markup(hours: list):
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(f"🗑️ {h:02d}:00", callback_data=f"sched_del_pick_{h}") for h in hours]
    for i in range(0, len(buttons), 3):
        markup.row(*buttons[i:i+3])
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="sched_back_main"))
    return markup

def schedule_del_move_target_markup(source_hour: int, other_hours: list):
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [InlineKeyboardButton(f"➡️ {h:02d}:00", callback_data=f"sched_del_target_{source_hour}_{h}") for h in other_hours]
    for i in range(0, len(buttons), 3):
        markup.row(*buttons[i:i+3])
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="sched_del_menu"))
    return markup

def schedule_del_confirm_markup(source_hour: int, target_hour: int | None = None):
    markup = InlineKeyboardMarkup(row_width=2)
    if target_hour is not None:
        markup.add(
            InlineKeyboardButton("✅ بله، حذف و انتقال بده", callback_data=f"sched_del_confirm_{source_hour}_{target_hour}"),
            InlineKeyboardButton("❌ انصراف", callback_data="sched_del_menu"),
        )
    else:
        markup.add(
            InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"sched_del_confirm_{source_hour}_none"),
            InlineKeyboardButton("❌ انصراف", callback_data="sched_del_menu"),
        )
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="sched_del_menu"))
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