import sqlite3
import datetime
import json
from config import DATABASE_NAME, ADMIN_USER_IDS, ADMIN_ID

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            tweets INTEGER DEFAULT 0,
            success_tweets INTEGER DEFAULT 0,
            failed_tweets INTEGER DEFAULT 0,
            join_date TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tweets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            status TEXT, -- pending, approved, rejected, sent
            approved_hour INTEGER,
            admin_msg_id INTEGER,
            rejection_reason TEXT,
            reply_info TEXT,
            handled_by TEXT,
            submission_date TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduler (
            hour INTEGER PRIMARY KEY,
            tweet_ids TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            added_by INTEGER,
            added_date TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tweet_admin_messages (
            tweet_id INTEGER,
            admin_id INTEGER,
            message_id INTEGER,
            PRIMARY KEY (tweet_id, admin_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    conn.commit()
    _migrate_db(conn)
    conn.close()

def _migrate_db(conn):
    cursor = conn.cursor()
    try:
        if ADMIN_ID:
            cursor.execute("SELECT id, admin_msg_id FROM tweets WHERE admin_msg_id IS NOT NULL AND admin_msg_id != 0")
            rows = cursor.fetchall()
            for r in rows:
                cursor.execute("""
                    INSERT OR IGNORE INTO tweet_admin_messages (tweet_id, admin_id, message_id)
                    VALUES (?, ?, ?)
                """, (r['id'], ADMIN_ID, r['admin_msg_id']))
            conn.commit()
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE tweets ADD COLUMN reply_info TEXT")
        conn.commit()
    except Exception:
        pass

    # مایگریشن خودکار برای ستون ادمینِ اقدام‌کننده
    try:
        cursor.execute("ALTER TABLE tweets ADD COLUMN handled_by TEXT")
        conn.commit()
    except Exception:
        pass

# ====================
# مدیریت تنظیمات
# ====================
def get_setting(key, default=None):
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# ====================
# مدیریت ادمین‌ها
# ====================
def is_superadmin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS

def get_db_admins():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM admins ORDER BY added_date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_admins():
    conn = get_db_connection()
    rows = conn.execute("SELECT id FROM admins").fetchall()
    conn.close()
    db_ids = [r['id'] for r in rows]
    return list(set(ADMIN_USER_IDS + db_ids))

def is_admin(user_id: int) -> bool:
    return user_id in get_all_admins()

def add_admin(user_id: int, added_by: int = None, username: str = None, first_name: str = None) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute("""
            INSERT INTO admins (id, username, first_name, added_by, added_date)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, first_name, added_by, now))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def remove_admin(user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE id = ?", (user_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

# ====================
# پیام‌های ادمین‌ها برای هر توییت
# ====================
def save_tweet_admin_message(tweet_id: int, admin_id: int, message_id: int):
    conn = get_db_connection()
    conn.execute("""
        INSERT OR REPLACE INTO tweet_admin_messages (tweet_id, admin_id, message_id)
        VALUES (?, ?, ?)
    """, (tweet_id, admin_id, message_id))
    conn.commit()
    conn.close()

def get_tweet_admin_messages(tweet_id: int):
    conn = get_db_connection()
    rows = conn.execute("SELECT admin_id, message_id FROM tweet_admin_messages WHERE tweet_id = ?", (tweet_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_other_admin_messages(tweet_id: int, current_admin_id: int):
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT admin_id, message_id FROM tweet_admin_messages 
        WHERE tweet_id = ? AND admin_id != ?
    """, (tweet_id, current_admin_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ====================
# عملیات توییت‌ها و کاربران
# ====================
def save_user(user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user.id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (id, first_name, username, join_date) VALUES (?, ?, ?, ?)",
                       (user.id, user.first_name, user.username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_user_by_id(user_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_id_by_tweet(tweet_id):
    conn = get_db_connection()
    row = conn.execute("SELECT user_id FROM tweets WHERE id = ?", (tweet_id,)).fetchone()
    conn.close()
    return row['user_id'] if row else None

def get_total_success_tweets():
    conn = get_db_connection()
    row = conn.execute("SELECT COUNT(*) AS count FROM tweets WHERE status = 'approved' OR status = 'sent'").fetchone()
    conn.close()
    return row['count'] if row else 0

def get_total_failed_tweets():
    conn = get_db_connection()
    row = conn.execute("SELECT COUNT(*) AS count FROM tweets WHERE status = 'rejected'").fetchone()
    conn.close()
    return row['count'] if row else 0

def submit_tweet(user_id, text, admin_msg_id=0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tweets (user_id, text, status, admin_msg_id, submission_date) VALUES (?, ?, 'pending', ?, ?)",
                   (user_id, text, admin_msg_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    tweet_id = cursor.lastrowid
    conn.execute("UPDATE users SET tweets = tweets + 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return tweet_id

def get_tweet_by_id(tweet_id):
    conn = get_db_connection()
    tweet = conn.execute("SELECT * FROM tweets WHERE id = ?", (tweet_id,)).fetchone()
    conn.close()
    return dict(tweet) if tweet else None

def get_tweet_by_admin_msg_id(admin_msg_id):
    conn = get_db_connection()
    tweet = conn.execute("SELECT * FROM tweets WHERE admin_msg_id = ?", (admin_msg_id,)).fetchone()
    conn.close()
    return dict(tweet) if tweet else None

def approve_tweet(tweet_id, hour, handled_by=None):
    conn = get_db_connection()
    conn.execute("UPDATE tweets SET status = 'approved', approved_hour = ?, handled_by = ? WHERE id = ?", (hour, handled_by, tweet_id))
    
    cursor = conn.cursor()
    cursor.execute("SELECT tweet_ids FROM scheduler WHERE hour = ?", (hour,))
    row = cursor.fetchone()
    if row:
        tweet_ids = json.loads(row['tweet_ids'])
        if tweet_id not in tweet_ids:
            tweet_ids.append(tweet_id)
        conn.execute("UPDATE scheduler SET tweet_ids = ? WHERE hour = ?", (json.dumps(tweet_ids), hour))
    else:
        conn.execute("INSERT INTO scheduler (hour, tweet_ids) VALUES (?, ?)", (hour, json.dumps([tweet_id])))
        
    conn.commit()
    conn.close()

def unapprove_tweet(tweet_id: int, handled_by: str = None) -> int | None:
    """Remove approved tweet from scheduler and mark as removed"""
    conn = get_db_connection()
    cursor = conn.cursor()
    tweet = cursor.execute("SELECT approved_hour, handled_by FROM tweets WHERE id = ?", (tweet_id,)).fetchone()
    if not tweet:
        conn.close()
        return None

    hour = tweet['approved_hour']
    if hour is not None:
        row = cursor.execute("SELECT tweet_ids FROM scheduler WHERE hour = ?", (hour,)).fetchone()
        if row and row['tweet_ids']:
            try:
                tweet_ids = json.loads(row['tweet_ids'])
                if tweet_id in tweet_ids:
                    tweet_ids.remove(tweet_id)
                    cursor.execute("UPDATE scheduler SET tweet_ids = ? WHERE hour = ?", (json.dumps(tweet_ids), hour))
            except Exception:
                pass

    admin_tag = handled_by or tweet['handled_by']
    cursor.execute("UPDATE tweets SET status = 'removed', handled_by = ? WHERE id = ?", (admin_tag, tweet_id))
    conn.commit()
    conn.close()
    return hour

def reject_tweet(tweet_id, reason, handled_by=None):
    conn = get_db_connection()
    conn.execute("UPDATE tweets SET status = 'rejected', rejection_reason = ?, handled_by = ? WHERE id = ?", (reason, handled_by, tweet_id))
    conn.execute("UPDATE users SET failed_tweets = failed_tweets + 1 WHERE id = (SELECT user_id FROM tweets WHERE id = ?)", (tweet_id,))
    conn.commit()
    conn.close()

def update_tweet_reply(tweet_id, reply_info, handled_by=None):
    conn = get_db_connection()
    if handled_by:
        conn.execute("UPDATE tweets SET reply_info = ?, handled_by = ? WHERE id = ?", (reply_info, handled_by, tweet_id))
    else:
        conn.execute("UPDATE tweets SET reply_info = ? WHERE id = ?", (reply_info, tweet_id))
    conn.commit()
    conn.close()

def update_tweet_text(tweet_id, new_text, handled_by=None):
    conn = get_db_connection()
    if handled_by:
        conn.execute("UPDATE tweets SET text = ?, handled_by = ? WHERE id = ?", (new_text, handled_by, tweet_id))
    else:
        conn.execute("UPDATE tweets SET text = ? WHERE id = ?", (new_text, tweet_id))
    conn.commit()
    conn.close()

def get_all_users_id():
    conn = get_db_connection()
    ids = [row['id'] for row in conn.execute("SELECT id FROM users").fetchall()]
    conn.close()
    return ids

def get_all_scheduler_hours():
    conn = get_db_connection()
    hours = [row['hour'] for row in conn.execute("SELECT hour FROM scheduler ORDER BY hour").fetchall()]
    conn.close()
    return hours

def add_schedule_hour(hour):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO scheduler (hour, tweet_ids) VALUES (?, ?)", (hour, json.dumps([])))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_scheduler_tweet_ids(hour: int) -> list:
    conn = get_db_connection()
    row = conn.execute("SELECT tweet_ids FROM scheduler WHERE hour = ?", (hour,)).fetchone()
    conn.close()
    if not row or not row['tweet_ids']:
        return []
    try:
        return json.loads(row['tweet_ids'])
    except Exception:
        return []

def get_scheduler_tweet_count(hour: int) -> int:
    return len(get_scheduler_tweet_ids(hour))

def delete_schedule_hour(source_hour: int, target_hour: int | None = None) -> tuple[bool, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT tweet_ids FROM scheduler WHERE hour = ?", (source_hour,)).fetchone()
    if not row:
        conn.close()
        return False, "ساعت مبدا یافت نشد."
    try:
        source_ids = json.loads(row['tweet_ids']) if row['tweet_ids'] else []
    except Exception:
        source_ids = []

    if source_ids and target_hour is not None:
        if source_hour == target_hour:
            conn.close()
            return False, "ساعت مقصد نمی‌تواند همان ساعت مبدا باشد."
        target_row = cursor.execute("SELECT tweet_ids FROM scheduler WHERE hour = ?", (target_hour,)).fetchone()
        if not target_row:
            conn.close()
            return False, "ساعت مقصد یافت نشد."
        try:
            target_ids = json.loads(target_row['tweet_ids']) if target_row['tweet_ids'] else []
        except Exception:
            target_ids = []
        merged = target_ids + [tid for tid in source_ids if tid not in target_ids]
        cursor.execute("UPDATE scheduler SET tweet_ids = ? WHERE hour = ?", (json.dumps(merged), target_hour))
        for tid in source_ids:
            cursor.execute("UPDATE tweets SET approved_hour = ? WHERE id = ? AND status IN ('approved','sent')", (target_hour, tid))

    cursor.execute("DELETE FROM scheduler WHERE hour = ?", (source_hour,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return (True, "ok") if deleted else (False, "حذف انجام نشد.")

def get_available_hours() -> list[int]:
    existing = set(get_all_scheduler_hours())
    return [h for h in range(24) if h not in existing]

def get_daily_stats():
    conn = get_db_connection()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    row = conn.execute("SELECT COUNT(*) AS count FROM tweets WHERE DATE(submission_date) = ?", (today,)).fetchone()
    conn.close()
    return row['count'] if row else 0

def get_weekly_stats():
    conn = get_db_connection()
    one_week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    row = conn.execute("SELECT COUNT(*) AS count FROM tweets WHERE DATE(submission_date) >= ?", (one_week_ago,)).fetchone()
    conn.close()
    return row['count'] if row else 0

def get_monthly_stats():
    conn = get_db_connection()
    one_month_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    row = conn.execute("SELECT COUNT(*) AS count FROM tweets WHERE DATE(submission_date) >= ?", (one_month_ago,)).fetchone()
    conn.close()
    return row['count'] if row else 0

def get_top_users(limit=5):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT username, success_tweets FROM users WHERE success_tweets > 0 ORDER BY success_tweets DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [{"username": r['username'] or f'کاربر {r["success_tweets"]}', "count": r['success_tweets']} for r in rows]