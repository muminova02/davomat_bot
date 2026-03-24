from datetime import datetime, timedelta, timezone
import secrets

UZ_TZ = timezone(timedelta(hours=5))

def now_uz():
    return datetime.now(tz=UZ_TZ)

def gen_token():
    return secrets.token_urlsafe(16)

def is_admin(tg_id: int, admins: set[int]) -> bool:
    return tg_id in admins