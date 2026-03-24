# db.py
import sqlite3
from datetime import datetime

class DB:
    def __init__(self, path="bot.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)
        cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('attendance_hours','2')")
        cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('homework_days','2')")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            start_at TEXT NOT NULL,
            created_by_admin_tg_id INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            att_status TEXT NOT NULL,
            marked_at TEXT NOT NULL,
            UNIQUE(lesson_id, user_id)
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            hw_status TEXT NOT NULL,
            marked_at TEXT NOT NULL,
            UNIQUE(lesson_id, user_id)
        )
        """)

        self.conn.commit()

    # ---------- users ----------
    def get_user_by_tg(self, tg_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
        return cur.fetchone()

    def create_user(self, tg_id: int, full_name: str, created_at: str):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO users(tg_id, full_name, created_at) VALUES(?,?,?)",
            (tg_id, full_name, created_at),
        )
        self.conn.commit()
        return self.get_user_by_tg(tg_id)

    def list_users(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users ORDER BY created_at ASC")
        return cur.fetchall()

    # ---------- lessons ----------
    def deactivate_all_lessons(self):
        cur = self.conn.cursor()
        cur.execute("UPDATE lessons SET is_active=0 WHERE is_active=1")
        self.conn.commit()

    def create_lesson(self, token: str, start_at: str, admin_tg_id: int):
        self.deactivate_all_lessons()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO lessons(token, start_at, created_by_admin_tg_id, is_active) VALUES(?,?,?,1)",
            (token, start_at, admin_tg_id),
        )
        self.conn.commit()
        return self.get_lesson_by_token(token)

    def get_active_lesson(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM lessons WHERE is_active=1 ORDER BY id DESC LIMIT 1")
        return cur.fetchone()

    def get_lesson_by_token(self, token: str):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM lessons WHERE token=?", (token,))
        return cur.fetchone()

    # ---------- attendance ----------
    def upsert_attendance(self, lesson_id: int, user_id: int, att_status: str, marked_at: str):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO attendance(lesson_id, user_id, att_status, marked_at)
            VALUES(?,?,?,?)
            ON CONFLICT(lesson_id, user_id) DO UPDATE SET
              att_status=excluded.att_status,
              marked_at=excluded.marked_at
        """, (lesson_id, user_id, att_status, marked_at))
        self.conn.commit()

    def get_attendance(self, lesson_id: int, user_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM attendance WHERE lesson_id=? AND user_id=?", (lesson_id, user_id))
        return cur.fetchone()

    # ---------- homework ----------
    def upsert_homework(self, lesson_id: int, user_id: int, hw_status: str, marked_at: str):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO homework(lesson_id, user_id, hw_status, marked_at)
            VALUES(?,?,?,?)
            ON CONFLICT(lesson_id, user_id) DO UPDATE SET
              hw_status=excluded.hw_status,
              marked_at=excluded.marked_at
        """, (lesson_id, user_id, hw_status, marked_at))
        self.conn.commit()

    def get_homework(self, lesson_id: int, user_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM homework WHERE lesson_id=? AND user_id=?", (lesson_id, user_id))
        return cur.fetchone()

    def get_lessons_between(self, start_iso: str, end_iso: str):
        """
        start_iso inclusive, end_iso exclusive
        """
        cur = self.conn.cursor()
        cur.execute("""
               SELECT * FROM lessons
               WHERE start_at >= ? AND start_at < ?
               ORDER BY start_at ASC
           """, (start_iso, end_iso))
        return cur.fetchall()

    def get_attendance_map(self, lesson_ids: list[int]):
        """
        returns dict[(lesson_id, user_id)] = row
        """
        if not lesson_ids:
            return {}
        q = ",".join(["?"] * len(lesson_ids))
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM attendance WHERE lesson_id IN ({q})", lesson_ids)
        rows = cur.fetchall()
        return {(r["lesson_id"], r["user_id"]): r for r in rows}

    def get_homework_map(self, lesson_ids: list[int]):
        """
        returns dict[(lesson_id, user_id)] = row
        """
        if not lesson_ids:
            return {}
        q = ",".join(["?"] * len(lesson_ids))
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM homework WHERE lesson_id IN ({q})", lesson_ids)
        rows = cur.fetchall()
        return {(r["lesson_id"], r["user_id"]): r for r in rows}

    def list_users_simple(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, full_name FROM users ORDER BY full_name ASC")
        return cur.fetchall()

    def get_first_lesson(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM lessons ORDER BY start_at ASC LIMIT 1")
        return cur.fetchone()

    def get_lessons_on_date(self, day_start_iso: str, day_end_iso: str):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM lessons
            WHERE start_at >= ? AND start_at < ?
            ORDER BY start_at ASC
        """, (day_start_iso, day_end_iso))
        return cur.fetchall()

    def get_last_lesson_on_date(self, day_start_iso: str, day_end_iso: str):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM lessons
            WHERE start_at >= ? AND start_at < ?
            ORDER BY start_at DESC
            LIMIT 1
        """, (day_start_iso, day_end_iso))
        return cur.fetchone()

    def delete_user_by_id(self, user_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM attendance WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM homework WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.conn.commit()

    def wipe_all_data(self):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM attendance")
        cur.execute("DELETE FROM homework")
        cur.execute("DELETE FROM lessons")
        cur.execute("DELETE FROM users")
        # autoincrementni ham yangidan boshlatish (ixtiyoriy, lekin yaxshi)
        cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('attendance','homework','lessons','users')")
        self.conn.commit()

    def get_setting(self, key: str, default: str = "") -> str:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO settings(key,value) VALUES(?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        self.conn.commit()

    def get_limits(self) -> tuple[int, int]:
        att_h = int(self.get_setting("attendance_hours", "2"))
        hw_d = int(self.get_setting("homework_days", "2"))
        return att_h, hw_d


