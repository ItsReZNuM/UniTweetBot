import sqlite3
import datetime
import json
from config import DATABASE_NAME

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
            status TEXT, -- pending, approved, rejected
            approved_hour INTEGER,
            admin_msg_id INTEGER,
            rejection_reason TEXT,
            submission_date TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduler (
            hour INTEGER PRIMARY KEY,
            tweet_ids TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def save_user(user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user.id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (id, first_name, username, join_date) VALUES (?, ?, ?, ?)",
                       (user.id, user.first_name, user.username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

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


def submit_tweet(user_id, text, admin_msg_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tweets (user_id, text, status, admin_msg_id, submission_date) VALUES (?, ?, 'pending', ?, ?)",
                   (user_id, text, admin_msg_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    tweet_id = cursor.lastrowid
    conn.execute("UPDATE users SET tweets = tweets + 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return tweet_id



def get_tweet_by_admin_msg_id(admin_msg_id):
    conn = get_db_connection()
    tweet = conn.execute("SELECT * FROM tweets WHERE admin_msg_id = ?", (admin_msg_id,)).fetchone()
    conn.close()
    return dict(tweet) if tweet else None

def approve_tweet(tweet_id, hour):
    conn = get_db_connection()
    conn.execute("UPDATE tweets SET status = 'approved', approved_hour = ? WHERE id = ?", (hour, tweet_id))
    
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

def reject_tweet(tweet_id, reason):
    conn = get_db_connection()
    conn.execute("UPDATE tweets SET status = 'rejected', rejection_reason = ? WHERE id = ?", (reason, tweet_id))
    conn.execute("UPDATE users SET failed_tweets = failed_tweets + 1 WHERE id = (SELECT user_id FROM tweets WHERE id = ?)", (tweet_id,))
    conn.commit()
    conn.close()

def update_tweet_text(tweet_id, new_text):
    conn = get_db_connection()
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


# فصد داشتم فیچر انتقال و حذف ساعت اضافه کنم ، ولی حوصله نداشتم این رو میتونی کلا پاک کنی 
def remove_schedule_hour(hour_to_remove, hour_to_transfer):
    conn = get_db_connection()
    cursor = conn.cursor()

    row = cursor.execute("SELECT tweet_ids FROM scheduler WHERE hour = ?", (hour_to_remove,)).fetchone()
    removed_ids = []

    # بررسی ایمن‌تر JSON
    if row and row['tweet_ids']:
        try:
            removed_ids = json.loads(row['tweet_ids'])
        except json.JSONDecodeError:
            removed_ids = []

    if not removed_ids:
        conn.execute("DELETE FROM scheduler WHERE hour = ?", (hour_to_remove,))
        conn.commit()
        conn.close()
        return

    # حذف ساعت مبدأ
    conn.execute("DELETE FROM scheduler WHERE hour = ?", (hour_to_remove,))

    # انتقال به ساعت مقصد
    placeholders = ','.join(['?'] * len(removed_ids))
    params = (hour_to_transfer, *removed_ids)
    conn.execute(f"UPDATE tweets SET approved_hour = ? WHERE id IN ({placeholders})", params)

    # افزودن به ساعت مقصد
    target_row = cursor.execute("SELECT tweet_ids FROM scheduler WHERE hour = ?", (hour_to_transfer,)).fetchone()
    target_ids = []
    if target_row and target_row['tweet_ids']:
        try:
            target_ids = json.loads(target_row['tweet_ids'])
        except json.JSONDecodeError:
            target_ids = []

    new_ids = list(set(target_ids + removed_ids))

    if target_row:
        conn.execute("UPDATE scheduler SET tweet_ids = ? WHERE hour = ?", (json.dumps(new_ids), hour_to_transfer))
    else:
        conn.execute("INSERT INTO scheduler (hour, tweet_ids) VALUES (?, ?)", (hour_to_transfer, json.dumps(new_ids)))

    conn.commit()
    conn.close()
