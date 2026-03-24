import asyncio
from datetime import date, datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, DB_PATH, ADMINS, TIMEZONE_OFFSET_HOURS

from db import DB
from states import AdminClean, Register, AdminLimits
from keyboards import (
    admin_clean_kb, confirm_yes_no_kb, admin_kb,
    hw_lessons_inline, user_stats_inline,
    user_kb, admin_stats_inline, admin_limits_kb
)
from utils import now_uz, gen_token, is_admin
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi .env faylda!")
# TIMEZONE
UZ_TZ = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))

DAY_NUM_EMOJI = ["1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣"]
SQUARES = ["🟥", "🟧", "🟩", "🟦", "🟪", "⬜️", "🟫"]

# DB
db = DB(DB_PATH)

# BOT
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
def day_symbol(weekday_idx: int, att_row, hw_row) -> str:
    """
    New rules:
    - ON_TIME => digit (auto homework considered done)
    - LATE => 🕒  (optional marker)
    - No attendance but homework => square
    - None => ❌
    """
    if att_row and att_row["att_status"] == "ON_TIME":
        return DAY_NUM_EMOJI[weekday_idx]

    if att_row and att_row["att_status"] == "LATE":
        return "🕒"  # kech kirgan (dars+vazifa hisoblanmaydi)

    if (not att_row) and hw_row:
        return SQUARES[weekday_idx]

    return "❌"

