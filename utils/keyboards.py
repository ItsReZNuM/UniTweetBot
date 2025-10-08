from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

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

def tweet_hours_markup(hours):
    markup = InlineKeyboardMarkup(row_width=3)
    # 🌟 FIX 1: تغییر callback_data از hour_select_{h} به hour_{h} برای تجزیه آسان‌تر
    buttons = [InlineKeyboardButton(f"{h}:00 ⏰", callback_data=f"hour_{h}") for h in hours]
    markup.add(*buttons)
    return markup

def admin_panel_markup():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("📣 پیام همگانی"),
        KeyboardButton("📊 مشاهده آمار"),
    )
    markup.add(
        KeyboardButton("⏰ ساعات توییت"),
    )
    return markup

def tweet_hours_list_markup(hours):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(f"ساعت {h}:00 ⏰", callback_data=f"view_hour_{h}") for h in hours]
    markup.add(*buttons)
    markup.add(
        InlineKeyboardButton("➕ افزودن ساعت جدید", callback_data="add_new_hour")
    )
    return markup

def remove_hour_markup(hour):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("حذف ساعت ❌", callback_data=f"remove_hour_confirm_{hour}")
    )
    return markup

def transfer_hour_markup(hour_to_remove, available_hours):
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton(f"{h}:00", callback_data=f"transfer_to_{hour_to_remove}_{h}") 
        for h in available_hours
    ]
    markup.add(*buttons)
    return markup