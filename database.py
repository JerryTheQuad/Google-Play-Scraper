# database.py
import sqlite3
from datetime import datetime

DB_PATH = "developers.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS apps (
            developer_id TEXT,
            country TEXT,
            app_id TEXT,
            title TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP,
            notified INTEGER DEFAULT 0,
            PRIMARY KEY (developer_id, country, app_id)
        )
    ''')
    conn.commit()
    conn.close()

def get_known_apps(developer_id: str, country: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT app_id FROM apps WHERE developer_id = ? AND country = ?",
        (developer_id, country)
    )
    known = {row[0] for row in cursor.fetchall()}
    conn.close()
    return known

def save_new_app(developer_id: str, country: str, app_id: str, title: str):
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat()
    conn.execute('''
        INSERT INTO apps (developer_id, country, app_id, title, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(developer_id, country, app_id) DO UPDATE
        SET last_seen = ?, title = ?
    ''', (developer_id, country, app_id, title, now, now, title))
    conn.commit()
    conn.close()