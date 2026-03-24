from dotenv import load_dotenv
import os

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH")
ADMINS = {int(x) for x in os.getenv("ADMINS", "").split(",") if x.strip().isdigit()}
TIMEZONE_OFFSET_HOURS = 5
ATTENDANCE_LATE_HOURS = 2