def parse_start_payload(text: str) -> str | None:
    # "/start lesson_<token>"
    parts = text.split(maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return None


@dp.message(F.text == "/id")
async def my_id(message: Message):
    await message.answer(f"Your user_id: {message.from_user.id}\nChat id: {message.chat.id}")

def week_start(d: date) -> date:
    # Monday start
    return d - timedelta(days=d.weekday())


def iso(dt: datetime) -> str:
    return dt.isoformat()


def date_key(dt_iso: str) -> date:
    # lessons.start_at isoformat tz-aware
    return datetime.fromisoformat(dt_iso).astimezone(UZ_TZ).date()


def to_date(dt_iso: str) -> date:
    return datetime.fromisoformat(dt_iso).astimezone(UZ_TZ).date()


def build_upto_report(db, end_day: date) -> str:
    first = db.get_first_lesson()
    if not first:
        return "🌸Hozirgacha davomat 🌸\n\nHali darslar yo‘q."

    start_day = to_date(first["start_at"])

    start_iso = datetime.combine(start_day, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    end_iso = datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=UZ_TZ).isoformat()

    lessons = db.get_lessons_between(start_iso, end_iso)
    if not lessons:
        return "🌸Hozirgacha davomat 🌸\n\nHali darslar yo‘q."

    # 1 kunda 1 dars: oxirgisi
    lesson_by_day = {}
    for l in lessons:
        d = to_date(l["start_at"])
        lesson_by_day[d] = l

    lesson_days = sorted(lesson_by_day.keys())
    lesson_ids = [lesson_by_day[d]["id"] for d in lesson_days]

    att_map = db.get_attendance_map(lesson_ids)
    hw_map = db.get_homework_map(lesson_ids)
    users = db.list_users_simple()

    lines = []
    lines.append("🌸Hozirgacha davomat 🌸\n")
    lines.append(f"{start_day.strftime('%d.%m.%Y')} - {end_day.strftime('%d.%m.%Y')}\n")

    idx = 1
    for u in users:
        row = []
        for d in lesson_days:
            w = d.weekday()
            lesson_id = lesson_by_day[d]["id"]
            att = att_map.get((lesson_id, u["id"]))
            hw = hw_map.get((lesson_id, u["id"]))
            row.append(day_symbol(w, att, hw))

        result = "💯" if is_full_success(row) else ""
        lines.append(f"{idx}. {u['full_name']}{''.join(row)}{result}")
        idx += 1

    return "\n".join(lines)


def build_week_report(db, any_day: date) -> str:
    start = week_start(any_day)
    end = start + timedelta(days=7)

    lessons = db.get_lessons_between(
        datetime.combine(start, datetime.min.time(), tzinfo=UZ_TZ).isoformat(),
        datetime.combine(end, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    )

    # 1 kunda 1 dars: shu sananing oxirgisi
    lesson_by_day = {}
    for l in lessons:
        d = to_date(l["start_at"])
        lesson_by_day[d] = l

    week_days = [start + timedelta(days=i) for i in range(7)]
    lesson_ids = [lesson_by_day[d]["id"] for d in week_days if d in lesson_by_day]

    att_map = db.get_attendance_map(lesson_ids)
    hw_map = db.get_homework_map(lesson_ids)
    users = db.list_users_simple()

    lines = []
    lines.append("🌸Haftalik davomat 🌸\n")
    lines.append(f"{start.strftime('%d.%m.%Y')} - {(end - timedelta(days=1)).strftime('%d.%m.%Y')}\n")

    idx = 1
    for u in users:
        row = []

        for i, d in enumerate(week_days):
            if d not in lesson_by_day:
                row.append("⬛️")
                continue

            lesson_id = lesson_by_day[d]["id"]
            att = att_map.get((lesson_id, u["id"]))
            hw = hw_map.get((lesson_id, u["id"]))

            row.append(day_symbol(i, att, hw))

        # 💯 faqat dars bo‘lgan kunlar bo‘yicha tekshiriladi (⬛️ ni hisobga olmaymiz)
        only_lesson_symbols = [row[i] for i, d in enumerate(week_days) if d in lesson_by_day]
        result = "💯" if is_full_success(only_lesson_symbols) else ""

        lines.append(f"{idx}. {u['full_name']}{''.join(row)}{result}")
        idx += 1

    return "\n".join(lines)


def build_today_report(db, day: date) -> str:
    start_iso = datetime.combine(day, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    end_iso = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UZ_TZ).isoformat()

    lesson = db.get_last_lesson_on_date(start_iso, end_iso)
    header = f"📅 Bugungi statistika\n\n{day.strftime('%d.%m.%Y')}\n"

    if not lesson:
        return header + "\n⬛️ Bugun dars ochilmagan."

    lesson_id = lesson["id"]
    start_at = datetime.fromisoformat(lesson["start_at"]).astimezone(UZ_TZ)

    users = db.list_users_simple()
    att_map = db.get_attendance_map([lesson_id])
    hw_map = db.get_homework_map([lesson_id])

    on_time = []
    late = []
    hw_wo_att = []
    absent = []

    for u in users:
        att = att_map.get((lesson_id, u["id"]))
        hw = hw_map.get((lesson_id, u["id"]))

        if att and att["att_status"] == "ON_TIME":
            on_time.append(u["full_name"])
        elif att and att["att_status"] == "LATE":
            late.append(u["full_name"])
        elif (not att) and hw:
            hw_wo_att.append(u["full_name"])
        else:
            absent.append(u["full_name"])

    def block(title: str, arr: list[str]) -> str:
        if not arr:
            return f"{title}: 0"
        return f"{title}: {len(arr)}\n" + "\n".join([f"— {x}" for x in arr])

    return "\n".join([
        header,
        f"🕘 Dars vaqti: {start_at.strftime('%H:%M')}\n",
        block("✅ Kirganlar (avto vazifa)", on_time),
        "",
        block("🕒 Kech kirganlar", late),
        "",
        block("🟥 Darsga kirmay vazifa belgilagan", hw_wo_att),
        "",
        block("❌ Umuman belgilanmagan", absent),
    ])


def month_start(d: date) -> date:
    return d.replace(day=1)


def next_month_start(d: date) -> date:
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1)
    return d.replace(month=d.month + 1, day=1)


def week_index_in_month(d: date) -> int:
    """
    Oy ichida 1-hafta, 2-hafta... (Dushanbadan boshlanadigan hafta)
    """
    ms = month_start(d)
    first_week_start = week_start(ms)  # Monday of the week where month starts
    return ((d - first_week_start).days // 7) + 1

def is_complete_symbol(sym: str) -> bool:
    return sym in DAY_NUM_EMOJI or sym in SQUARES
def is_full_success(symbols: list[str]) -> bool:
    # row ichida birorta ❌ yoki 🕒 bo‘lmasa => 💯
    if not symbols:
        return False
    return all(is_complete_symbol(s) for s in symbols)
def build_month_report(db, any_day: date) -> str:
    ms = month_start(any_day)
    nm = next_month_start(any_day)

    start_iso = datetime.combine(ms, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    end_iso = datetime.combine(nm, datetime.min.time(), tzinfo=UZ_TZ).isoformat()

    lessons = db.get_lessons_between(start_iso, end_iso)
    if not lessons:
        return f"🌙 Oylik davomat\n\n{ms.strftime('%m.%Y')}\n\nBu oyda dars yo‘q."

    # 1 kunda 1 dars: shu sananing oxirgisi
    lesson_by_day = {}
    for l in lessons:
        d = to_date(l["start_at"])
        lesson_by_day[d] = l

    lesson_days_sorted = sorted(lesson_by_day.keys())
    if not lesson_days_sorted:
        return f"🌙 Oylik davomat\n\n{ms.strftime('%m.%Y')}\n\nBu oyda dars yo‘q."

    lesson_ids = [lesson_by_day[d]["id"] for d in lesson_days_sorted]

    att_map = db.get_attendance_map(lesson_ids)
    hw_map = db.get_homework_map(lesson_ids)
    users = db.list_users_simple()

    # haftalarga guruhlash
    weeks = {}
    for d in lesson_days_sorted:
        wi = week_index_in_month(d)
        weeks.setdefault(wi, []).append(d)

    lines = []
    lines.append("🌙 Oylik davomat\n")
    lines.append(f"{ms.strftime('%d.%m.%Y')} - {(nm - timedelta(days=1)).strftime('%d.%m.%Y')}\n")

    # ===== Haftalar bo‘yicha jadval =====
    for wi in sorted(weeks.keys()):
        days = weeks[wi]
        ws = week_start(days[0])
        we = ws + timedelta(days=6)

        lines.append(f"\n— {wi}-hafta ({ws.strftime('%d.%m.%Y')} - {we.strftime('%d.%m.%Y')})\n")

        idx = 1
        for u in users:
            row = []
            total = 0
            completed = 0  # digit yoki square

            for d in days:
                total += 1
                w = d.weekday()
                lesson_id = lesson_by_day[d]["id"]
                att = att_map.get((lesson_id, u["id"]))
                hw = hw_map.get((lesson_id, u["id"]))

                sym = day_symbol(w, att, hw)
                row.append(sym)

                if is_complete_symbol(sym):
                    completed += 1

            # ✅ Yangi qoidaga ko‘ra 💯:
            # haftadagi barcha darslar complete bo‘lsa (❌ va 🕒 yo‘q)
            result = "💯" if (total > 0 and completed == total) else ""
            lines.append(f"{idx}. {u['full_name']}{''.join(row)}{result}")
            idx += 1

    # ===== Natija (oy bo‘yicha) =====
    # 📚 on_time/total, ✅ on_time, 🟥 hw_without_att, 🕒 late, ❌ nothing
    lines.append("\n\n📌 Natija (oy bo‘yicha)\n")
    total_month = len(lesson_days_sorted)

    for i, u in enumerate(users, start=1):
        on_time = 0
        late = 0
        hw_wo_att = 0
        absent = 0

        for d in lesson_days_sorted:
            w = d.weekday()
            lesson_id = lesson_by_day[d]["id"]
            att = att_map.get((lesson_id, u["id"]))
            hw = hw_map.get((lesson_id, u["id"]))

            sym = day_symbol(w, att, hw)

            if sym in DAY_NUM_EMOJI:
                on_time += 1
            elif sym == "🕒":
                late += 1
            elif sym in SQUARES:
                hw_wo_att += 1
            else:
                absent += 1

        lines.append(
            f"{i}. {u['full_name']} — "
            f"📚{on_time}/{total_month}  ✅{on_time}  🟥{hw_wo_att}  🕒{late}  ❌{absent}"
        )

    return "\n".join(lines)


# User
def build_my_today(db, user_id: int, full_name: str, day: date) -> str:
    start_iso = datetime.combine(day, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    end_iso = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UZ_TZ).isoformat()

    lesson = db.get_last_lesson_on_date(start_iso, end_iso)
    header = f"📅 Bugungi statiska\n\n{day.strftime('%d.%m.%Y')}\n"

    if not lesson:
        return header + "\n⬛️ Bugun dars ochilmagan."

    lesson_id = lesson["id"]
    start_at = datetime.fromisoformat(lesson["start_at"]).astimezone(UZ_TZ)

    att = db.get_attendance(lesson_id, user_id)
    hw = db.get_homework(lesson_id, user_id)

    # darsdagi holat
    if att:
        if att["att_status"] == "LATE":
            att_txt = "🕒 Kech kirgansiz"
        else:
            att_txt = "✅ Darsga kirgansiz"
    else:
        att_txt = "❌ Darsga kirmagansiz"

    # vazifa holat
    if hw:
        if att:
            hw_txt = "☑️ Vazifa belgilangan"
        else:
            hw_txt = "🟥 Vazifa belgilangan (darsga kirmay)"
    else:
        hw_txt = "🔴 Vazifa belgilanmagan"

    return (
            header
            + f"🕘 Dars vaqti: {start_at.strftime('%H:%M')}\n\n"
            + f"👤 {full_name}\n"
            + f"{att_txt}\n"
            + f"{hw_txt}"
    )


def build_my_week(db, user_id: int, full_name: str, any_day: date) -> str:
    start = week_start(any_day)
    end = start + timedelta(days=7)

    lessons = db.get_lessons_between(
        datetime.combine(start, datetime.min.time(), tzinfo=UZ_TZ).isoformat(),
        datetime.combine(end, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    )

    lesson_by_day = {}
    for l in lessons:
        d = to_date(l["start_at"])
        lesson_by_day[d] = l

    week_days = [start + timedelta(days=i) for i in range(7)]
    lesson_ids = [lesson_by_day[d]["id"] for d in week_days if d in lesson_by_day]

    att_map = db.get_attendance_map(lesson_ids)
    hw_map = db.get_homework_map(lesson_ids)

    row = []
    for i, d in enumerate(week_days):
        if d not in lesson_by_day:
            row.append("⬛️")
            continue

        lesson_id = lesson_by_day[d]["id"]
        att = att_map.get((lesson_id, user_id))
        hw = hw_map.get((lesson_id, user_id))
        row.append(day_symbol(i, att, hw))

    only_lesson_symbols = [row[i] for i, d in enumerate(week_days) if d in lesson_by_day]
    result = "💯" if is_full_success(only_lesson_symbols) else ""

    return (
        "🌸 Haftalik statiska 🌸\n\n"
        f"{start.strftime('%d.%m.%Y')} - {(end - timedelta(days=1)).strftime('%d.%m.%Y')}\n\n"
        f"1. {full_name}{''.join(row)}{result}"
    )

def build_month_points_report(db, any_day: date) -> str:
    ms = month_start(any_day)
    nm = next_month_start(any_day)

    start_iso = datetime.combine(ms, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    end_iso = datetime.combine(nm, datetime.min.time(), tzinfo=UZ_TZ).isoformat()

    lessons = db.get_lessons_between(start_iso, end_iso)
    if not lessons:
        return f"🏆 Oylik ball\n\n{ms.strftime('%m.%Y')}\n\nBu oyda dars yo‘q."

    lesson_by_day = {}
    for l in lessons:
        d = to_date(l["start_at"])
        lesson_by_day[d] = l

    lesson_days_sorted = sorted(lesson_by_day.keys())
    if not lesson_days_sorted:
        return f"🏆 Oylik ball\n\n{ms.strftime('%m.%Y')}\n\nBu oyda dars yo‘q."

    lesson_ids = [lesson_by_day[d]["id"] for d in lesson_days_sorted]
    att_map = db.get_attendance_map(lesson_ids)
    hw_map = db.get_homework_map(lesson_ids)
    users = db.list_users_simple()

    # haftalarga dars kunlarini bo‘lamiz
    weeks = {}
    for d in lesson_days_sorted:
        wi = week_index_in_month(d)
        weeks.setdefault(wi, []).append(d)

    # user -> haftalik 💯 soni
    points = {u["id"]: 0 for u in users}

    for wi, days in weeks.items():
        for u in users:
            total = 0
            completed = 0
            for d in days:
                total += 1
                w = d.weekday()
                lesson_id = lesson_by_day[d]["id"]
                att = att_map.get((lesson_id, u["id"]))
                hw = hw_map.get((lesson_id, u["id"]))
                sym = day_symbol(w, att, hw)
                if is_complete_symbol(sym):
                    completed += 1
            # hafta 💯 bo‘lsa +1 ball
            if total > 0 and completed == total:
                points[u["id"]] += 1

    # 1-4 ball bo‘yicha guruhlash
    groups = {4: [], 3: [], 2: [], 1: [], 0: []}
    for u in users:
        p = points[u["id"]]
        if p >= 4:
            groups[4].append(u["full_name"])
        elif p == 3:
            groups[3].append(u["full_name"])
        elif p == 2:
            groups[2].append(u["full_name"])
        elif p == 1:
            groups[1].append(u["full_name"])
        else:
            groups[0].append(u["full_name"])

    # chiroyli “toj/olmos” bilan
    lines = []
    lines.append("🏆 Oylik ball natijalari\n")
    lines.append(f"{ms.strftime('%d.%m.%Y')} - {(nm - timedelta(days=1)).strftime('%d.%m.%Y')}\n")
    lines.append("Qoidasi: har hafta 💯 bo‘lsa +1 ball.\n")

    def section(title: str, emoji: str, names: list[str]) -> str:
        if not names:
            return f"{emoji} {title}: 0"
        body = "\n".join([f"— {n}" for n in names])
        return f"{emoji} {title}: {len(names)}\n{body}"

    lines.append(section("4 ball (4 hafta 💯)", "👑💎", groups[4]))
    lines.append("")
    lines.append(section("3 ball (3 hafta 💯)", "👑", groups[3]))
    lines.append("")
    lines.append(section("2 ball (2 hafta 💯)", "💎", groups[2]))
    lines.append("")
    lines.append(section("1 ball (1 hafta 💯)", "⭐", groups[1]))
    lines.append("")
    lines.append(section("0 ball", "⚪️", groups[0]))

    return "\n".join(lines)
def build_my_upto(db, user_id: int, full_name: str, end_day: date) -> str:
    first = db.get_first_lesson()
    if not first:
        return "🌸Hozirgacha statiska 🌸\n\nHali darslar yo‘q."

    start_day = to_date(first["start_at"])

    start_iso = datetime.combine(start_day, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    end_iso = datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=UZ_TZ).isoformat()

    lessons = db.get_lessons_between(start_iso, end_iso)
    if not lessons:
        return "🌸Hozirgacha statiska 🌸\n\nHali darslar yo‘q."

    lesson_by_day = {}
    for l in lessons:
        d = to_date(l["start_at"])
        lesson_by_day[d] = l

    lesson_days = sorted(lesson_by_day.keys())
    lesson_ids = [lesson_by_day[d]["id"] for d in lesson_days]

    att_map = db.get_attendance_map(lesson_ids)
    hw_map = db.get_homework_map(lesson_ids)

    row = []
    for d in lesson_days:
        w = d.weekday()
        lesson_id = lesson_by_day[d]["id"]
        att = att_map.get((lesson_id, user_id))
        hw = hw_map.get((lesson_id, user_id))
        row.append(day_symbol(w, att, hw))

    result = "💯" if is_full_success(row) else ""

    return (
        "🌸Hozirgacha statiska 🌸\n\n"
        f"{start_day.strftime('%d.%m.%Y')} - {end_day.strftime('%d.%m.%Y')}\n\n"
        f"1. {full_name}{''.join(row)}{result}"
    )


def build_my_month(db, user_id: int, full_name: str, any_day: date) -> str:
    ms = month_start(any_day)
    nm = next_month_start(any_day)

    start_iso = datetime.combine(ms, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    end_iso = datetime.combine(nm, datetime.min.time(), tzinfo=UZ_TZ).isoformat()

    lessons = db.get_lessons_between(start_iso, end_iso)
    if not lessons:
        return f"🌙 Oylik statiska\n\n{ms.strftime('%m.%Y')}\n\nBu oyda dars yo‘q."

    lesson_by_day = {}
    for l in lessons:
        d = to_date(l["start_at"])
        lesson_by_day[d] = l

    lesson_days_sorted = sorted(lesson_by_day.keys())
    if not lesson_days_sorted:
        return f"🌙 Oylik statiska\n\n{ms.strftime('%m.%Y')}\n\nBu oyda dars yo‘q."

    lesson_ids = [lesson_by_day[d]["id"] for d in lesson_days_sorted]
    att_map = db.get_attendance_map(lesson_ids)
    hw_map = db.get_homework_map(lesson_ids)

    weeks = {}
    for d in lesson_days_sorted:
        wi = week_index_in_month(d)
        weeks.setdefault(wi, []).append(d)

    lines = []
    lines.append("🌙 Oylik statiska\n")
    lines.append(f"{ms.strftime('%d.%m.%Y')} - {(nm - timedelta(days=1)).strftime('%d.%m.%Y')}\n")
    lines.append(f"👤 {full_name}\n")

    for wi in sorted(weeks.keys()):
        days = weeks[wi]
        ws = week_start(days[0])
        we = ws + timedelta(days=6)

        row = []
        for d in days:
            w = d.weekday()
            lesson_id = lesson_by_day[d]["id"]
            att = att_map.get((lesson_id, user_id))
            hw = hw_map.get((lesson_id, user_id))
            row.append(day_symbol(w, att, hw))

        result = "💯" if is_full_success(row) else ""
        lines.append(f"\n— {wi}-hafta ({ws.strftime('%d.%m.%Y')} - {we.strftime('%d.%m.%Y')})")
        lines.append(f"1. {full_name}{''.join(row)}{result}")

    # Natija (oy bo‘yicha) — 📚 ✅ 🟥 🕒 ❌
    total_month = len(lesson_days_sorted)
    on_time = 0
    late = 0
    hw_wo_att = 0
    absent = 0

    for d in lesson_days_sorted:
        w = d.weekday()
        lesson_id = lesson_by_day[d]["id"]
        att = att_map.get((lesson_id, user_id))
        hw = hw_map.get((lesson_id, user_id))
        sym = day_symbol(w, att, hw)

        if sym in DAY_NUM_EMOJI:
            on_time += 1
        elif sym == "🕒":
            late += 1
        elif sym in SQUARES:
            hw_wo_att += 1
        else:
            absent += 1

    lines.append("\n\n📌 Natija (oy bo‘yicha)")
    lines.append(f"1. {full_name} — 📚{on_time}/{total_month}  ✅{on_time}  🟥{hw_wo_att}  🕒{late}  ❌{absent}")

    return "\n".join(lines)


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    payload = parse_start_payload(message.text or "")

    # 1) Admin start
    if is_admin(tg_id, ADMINS):
        await state.clear()
        await message.answer("Admin panel.", reply_markup=admin_kb())
        if payload:
            await message.answer(
                "Siz admin sifatida link orqali kirdingiz. Oddiy foydalanuvchi davomatiga ta’sir qilmaydi.")
        return

    # 2) User start
    user = db.get_user_by_tg(tg_id)
    if not user:
        # Agar deep-link bilan kirgan bo‘lsa payloadni eslab turamiz
        if payload and payload.startswith("lesson_"):
            await state.update_data(pending_payload=payload)
        await state.set_state(Register.full_name)
        await message.answer("Assalomu alaykum. Ism va familiyangizni kiriting:")
        return

    # user mavjud
    await message.answer(f"Xush kelibsiz, {user['full_name']}!", reply_markup=user_kb())

    # Agar payload bor bo‘lsa, darhol davomatni belgilab ko‘ramiz
    if payload and payload.startswith("lesson_"):
        await handle_lesson_payload(message, payload, user["id"], user["full_name"])


@dp.message(Register.full_name, F.text)
async def register_full_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Iltimos, ism-familiyani to‘liq kiriting.")
        return

    tg_id = message.from_user.id
    created = now_uz().isoformat()
    user = db.create_user(tg_id, full_name, created)

    data = await state.get_data()
    payload = data.get("pending_payload")
    await state.clear()

    await message.answer(f"Rahmat, {full_name}! Endi botdan foydalanishingiz mumkin.", reply_markup=user_kb())

    if payload and payload.startswith("lesson_"):
        await handle_lesson_payload(message, payload, user["id"], full_name)


# --------- Admin: tozalash  ---------
@dp.message(F.text == "🧹 Xotirani tozalash")
async def admin_clean_menu(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, ADMINS):
        return
    await state.set_state(AdminClean.choose_action)
    await message.answer(
        "🧹 Xotirani tozalash bo‘limi.\n\n"
        "Nimani qilamiz?",
        reply_markup=admin_clean_kb()
    )


# --------- Admin: user delate  ---------
@dp.message(AdminClean.choose_action, F.text == "⬅️ Orqaga")
async def admin_clean_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Admin panel.", reply_markup=admin_kb())


@dp.message(AdminClean.choose_action, F.text == "👤 Userni o‘chirish")
async def admin_delete_user_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, ADMINS):
        return

    users = db.list_users_simple()
    if not users:
        await message.answer("Hali userlar yo‘q.", reply_markup=admin_clean_kb())
        return

    # Tartib raqami bilan chiqaramiz (1..N)
    lines = ["👤 O‘chirmoqchi bo‘lgan user raqamini kiriting:\n"]
    for i, u in enumerate(users, start=1):
        lines.append(f"{i}. {u['full_name']}")

    # mappingni state’da saqlaymiz: index -> user_id
    index_map = {str(i): u["id"] for i, u in enumerate(users, start=1)}
    await state.update_data(delete_index_map=index_map)

    await state.set_state(AdminClean.input_user_number)
    await message.answer("\n".join(lines))


# --------- Admin: user delate + tasdiqlash  ---------
@dp.message(AdminClean.input_user_number, F.text)
async def admin_delete_user_pick(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, ADMINS):
        return

    num = message.text.strip()
    data = await state.get_data()
    index_map = data.get("delete_index_map", {})

    if num not in index_map:
        await message.answer("❗ Noto‘g‘ri raqam. Ro‘yxatdagi raqamni kiriting.")
        return

    user_id = index_map[num]
    # user nomini topamiz (chiroyli tasdiq uchun)
    users = db.list_users_simple()
    target_name = next((u["full_name"] for u in users if u["id"] == user_id), "User")

    await state.update_data(target_user_id=user_id, target_name=target_name)
    await state.set_state(AdminClean.confirm_delete_user)

    await message.answer(
        f"⚠️ Rostdan ham quyidagi userni o‘chirmoqchimisiz?\n\n"
        f"#{num} — {target_name}\n\n"
        f"Bu userning davomat/vazifa tarixlari ham o‘chadi.",
        reply_markup=confirm_yes_no_kb()
    )


@dp.message(AdminClean.confirm_delete_user, F.text.in_({"✅ Ha", "❌ Yo‘q"}))
async def admin_delete_user_confirm(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, ADMINS):
        return

    if message.text == "❌ Yo‘q":
        await state.set_state(AdminClean.choose_action)
        await message.answer("Bekor qilindi.", reply_markup=admin_clean_kb())
        return

    data = await state.get_data()
    user_id = data["target_user_id"]
    target_name = data.get("target_name", "User")

    db.delete_user_by_id(user_id)

    await state.set_state(AdminClean.choose_action)
    await message.answer(f"✅ O‘chirildi: {target_name}", reply_markup=admin_clean_kb())


# --------- Admin: Barchasini o‘chirish  ---------
@dp.message(AdminClean.choose_action, F.text == "🗑 Barchasini o‘chirish")
async def admin_delete_all_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, ADMINS):
        return

    await state.set_state(AdminClean.confirm_delete_all)
    await message.answer(
        "⚠️ DIQQAT!\n\n"
        "Hamma userlar, darslar, davomat va vazifa tarixlari to‘liq o‘chadi.\n"
        "Keyin hammasi yangidan boshlanadi.\n\n"
        "Rostdan ham davom etamizmi?",
        reply_markup=confirm_yes_no_kb()
    )


@dp.message(AdminClean.confirm_delete_all, F.text.in_({"✅ Ha", "❌ Yo‘q"}))
async def admin_delete_all_confirm(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, ADMINS):
        return

    if message.text == "❌ Yo‘q":
        await state.set_state(AdminClean.choose_action)
        await message.answer("Bekor qilindi.", reply_markup=admin_clean_kb())
        return

    db.wipe_all_data()
    await state.clear()
    await message.answer("✅ Database tozalandi. Endi yangidan boshlashingiz mumkin.", reply_markup=admin_kb())


# --------- Admin: dars boshlash ---------
@dp.message(F.text == "🎬 Dars boshlash")
async def admin_start_lesson(message: Message):
    tg_id = message.from_user.id
    if not is_admin(tg_id, ADMINS):
        return

    token = gen_token()
    start_at = now_uz().isoformat()
    lesson = db.create_lesson(token, start_at, tg_id)

    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=lesson_{lesson['token']}"

    await message.answer(
        "✅ Dars boshlandi.\n"
        "Kanalga quyidagi linkni tashlang:\n"
        f"{link}"
    )


@dp.message(F.text == "📈 Statiskani ko‘rish")
async def admin_stats_menu(message: Message):
    tg_id = message.from_user.id
    if not is_admin(tg_id, ADMINS):
        return
    await message.answer("Qaysi statistikani ko‘rasiz?", reply_markup=admin_stats_inline())


# --------- Deep-link handler logic ---------
async def handle_lesson_payload(message: Message, payload: str, user_id: int, full_name: str):
    token = payload.replace("lesson_", "", 1)
    lesson = db.get_lesson_by_token(token)
    if not lesson:
        await message.answer("⚠️ Link eskirgan yoki noto‘g‘ri.")
        return

    attendance_hours, _ = db.get_limits()

    start_at = datetime.fromisoformat(lesson["start_at"]).astimezone(UZ_TZ)
    delta = now_uz() - start_at

    if delta <= timedelta(hours=attendance_hours):
        # ✅ BOR + ✅ VAZIFA avtomatik
        db.upsert_attendance(lesson["id"], user_id, "ON_TIME", now_uz().isoformat())
        db.upsert_homework(lesson["id"], user_id, "DONE", now_uz().isoformat())
        await message.answer("✅ Davomat qo‘yildi va vazifa ham avtomatik belgilandi.")
    else:
        # Vaqt o'tib ketgan -> davomat hisoblanmaydi
        # xohlasangiz log uchun LATE yozib qo'yamiz (statistikada alohida ko‘rsatish mumkin)
        db.upsert_attendance(lesson["id"], user_id, "LATE", now_uz().isoformat())
        await message.answer(
            f"🕒 Kechikdingiz.\n"
            f"Davomat {attendance_hours} soat ichida qo‘yiladi.\n"
            f"Agar darsga kira olmagan bo‘lsangiz, vazifani belgilash bo‘limidan (muddat ichida) belgilashingiz mumkin."
        )


# --------- User: davomat tugmasi ---------
@dp.message(F.text == "✅ Davomatni belgilash")
async def user_mark_attendance(message: Message):
    tg_id = message.from_user.id
    user = db.get_user_by_tg(tg_id)
    if not user:
        await message.answer("Avval /start bosing va ro‘yxatdan o‘ting.")
        return

    lesson = db.get_active_lesson()
    if not lesson:
        await message.answer("⬛️ Hozircha dars ochilmagan. (Admin dars boshlashi kerak.)")
        return

    start_at = datetime.fromisoformat(lesson["start_at"])
    delta = now_uz() - start_at
    get_time = db.get_limits()[0]
    if delta <= timedelta(hours=get_time):
        status = "ON_TIME"
        text = "✅ Davomatingiz belgilandi."
    else:
        status = "LATE"
        text = "🕒 Davomatingiz belgilandi (kech)."

    db.upsert_attendance(lesson["id"], user["id"], status, now_uz().isoformat())
    await message.answer(text)


# --------- User: vazifa tugmasi ---------
@dp.message(F.text == "📝 Vazifani belgilash")
async def user_mark_homework(message: Message):
    tg_id = message.from_user.id
    user = db.get_user_by_tg(tg_id)
    if not user:
        await message.answer("Avval /start bosing va ro‘yxatdan o‘ting.")
        return

    _, homework_days = db.get_limits()

    end_day = now_uz().date()
    start_day = end_day - timedelta(days=homework_days)

    start_iso = datetime.combine(start_day, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    end_iso = datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=UZ_TZ).isoformat()

    lessons = db.get_lessons_between(start_iso, end_iso)
    if not lessons:
        await message.answer("Hozircha tanlanadigan dars yo‘q.")
        return

    # 1 kunda 1 dars: shu sananing oxirgisini olamiz
    lesson_by_day = {}
    for l in lessons:
        d = to_date(l["start_at"])
        lesson_by_day[d] = l

    lesson_days = sorted(lesson_by_day.keys())
    lesson_ids = [lesson_by_day[d]["id"] for d in lesson_days]

    att_map = db.get_attendance_map(lesson_ids)
    hw_map = db.get_homework_map(lesson_ids)

    eligible = []
    n = 1
    for d in lesson_days:
        lesson_id = lesson_by_day[d]["id"]
        att = att_map.get((lesson_id, user["id"]))
        hw = hw_map.get((lesson_id, user["id"]))

        # ✅ qoida: davomat yo‘q (ON_TIME emas) va vazifa ham hali yo‘q bo‘lsa tanlanadi
        attended = att and att["att_status"] == "ON_TIME"
        if (not attended) and (not hw):
            eligible.append((lesson_id, f"{n}-dars > {d.strftime('%d.%m.%Y')}"))
            n += 1

    if not eligible:
        await message.answer(f"✅ Sizda {homework_days} kun ichida vazifa belgilash kerak bo‘lgan dars yo‘q.")
        return

    await message.answer(
        f"📝 Qaysi darsning vazifasini belgilaysiz?\n"
        f"(muddat: {homework_days} kun)",
        reply_markup=hw_lessons_inline(eligible)
    )

@dp.callback_query(F.data.startswith("hwmark:"))
async def user_hw_mark_callback(call: CallbackQuery):
    tg_id = call.from_user.id
    user = db.get_user_by_tg(tg_id)
    if not user:
        await call.answer("Avval /start bosing.", show_alert=True)
        return

    lesson_id = int(call.data.split(":", 1)[1])

    # muddat tekshirish (Y kun)
    _, homework_days = db.get_limits()
    lesson = None
    # tez topish uchun token emas, id bo‘yicha olish yo‘q edi — oson yo‘l:
    # get_lessons_between orqali tekshiramiz
    end_day = now_uz().date()
    start_day = end_day - timedelta(days=homework_days)
    start_iso = datetime.combine(start_day, datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    end_iso = datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=UZ_TZ).isoformat()
    lessons = db.get_lessons_between(start_iso, end_iso)
    lesson_ids = {l["id"] for l in lessons}
    if lesson_id not in lesson_ids:
        await call.answer("⛔ Muddat tugagan yoki dars topilmadi.", show_alert=True)
        return

    # agar allaqachon belgilangan bo‘lsa
    if db.get_homework(lesson_id, user["id"]):
        await call.answer("Bu dars uchun vazifa allaqachon belgilangan.", show_alert=True)
        return

    db.upsert_homework(lesson_id, user["id"], "DONE_WITHOUT_ATTENDANCE", now_uz().isoformat())
    await call.answer("✅ Vazifa belgilandi.")
    await call.message.answer("✅ Tanlangan dars uchun vazifa belgilandi.")
# --------- User: shaxsiy statistika ---------
@dp.message(F.text == "📊 Statiskamni ko‘rish")
async def user_my_stats(message: Message):
    tg_id = message.from_user.id
    user = db.get_user_by_tg(tg_id)
    if not user:
        await message.answer("Avval /start bosing va ro‘yxatdan o‘ting.")
        return

    await message.answer("Qaysi statistikani ko‘rasiz?", reply_markup=user_stats_inline())


@dp.callback_query(F.data.startswith("mystats:"))
async def user_stats_callback(call: CallbackQuery):
    tg_id = call.from_user.id
    user = db.get_user_by_tg(tg_id)
    if not user:
        await call.answer("Avval /start bosing.", show_alert=True)
        return

    period = call.data.split(":", 1)[1]
    await call.answer()

    today = now_uz().date()
    user_id = user["id"]
    full_name = user["full_name"]

    if period == "today":
        text = build_my_today(db, user_id, full_name, today)
    elif period == "week":
        text = build_my_week(db, user_id, full_name, today)
    elif period == "upto":
        text = build_my_upto(db, user_id, full_name, today)
    else:  # month
        text = build_my_month(db, user_id, full_name, today)

    # ✅ None-safe
    if not text:
        text = "⚠️ Statistika topilmadi (hali darslar yo‘q yoki ma’lumot yetarli emas)."

    for chunk in [text[i:i + 3500] for i in range(0, len(text), 3500)]:
        await call.message.answer(chunk)


# --------- Admin stats callbacks (keyin to‘liq jadval) ---------
@dp.callback_query(F.data.startswith("stats:"))
async def admin_stats_callback(call: CallbackQuery):
    if not is_admin(call.from_user.id, ADMINS):
        await call.answer("Ruxsat yo‘q.", show_alert=True)
        return

    period = call.data.split(":", 1)[1]
    await call.answer()

    today = now_uz().date()
    if period == "today":
        text = build_today_report(db, today)
        for chunk in [text[i:i + 3500] for i in range(0, len(text), 3500)]:
            await call.message.answer(chunk)
        return

    if period == "month":
        text = build_month_report(db, today)
        if not text:
            text = "⚠️ Hisobot topilmadi."
        for chunk in [text[i:i + 3500] for i in range(0, len(text), 3500)]:
            await call.message.answer(chunk)
        return
    if period == "upto":
        text = build_upto_report(db, today)
        for chunk in [text[i:i + 3500] for i in range(0, len(text), 3500)]:
            await call.message.answer(chunk)
        return
    if period == "week":
        text = build_week_report(db, today)
        # Juda uzun bo‘lsa, bo‘lib yuboramiz (Telegram limit)
        for chunk in [text[i:i + 3500] for i in range(0, len(text), 3500)]:
            await call.message.answer(chunk)
    if period == "month_points":
        text = build_month_points_report(db, today)
        if not text:
            text = "⚠️ Hisobot topilmadi."
        for chunk in [text[i:i + 3500] for i in range(0, len(text), 3500)]:
            await call.message.answer(chunk)
        return
    elif period == "month":
        await call.message.answer("🌙 Oylik statistika: keyingi bosqichda (haftalik ishlasa, oylik ham shu prinsipda).")
    else:
        await call.message.answer("📅 Bugungi statistika: keyingi bosqichda.")

@dp.message(F.text == "⚙️ Cheklovlar")
async def admin_limits_menu(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id, ADMINS):
        return
    att_h, hw_d = db.get_limits()
    await state.set_state(AdminLimits.menu)
    await message.answer("⚙️ Cheklovlar:", reply_markup=admin_limits_kb(att_h, hw_d))

@dp.message(AdminLimits.menu, F.text == "⬅️ Orqaga")
async def admin_limits_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Admin panel.", reply_markup=admin_kb())

@dp.message(AdminLimits.menu, F.text.startswith("⏱ Davomat oynasi"))
async def admin_limits_att_start(message: Message, state: FSMContext):
    await state.set_state(AdminLimits.set_att_hours)
    await message.answer("Yangi qiymatni kiriting (soat). Masalan: 1, 2, 3, 4")

@dp.message(AdminLimits.set_att_hours, F.text)
async def admin_limits_att_set(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat son kiriting. Masalan: 2")
        return
    val = int(message.text)
    if val < 1 or val > 24:
        await message.answer("1 dan 24 gacha kiriting.")
        return
    db.set_setting("attendance_hours", str(val))
    att_h, hw_d = db.get_limits()
    await state.set_state(AdminLimits.menu)
    await message.answer("✅ Saqlandi.", reply_markup=admin_limits_kb(att_h, hw_d))

@dp.message(AdminLimits.menu, F.text.startswith("📆 Vazifa muddati"))
async def admin_limits_hw_start(message: Message, state: FSMContext):
    await state.set_state(AdminLimits.set_hw_days)
    await message.answer("Yangi qiymatni kiriting (kun). Masalan: 2, 3, 5")

@dp.message(AdminLimits.set_hw_days, F.text)
async def admin_limits_hw_set(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat son kiriting. Masalan: 2")
        return
    val = int(message.text)
    if val < 1 or val > 30:
        await message.answer("1 dan 30 gacha kiriting.")
        return
    db.set_setting("homework_days", str(val))
    att_h, hw_d = db.get_limits()
    await state.set_state(AdminLimits.menu)
    await message.answer("✅ Saqlandi.", reply_markup=admin_limits_kb(att_h, hw_d))
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    print("Bot ishga tushdi")
    asyncio.run(main())
