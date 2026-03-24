from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def user_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Davomatni belgilash")],
            [KeyboardButton(text="📝 Vazifani belgilash")],
            [KeyboardButton(text="📊 Statiskamni ko‘rish")],
        ],
        resize_keyboard=True
    )

def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Dars boshlash")],
            [KeyboardButton(text="📈 Statiskani ko‘rish")],
            [KeyboardButton(text="⚙️ Cheklovlar")],
            [KeyboardButton(text="🧹 Xotirani tozalash")],
        ],
        resize_keyboard=True
    )
def admin_limits_kb(att_hours: int, hw_days: int):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"⏱ Davomat oynasi: {att_hours} soat")],
            [KeyboardButton(text=f"📆 Vazifa muddati: {hw_days} kun")],
            [KeyboardButton(text="⬅️ Orqaga")],
        ],
        resize_keyboard=True
    )
def admin_stats_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌸 Haftalik", callback_data="stats:week")],
        [InlineKeyboardButton(text="🌙 Oylik", callback_data="stats:month")],
        [InlineKeyboardButton(text="📅 Bugungi", callback_data="stats:today")],
        [InlineKeyboardButton(text="⏳ Hozirgacha", callback_data="stats:upto")],
        [InlineKeyboardButton(text="🏆 Oylik ball", callback_data="stats:month_points")]
    ])
def user_stats_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Bugungi", callback_data="mystats:today")],
        [InlineKeyboardButton(text="🌸 Haftalik", callback_data="mystats:week")],
        [InlineKeyboardButton(text="⏳ Hozirgacha", callback_data="mystats:upto")],
        [InlineKeyboardButton(text="🌙 Oylik", callback_data="mystats:month")],
    ])

def admin_clean_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Userni o‘chirish")],
            [KeyboardButton(text="🗑 Barchasini o‘chirish")],
            [KeyboardButton(text="⬅️ Orqaga")],
        ],
        resize_keyboard=True
    )

def confirm_yes_no_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Ha"), KeyboardButton(text="❌ Yo‘q")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
def hw_lessons_inline(items: list[tuple[int, str]]):
    """
    items: [(lesson_id, "1-dars > 27.02.2026"), ...]
    """
    kb = []
    for lesson_id, title in items:
        kb.append([InlineKeyboardButton(text=title, callback_data=f"hwmark:{lesson_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)