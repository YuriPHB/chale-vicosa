import secrets, time
from db import get_conn, verify_password, hash_password

SESSIONS = {}

def create_session(user_id, role):
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"user_id": user_id, "role": role, "created": time.time()}
    return token

def get_session(token):
    s = SESSIONS.get(token)
    if not s:
        return None
    if time.time() - s["created"] > 8*3600:
        del SESSIONS[token]
        return None
    return s

def destroy_session(token):
    SESSIONS.pop(token, None)

def login(email, password):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if not row:
        return None
    if not verify_password(password, row["password_hash"], row["salt"]):
        return None
    return row

def register(name, email, password):
    h, salt = hash_password(password)
    from datetime import datetime
    conn = get_conn()
    try:
        role = "admin" if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0 else "client"
        conn.execute("INSERT INTO users (name,email,password_hash,salt,role,created_at) VALUES (?,?,?,?,?,?)",
                     (name, email, h, salt, role, datetime.now().isoformat()))
        conn.commit()
        uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except Exception as e:
        conn.close()
        return None, str(e)
    conn.close()
    return uid, None
