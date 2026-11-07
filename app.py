import http.server, socketserver, urllib.parse, json, os, secrets, datetime
from db import init_db, get_conn
from auth import login, register, create_session, get_session, destroy_session
from db import hash_password

import os as _os
PORT = int(_os.environ.get("PORT", 8002))
BASE = os.path.dirname(__file__)

def read_body(handler):
    n = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(n).decode()
    ct = handler.headers.get("Content-Type", "")
    if "application/json" in ct:
        return json.loads(raw or "{}")
    return urllib.parse.parse_qs(raw)

def send_html(handler, path, code=200):
    full = os.path.join(BASE, "static", path)
    with open(full, "rb") as f:
        data = f.read()
    handler.send_response(code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)

def send_json(handler, obj, code=200):
    data = json.dumps(obj).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)

def get_cookie(handler, name):
    c = handler.headers.get("Cookie", "")
    for part in c.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            if k == name:
                return v
    return None

def set_cookie(handler, name, value, path="/"):
    handler.send_header("Set-Cookie", f"{name}={value}; Path={path}; HttpOnly")

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        if path == "/":
            send_html(self, "index.html"); return
        if path == "/login":
            send_html(self, "login.html"); return
        if path == "/register":
            send_html(self, "register.html"); return
        if path == "/admin":
            send_html(self, "admin.html"); return
        if path == "/dashboard":
            send_html(self, "dashboard.html"); return
        if path == "/api/me":
            tok = get_cookie(self, "session")
            s = get_session(tok) if tok else None
            if not s:
                send_json(self, {"user": None}, 401); return
            conn = get_conn()
            u = conn.execute("SELECT id,name,email,role FROM users WHERE id=?", (s["user_id"],)).fetchone()
            conn.close()
            send_json(self, {"user": dict(u)}); return
        if path == "/api/bookings":
            tok = get_cookie(self, "session")
            s = get_session(tok) if tok else None
            if not s:
                send_json(self, {"error": "unauth"}, 401); return
            conn = get_conn()
            if s["role"] == "admin":
                rows = conn.execute("SELECT b.*, u.name as client_name, u.email as client_email FROM bookings b JOIN users u ON u.id=b.user_id ORDER BY b.id DESC").fetchall()
            else:
                rows = conn.execute("SELECT * FROM bookings WHERE user_id=? ORDER BY id DESC", (s["user_id"],)).fetchall()
            conn.close()
            send_json(self, {"bookings": [dict(r) for r in rows]}); return
        if path == "/api/report":
            tok = get_cookie(self, "session")
            s = get_session(tok) if tok else None
            if not s or s["role"] != "admin":
                send_json(self, {"error": "forbidden"}, 403); return
            conn = get_conn()
            total_rev = conn.execute("SELECT COALESCE(SUM(total),0) FROM bookings WHERE status='confirmed'").fetchone()[0]
            count = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
            confirmed = conn.execute("SELECT COUNT(*) FROM bookings WHERE status='confirmed'").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM bookings WHERE status='pending'").fetchone()[0]
            cancelled = conn.execute("SELECT COUNT(*) FROM bookings WHERE status='cancelled'").fetchone()[0]
            clients = conn.execute("SELECT COUNT(*) FROM users WHERE role='client'").fetchone()[0]
            nights = conn.execute("SELECT COALESCE(SUM((julianday(checkout)-julianday(checkin))),0) FROM bookings").fetchone()[0]
            conn.close()
            send_json(self, {"revenue": total_rev, "total_bookings": count, "confirmed": confirmed, "pending": pending, "cancelled": cancelled, "clients": clients, "nights": int(nights or 0)}); return
        if path.startswith("/api/calendar/"):
            bid = path.split('/')[-1]
            tok = get_cookie(self, "session")
            s = get_session(tok) if tok else None
            if not s:
                send_json(self, {"error": "unauth"}, 401); return
            conn = get_conn()
            b = conn.execute("SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
            conn.close()
            if not b:
                self.send_response(404); self.end_headers(); return
            ics = ("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Chale Vicosa//PT\n"
                   "BEGIN:VEVENT\nUID:booking-"+str(b['id'])+"@chalevicosa\n"
                   "DTSTART;VALUE=DATE:"+b['checkin'].replace('-','')+"\n"
                   "DTEND;VALUE=DATE:"+b['checkout'].replace('-','')+"\n"
                   "SUMMARY:Reserva Chale Vicosa ("+str(b['id'])+")\n"
                   "DESCRIPTION:Diaria R$"+str(b['daily_rate'])+" Total R$"+str(b['total'])+" Senha fechadura: "+str(b['lock_code'])+"\n"
                   "END:VEVENT\nEND:VCALENDAR\n")
            data = ics.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar")
            self.send_header("Content-Disposition", "attachment; filename=reserva-"+str(bid)+".ics")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data); return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/register":
            data = read_body(self)
            uid, err = register(data.get("name",""), data.get("email",""), data.get("password",""))
            if err:
                send_json(self, {"error": err}, 400); return
            tok = create_session(uid, "client")
            self.send_response(200)
            set_cookie(self, "session", tok)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode()); return
        if path == "/api/login":
            data = read_body(self)
            row = login(data.get("email",""), data.get("password",""))
            if not row:
                send_json(self, {"error": "invalid credentials"}, 401); return
            tok = create_session(row["id"], row["role"])
            self.send_response(200)
            set_cookie(self, "session", tok)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "role": row["role"]}).encode()); return
        if path == "/api/logout":
            tok = get_cookie(self, "session")
            if tok: destroy_session(tok)
            self.send_response(200)
            set_cookie(self, "session", "")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}'); return
        if path == "/api/book":
            tok = get_cookie(self, "session")
            s = get_session(tok) if tok else None
            if not s:
                send_json(self, {"error": "unauth"}, 401); return
            data = read_body(self)
            checkin = data.get("checkin","")
            checkout = data.get("checkout","")
            rate = float(data.get("daily_rate", 400))
            if rate < 400 or rate > 450:
                send_json(self, {"error": "daily rate must be 400-450"}, 400); return
            # compute nights
            d0 = datetime.date.fromisoformat(checkin)
            d1 = datetime.date.fromisoformat(checkout)
            nights = (d1 - d0).days
            if nights <= 0:
                send_json(self, {"error": "invalid dates"}, 400); return
            total = nights * rate
            lock_code = secrets.token_hex(3).upper()  # 6-digit hex-ish code
            from datetime import datetime as dt
            conn = get_conn()
            conn.execute("INSERT INTO bookings (user_id,checkin,checkout,daily_rate,total,status,lock_code,notes,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                         (s["user_id"], checkin, checkout, rate, total, "pending", lock_code, data.get("notes",""), dt.now().isoformat()))
            conn.commit()
            bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
            send_json(self, {"ok": True, "booking_id": bid, "nights": nights, "total": total, "lock_code": lock_code}); return
        if path == "/api/confirm":
            tok = get_cookie(self, "session")
            s = get_session(tok) if tok else None
            if not s or s["role"] != "admin":
                send_json(self, {"error": "forbidden"}, 403); return
            data = read_body(self)
            bid = data.get("id")
            conn = get_conn()
            conn.execute("UPDATE bookings SET status='confirmed' WHERE id=?", (bid,))
            conn.commit()
            conn.close()
            send_json(self, {"ok": True}); return
        if path == "/api/cancel":
            tok = get_cookie(self, "session")
            s = get_session(tok) if tok else None
            if not s or s["role"] != "admin":
                send_json(self, {"error": "forbidden"}, 403); return
            data = read_body(self)
            bid = data.get("id")
            conn = get_conn()
            conn.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (bid,))
            conn.commit()
            conn.close()
            send_json(self, {"ok": True}); return
        if path == "/api/change_password":
            tok = get_cookie(self, "session")
            s = get_session(tok) if tok else None
            if not s:
                send_json(self, {"error": "unauth"}, 401); return
            data = read_body(self)
            conn = get_conn()
            row = conn.execute("SELECT * FROM users WHERE id=?", (s["user_id"],)).fetchone()
            from auth import verify_password
            if not verify_password(data.get("old_password",""), row["password_hash"], row["salt"]):
                conn.close(); send_json(self, {"error": "senha atual incorreta"}, 400); return
            h, salt = hash_password(data.get("new_password",""))
            conn.execute("UPDATE users SET password_hash=?, salt=? WHERE id=?", (h, salt, s["user_id"]))
            conn.commit(); conn.close()
            send_json(self, {"ok": True}); return
        self.send_response(404); self.end_headers()

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    init_db()
    print(f"Rental app running on http://localhost:{PORT}")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()