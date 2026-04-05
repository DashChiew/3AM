import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "instance", "3am.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN is_anonymous BOOLEAN DEFAULT 0;")
        conn.commit()
        print("Added is_anonymous to chat_messages in 3am.db")
    except sqlite3.OperationalError as e:
        print(f"3am.db error: {e}")
    conn.close()

db_path2 = os.path.join(os.path.dirname(__file__), "instance", "app.db")
if os.path.exists(db_path2):
    conn = sqlite3.connect(db_path2)
    try:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN is_anonymous BOOLEAN DEFAULT 0;")
        conn.commit()
        print("Added is_anonymous to chat_messages in app.db")
    except sqlite3.OperationalError as e:
        print(f"app.db error: {e}")
    conn.close()
