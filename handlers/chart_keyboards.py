
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def back_btn(cb_data="BACK"):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data=cb_data))
    return kb


def user_results_kb(results: list[dict]):
    kb = InlineKeyboardMarkup()
    for r in results:
        kb.add(InlineKeyboardButton(f"📌 {r['major_name']} ({r['score']}٪)", callback_data=f"U_PICK:{r['id']}"))

    kb.add(InlineKeyboardButton("❌ چارت رشته من نیست", callback_data="U_NOT_MINE"))
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="BACK"))
    return kb

def user_no_result_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ چارت رشته من نیست", callback_data="U_NOT_MINE"))
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="BACK"))
    return kb


def admin_menu_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ اضافه کردن چارت", callback_data="A_ADD"))
    kb.add(InlineKeyboardButton("🗑️ حذف چارت", callback_data="A_DEL"))
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="BACK"))
    return kb


def admin_del_results_kb(results: list[dict]):
    kb = InlineKeyboardMarkup()
    for r in results:
        kb.add(InlineKeyboardButton(f"🗑️ {r['major_name']} ({r['score']}٪)", callback_data=f"A_DEL_PICK:{r['id']}"))
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="BACK"))
    return kb


def confirm_delete_kb(chart_id: int):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ بله، حذف کن", callback_data=f"A_DEL_YES:{chart_id}"),
        InlineKeyboardButton("❌ خیر", callback_data="A_DEL_NO"),
    )
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="BACK"))
    return kb
