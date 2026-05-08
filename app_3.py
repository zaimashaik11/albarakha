"""
Al Barakha Medical Tourism — Backend Server
Run: python3 app.py
Admin: http://localhost:5000/admin  (password: albarakha2024)
"""

from flask import Flask, request, jsonify, session, redirect, url_for, render_template_string, send_from_directory
import sqlite3, hashlib, secrets, json, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DB_PATH = "albarakha.db"
ADMIN_PASSWORD_HASH = hashlib.sha256("albarakha2024".encode()).hexdigest()

# ─── DATABASE SETUP ───────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT NOT NULL,
            service TEXT,
            message TEXT,
            status TEXT DEFAULT 'new',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            doctor TEXT NOT NULL,
            date TEXT,
            time TEXT,
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """)

init_db()

# ─── CORS HELPER ──────────────────────────────────────────────────────────────

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response

@app.route("/api/<path:p>", methods=["OPTIONS"])
def options(p):
    return jsonify({}), 200

# ─── PUBLIC API ───────────────────────────────────────────────────────────────

@app.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.get_json(force=True)
    if not data.get("name") or not data.get("email"):
        return jsonify({"error": "Name and email are required"}), 400
    with get_db() as db:
        db.execute(
            "INSERT INTO contacts (name, phone, email, service, message) VALUES (?,?,?,?,?)",
            (data.get("name"), data.get("phone",""), data.get("email"),
             data.get("service",""), data.get("message",""))
        )
    return jsonify({"ok": True, "message": "Message received. We'll contact you soon!"})

@app.route("/api/appointment", methods=["POST"])
def api_appointment():
    data = request.get_json(force=True)
    if not data.get("name") or not data.get("phone") or not data.get("doctor"):
        return jsonify({"error": "Name, phone, and doctor are required"}), 400
    with get_db() as db:
        db.execute(
            "INSERT INTO appointments (name, phone, email, doctor, date, time, notes) VALUES (?,?,?,?,?,?,?)",
            (data.get("name"), data.get("phone"), data.get("email",""),
             data.get("doctor"), data.get("date",""), data.get("time",""), data.get("notes",""))
        )
    return jsonify({"ok": True, "message": "Appointment request received!"})

@app.route("/api/stats", methods=["GET"])
def api_stats():
    with get_db() as db:
        total_contacts = db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        total_apts = db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        new_contacts = db.execute("SELECT COUNT(*) FROM contacts WHERE status='new'").fetchone()[0]
        pending_apts = db.execute("SELECT COUNT(*) FROM appointments WHERE status='pending'").fetchone()[0]
    return jsonify({
        "total_contacts": total_contacts,
        "total_appointments": total_apts,
        "new_contacts": new_contacts,
        "pending_appointments": pending_apts
    })

# ─── ADMIN AUTH ───────────────────────────────────────────────────────────────

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        pw = request.form.get("password","")
        if hashlib.sha256(pw.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
            session["admin"] = True
            return redirect("/admin")
        error = "Incorrect password."
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin/login")

# ─── ADMIN DASHBOARD API ─────────────────────────────────────────────────────

@app.route("/admin/api/contacts", methods=["GET"])
@admin_required
def admin_contacts():
    with get_db() as db:
        rows = db.execute("SELECT * FROM contacts ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/admin/api/appointments", methods=["GET"])
@admin_required
def admin_appointments():
    with get_db() as db:
        rows = db.execute("SELECT * FROM appointments ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/admin/api/contacts/<int:id>", methods=["PUT"])
@admin_required
def update_contact(id):
    data = request.get_json(force=True)
    with get_db() as db:
        db.execute("UPDATE contacts SET status=?, notes=? WHERE id=?",
                   (data.get("status"), data.get("notes",""), id))
    return jsonify({"ok": True})

@app.route("/admin/api/appointments/<int:id>", methods=["PUT"])
@admin_required
def update_appointment(id):
    data = request.get_json(force=True)
    with get_db() as db:
        db.execute("UPDATE appointments SET status=?, notes=? WHERE id=?",
                   (data.get("status"), data.get("notes",""), id))
    return jsonify({"ok": True})

@app.route("/admin/api/contacts/<int:id>", methods=["DELETE"])
@admin_required
def delete_contact(id):
    with get_db() as db:
        db.execute("DELETE FROM contacts WHERE id=?", (id,))
    return jsonify({"ok": True})

@app.route("/admin/api/appointments/<int:id>", methods=["DELETE"])
@admin_required
def delete_appointment(id):
    with get_db() as db:
        db.execute("DELETE FROM appointments WHERE id=?", (id,))
    return jsonify({"ok": True})

@app.route("/admin/api/export/contacts")
@admin_required
def export_contacts():
    import csv, io
    with get_db() as db:
        rows = db.execute("SELECT * FROM contacts ORDER BY created_at DESC").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Name","Phone","Email","Service","Message","Status","Notes","Created At"])
    for r in rows:
        writer.writerow([r["id"],r["name"],r["phone"],r["email"],r["service"],r["message"],r["status"],r["notes"],r["created_at"]])
    from flask import Response
    return Response(output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=contacts.csv"})

@app.route("/admin/api/export/appointments")
@admin_required
def export_appointments():
    import csv, io
    with get_db() as db:
        rows = db.execute("SELECT * FROM appointments ORDER BY created_at DESC").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Name","Phone","Email","Doctor","Date","Time","Notes","Status","Created At"])
    for r in rows:
        writer.writerow([r["id"],r["name"],r["phone"],r["email"],r["doctor"],r["date"],r["time"],r["notes"],r["status"],r["created_at"]])
    from flask import Response
    return Response(output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=appointments.csv"})

# ─── ADMIN SEED (demo data) ───────────────────────────────────────────────────

@app.route("/admin/api/seed", methods=["POST"])
@admin_required
def seed():
    with get_db() as db:
        count = db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        if count > 0:
            return jsonify({"ok": False, "msg": "Data already exists"})
        db.executescript("""
        INSERT INTO contacts (name,phone,email,service,message,status) VALUES
        ('Ahmed Al-Rashidi','+971501234567','ahmed@email.com','Doctor / Hospital Appointment','Need appointment with heart specialist for my father','new'),
        ('Fatima Hassan','+968912345678','fatima@email.com','Hotel Booking','Looking for hotel near Fortis Hospital for 2 weeks','contacted'),
        ('Mohammed Khalid','+97312345678','mkhalid@email.com','Full Package (All Services)','Need complete package - visa, hotel, doctor, flight for knee replacement','new'),
        ('Sara Al-Amin','+96612345678','sara@email.com','Visa Assistance','Need medical visa letter for my husband','resolved');

        INSERT INTO appointments (name,phone,email,doctor,date,time,status) VALUES
        ('Ahmed Al-Rashidi','+971501234567','ahmed@email.com','Dr. Naveed – Heart Surgeon','2025-07-15','10:00','pending'),
        ('Mohammed Khalid','+97312345678','mkhalid@email.com','Dr. Ayappa – Orthopedic Specialist','2025-07-20','14:30','confirmed'),
        ('Layla Nasser','+96512345678','layla@email.com','Dr. Rao – Neuro Specialist','2025-07-18','09:00','pending');
        """)
    return jsonify({"ok": True})

# ─── ADMIN FRONTEND ───────────────────────────────────────────────────────────

@app.route("/admin")
@app.route("/admin/")
@admin_required
def admin_dashboard():
    return render_template_string(ADMIN_HTML)

# ─── SERVE FRONTEND ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("static", path)

# ─── HTML TEMPLATES ───────────────────────────────────────────────────────────

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Admin Login – Al Barakha</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'DM Sans',sans-serif; background:#0F1C2E; display:flex; align-items:center; justify-content:center; min-height:100vh; }
.box { background:#1A2E45; border:1px solid rgba(201,168,92,0.25); border-radius:12px; padding:48px 40px; width:380px; }
.logo { font-family:'Cormorant Garamond',serif; color:#C9A85C; font-size:1.5rem; text-align:center; margin-bottom:6px; }
.sub { color:rgba(255,255,255,0.4); font-size:0.78rem; text-align:center; letter-spacing:0.12em; text-transform:uppercase; margin-bottom:32px; }
label { display:block; color:rgba(255,255,255,0.5); font-size:0.75rem; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:6px; }
input { width:100%; padding:12px 14px; background:rgba(255,255,255,0.07); border:1px solid rgba(201,168,92,0.25); border-radius:4px; color:#fff; font-size:0.9rem; font-family:'DM Sans',sans-serif; outline:none; margin-bottom:20px; }
input:focus { border-color:#C9A85C; }
button { width:100%; padding:13px; background:#C9A85C; color:#0F1C2E; border:none; border-radius:4px; font-family:'DM Sans',sans-serif; font-weight:500; font-size:0.875rem; letter-spacing:0.08em; text-transform:uppercase; cursor:pointer; }
button:hover { background:#E8D5A3; }
.error { color:#F09595; font-size:0.83rem; margin-bottom:16px; text-align:center; }
</style>
</head>
<body>
<div class="box">
  <div class="logo">Al Barakha</div>
  <div class="sub">Admin Dashboard</div>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <form method="POST">
    <label>Password</label>
    <input type="password" name="password" placeholder="Enter admin password" autofocus>
    <button type="submit">Sign In</button>
  </form>
</div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Admin – Al Barakha Medical Tourism</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'DM Sans',sans-serif; background:#F5F4F0; color:#0F1C2E; display:flex; height:100vh; overflow:hidden; }

/* SIDEBAR */
.sidebar { width:230px; background:#0F1C2E; display:flex; flex-direction:column; flex-shrink:0; border-right:1px solid rgba(201,168,92,0.15); }
.sidebar-logo { padding:24px 20px; border-bottom:1px solid rgba(201,168,92,0.15); }
.sidebar-logo-text { font-family:'Cormorant Garamond',serif; color:#C9A85C; font-size:1.2rem; }
.sidebar-logo-sub { color:rgba(255,255,255,0.35); font-size:0.68rem; letter-spacing:0.12em; text-transform:uppercase; margin-top:2px; }
nav { flex:1; padding:16px 0; }
.nav-item { display:flex; align-items:center; gap:10px; padding:10px 20px; color:rgba(255,255,255,0.5); font-size:0.85rem; cursor:pointer; transition:all 0.15s; border-left:3px solid transparent; }
.nav-item:hover { color:#fff; background:rgba(255,255,255,0.05); }
.nav-item.active { color:#C9A85C; border-left-color:#C9A85C; background:rgba(201,168,92,0.08); }
.nav-icon { font-size:1rem; width:18px; }
.sidebar-footer { padding:16px 20px; border-top:1px solid rgba(201,168,92,0.1); }
.sidebar-footer a { color:rgba(255,255,255,0.35); font-size:0.78rem; text-decoration:none; }
.sidebar-footer a:hover { color:#C9A85C; }

/* MAIN */
.main { flex:1; overflow:auto; display:flex; flex-direction:column; }
.topbar { background:#fff; border-bottom:1px solid #E8E0D0; padding:0 28px; height:60px; display:flex; align-items:center; justify-content:space-between; flex-shrink:0; }
.topbar h1 { font-family:'Cormorant Garamond',serif; font-size:1.4rem; color:#0F1C2E; }
.topbar-right { display:flex; gap:10px; }
.btn { padding:8px 16px; border:none; border-radius:4px; cursor:pointer; font-family:'DM Sans',sans-serif; font-size:0.8rem; font-weight:500; letter-spacing:0.05em; text-transform:uppercase; text-decoration:none; transition:all 0.15s; }
.btn-gold { background:#C9A85C; color:#0F1C2E; }
.btn-gold:hover { background:#E8D5A3; }
.btn-outline { background:transparent; border:1px solid #C9A85C; color:#C9A85C; }
.btn-outline:hover { background:rgba(201,168,92,0.1); }
.btn-danger { background:#E24B4A; color:#fff; }
.btn-sm { padding:5px 11px; font-size:0.72rem; }

/* CONTENT */
.content { padding:28px; flex:1; }
.page { display:none; }
.page.active { display:block; }

/* STATS */
.stats-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:28px; }
.stat-card { background:#fff; border:1px solid #E8E0D0; border-radius:8px; padding:20px; }
.stat-label { font-size:0.72rem; letter-spacing:0.1em; text-transform:uppercase; color:#718096; margin-bottom:8px; }
.stat-num { font-family:'Cormorant Garamond',serif; font-size:2.4rem; font-weight:600; color:#0F1C2E; line-height:1; }
.stat-sub { font-size:0.75rem; color:#718096; margin-top:4px; }
.stat-card.gold .stat-num { color:#C9A85C; }
.stat-card.teal .stat-num { color:#1D7A6B; }
.stat-card.red .stat-num { color:#E24B4A; }

/* TABLES */
.card { background:#fff; border:1px solid #E8E0D0; border-radius:8px; overflow:hidden; }
.card-header { padding:16px 20px; border-bottom:1px solid #E8E0D0; display:flex; align-items:center; justify-content:space-between; }
.card-header h3 { font-family:'DM Sans'; font-weight:500; font-size:0.95rem; }
.card-header-right { display:flex; gap:8px; align-items:center; }
.filter-select { padding:6px 10px; border:1px solid #E8E0D0; border-radius:4px; font-family:'DM Sans'; font-size:0.8rem; color:#0F1C2E; background:#fff; outline:none; }
table { width:100%; border-collapse:collapse; font-size:0.84rem; }
th { background:#F9F5EF; color:#718096; font-weight:500; font-size:0.7rem; letter-spacing:0.1em; text-transform:uppercase; padding:10px 16px; text-align:left; border-bottom:1px solid #E8E0D0; }
td { padding:12px 16px; border-bottom:1px solid #F0EAE0; vertical-align:top; }
tr:last-child td { border-bottom:none; }
tr:hover td { background:#FDFBF7; }
.badge { display:inline-block; padding:3px 10px; border-radius:100px; font-size:0.7rem; font-weight:500; letter-spacing:0.06em; text-transform:uppercase; }
.badge-new { background:#E6F1FB; color:#185FA5; }
.badge-contacted { background:#EAF3DE; color:#3B6D11; }
.badge-resolved { background:#E1F5EE; color:#0F6E56; }
.badge-pending { background:#FAEEDA; color:#854F0B; }
.badge-confirmed { background:#EAF3DE; color:#3B6D11; }
.badge-cancelled { background:#FCEBEB; color:#A32D2D; }
.td-name { font-weight:500; }
.td-email { color:#185FA5; }
.td-msg { color:#718096; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.td-time { color:#718096; font-size:0.78rem; white-space:nowrap; }
.actions { display:flex; gap:6px; }

/* MODAL */
.modal-overlay { display:none; position:fixed; inset:0; background:rgba(15,28,46,0.6); z-index:1000; align-items:center; justify-content:center; }
.modal-overlay.open { display:flex; }
.modal { background:#fff; border-radius:10px; padding:28px; width:500px; max-width:95vw; max-height:85vh; overflow-y:auto; }
.modal h3 { font-family:'Cormorant Garamond',serif; font-size:1.4rem; margin-bottom:20px; }
.modal-row { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.form-group { margin-bottom:16px; }
.form-group label { display:block; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.08em; color:#718096; margin-bottom:5px; }
.form-group input, .form-group select, .form-group textarea { width:100%; padding:9px 12px; border:1px solid #E8E0D0; border-radius:4px; font-family:'DM Sans'; font-size:0.875rem; color:#0F1C2E; outline:none; }
.form-group textarea { min-height:80px; resize:vertical; }
.form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color:#C9A85C; }
.modal-actions { display:flex; gap:10px; justify-content:flex-end; margin-top:20px; }
.btn-cancel { background:#F5F4F0; color:#718096; }

/* EMPTY */
.empty { text-align:center; padding:48px; color:#718096; font-size:0.9rem; }
.empty-icon { font-size:2.5rem; margin-bottom:12px; }

/* SEARCH */
.search-bar { padding:8px 12px; border:1px solid #E8E0D0; border-radius:4px; font-family:'DM Sans'; font-size:0.85rem; outline:none; width:200px; }
.search-bar:focus { border-color:#C9A85C; }

/* TOAST */
.toast { position:fixed; bottom:24px; right:24px; background:#0F1C2E; color:#C9A85C; padding:12px 20px; border-radius:6px; font-size:0.85rem; z-index:9999; opacity:0; transform:translateY(8px); transition:all 0.3s; pointer-events:none; }
.toast.show { opacity:1; transform:translateY(0); }
</style>
</head>
<body>

<!-- SIDEBAR -->
<aside class="sidebar">
  <div class="sidebar-logo">
    <div class="sidebar-logo-text">Al Barakha</div>
    <div class="sidebar-logo-sub">Admin Panel</div>
  </div>
  <nav>
    <div class="nav-item active" onclick="showPage('dashboard')">
      <span class="nav-icon">📊</span> Dashboard
    </div>
    <div class="nav-item" onclick="showPage('contacts')">
      <span class="nav-icon">💬</span> Contact Enquiries
    </div>
    <div class="nav-item" onclick="showPage('appointments')">
      <span class="nav-icon">📅</span> Appointments
    </div>
  </nav>
  <div class="sidebar-footer">
    <a href="/admin/logout">← Sign Out</a>
  </div>
</aside>

<!-- MAIN -->
<div class="main">
  <div class="topbar">
    <h1 id="page-title">Dashboard</h1>
    <div class="topbar-right" id="topbar-actions"></div>
  </div>
  <div class="content">

    <!-- DASHBOARD -->
    <div class="page active" id="page-dashboard">
      <div class="stats-grid">
        <div class="stat-card gold">
          <div class="stat-label">Total Enquiries</div>
          <div class="stat-num" id="s-total-contacts">–</div>
          <div class="stat-sub">Contact form submissions</div>
        </div>
        <div class="stat-card red">
          <div class="stat-label">New / Unread</div>
          <div class="stat-num" id="s-new">–</div>
          <div class="stat-sub">Awaiting response</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Appointments</div>
          <div class="stat-num" id="s-total-apts">–</div>
          <div class="stat-sub">Booking requests</div>
        </div>
        <div class="stat-card teal">
          <div class="stat-label">Pending Appointments</div>
          <div class="stat-num" id="s-pending">–</div>
          <div class="stat-sub">Need confirmation</div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
        <div class="card">
          <div class="card-header">
            <h3>Recent Enquiries</h3>
            <a onclick="showPage('contacts')" style="cursor:pointer;color:#C9A85C;font-size:0.8rem;">View all →</a>
          </div>
          <table>
            <thead><tr><th>Name</th><th>Service</th><th>Status</th><th>Date</th></tr></thead>
            <tbody id="dash-contacts"></tbody>
          </table>
        </div>
        <div class="card">
          <div class="card-header">
            <h3>Recent Appointments</h3>
            <a onclick="showPage('appointments')" style="cursor:pointer;color:#C9A85C;font-size:0.8rem;">View all →</a>
          </div>
          <table>
            <thead><tr><th>Name</th><th>Doctor</th><th>Status</th><th>Date</th></tr></thead>
            <tbody id="dash-apts"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- CONTACTS PAGE -->
    <div class="page" id="page-contacts">
      <div class="card">
        <div class="card-header">
          <h3>All Contact Enquiries</h3>
          <div class="card-header-right">
            <input class="search-bar" placeholder="Search…" id="contact-search" oninput="filterContacts()">
            <select class="filter-select" id="contact-filter" onchange="filterContacts()">
              <option value="">All Status</option>
              <option value="new">New</option>
              <option value="contacted">Contacted</option>
              <option value="resolved">Resolved</option>
            </select>
            <a href="/admin/api/export/contacts" class="btn btn-outline btn-sm">Export CSV</a>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>#</th><th>Name</th><th>Contact</th><th>Service</th>
              <th>Message</th><th>Status</th><th>Received</th><th>Actions</th>
            </tr>
          </thead>
          <tbody id="contacts-body"></tbody>
        </table>
        <div id="contacts-empty" class="empty" style="display:none;">
          <div class="empty-icon">📭</div>
          No enquiries found.
        </div>
      </div>
    </div>

    <!-- APPOINTMENTS PAGE -->
    <div class="page" id="page-appointments">
      <div class="card">
        <div class="card-header">
          <h3>All Appointment Requests</h3>
          <div class="card-header-right">
            <input class="search-bar" placeholder="Search…" id="apt-search" oninput="filterApts()">
            <select class="filter-select" id="apt-filter" onchange="filterApts()">
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="confirmed">Confirmed</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <a href="/admin/api/export/appointments" class="btn btn-outline btn-sm">Export CSV</a>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>#</th><th>Name</th><th>Contact</th><th>Doctor</th>
              <th>Date & Time</th><th>Status</th><th>Received</th><th>Actions</th>
            </tr>
          </thead>
          <tbody id="apts-body"></tbody>
        </table>
        <div id="apts-empty" class="empty" style="display:none;">
          <div class="empty-icon">📭</div>
          No appointments found.
        </div>
      </div>
    </div>

  </div>
</div>

<!-- CONTACT EDIT MODAL -->
<div class="modal-overlay" id="contact-modal">
  <div class="modal">
    <h3>Edit Enquiry</h3>
    <div id="contact-modal-details" style="background:#F9F5EF;border-radius:6px;padding:14px;margin-bottom:18px;font-size:0.85rem;line-height:1.8;color:#0F1C2E;"></div>
    <div class="form-group">
      <label>Status</label>
      <select id="m-contact-status">
        <option value="new">New</option>
        <option value="contacted">Contacted</option>
        <option value="resolved">Resolved</option>
      </select>
    </div>
    <div class="form-group">
      <label>Internal Notes</label>
      <textarea id="m-contact-notes" placeholder="Add notes for your team…"></textarea>
    </div>
    <div class="modal-actions">
      <button class="btn btn-cancel" onclick="closeModal('contact-modal')">Cancel</button>
      <button class="btn btn-gold" onclick="saveContact()">Save Changes</button>
    </div>
  </div>
</div>

<!-- APPOINTMENT EDIT MODAL -->
<div class="modal-overlay" id="apt-modal">
  <div class="modal">
    <h3>Edit Appointment</h3>
    <div id="apt-modal-details" style="background:#F9F5EF;border-radius:6px;padding:14px;margin-bottom:18px;font-size:0.85rem;line-height:1.8;color:#0F1C2E;"></div>
    <div class="form-group">
      <label>Status</label>
      <select id="m-apt-status">
        <option value="pending">Pending</option>
        <option value="confirmed">Confirmed</option>
        <option value="cancelled">Cancelled</option>
      </select>
    </div>
    <div class="form-group">
      <label>Internal Notes</label>
      <textarea id="m-apt-notes" placeholder="Add notes…"></textarea>
    </div>
    <div class="modal-actions">
      <button class="btn btn-cancel" onclick="closeModal('apt-modal')">Cancel</button>
      <button class="btn btn-gold" onclick="saveApt()">Save Changes</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let contacts = [], appointments = [], editingContactId = null, editingAptId = null;

// ── NAV ──────────────────────────────────────────────────────────────────────
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => {
    if (n.textContent.trim().toLowerCase().includes(name === 'dashboard' ? 'dash' : name === 'contacts' ? 'enquir' : 'appoint'))
      n.classList.add('active');
  });
  const titles = { dashboard: 'Dashboard', contacts: 'Contact Enquiries', appointments: 'Appointment Requests' };
  document.getElementById('page-title').textContent = titles[name];
  const actions = document.getElementById('topbar-actions');
  if (name === 'contacts') {
    actions.innerHTML = '<button class="btn btn-outline btn-sm" onclick="seedData()">Load Sample Data</button>';
  } else {
    actions.innerHTML = '';
  }
  if (name !== 'dashboard') loadData(name);
}

// ── DATA ─────────────────────────────────────────────────────────────────────
async function loadStats() {
  const r = await fetch('/api/stats');
  const d = await r.json();
  document.getElementById('s-total-contacts').textContent = d.total_contacts;
  document.getElementById('s-new').textContent = d.new_contacts;
  document.getElementById('s-total-apts').textContent = d.total_appointments;
  document.getElementById('s-pending').textContent = d.pending_appointments;
}

async function loadDash() {
  const [cr, ar] = await Promise.all([
    fetch('/admin/api/contacts').then(r=>r.json()),
    fetch('/admin/api/appointments').then(r=>r.json())
  ]);
  renderDashContacts(cr.slice(0,5));
  renderDashApts(ar.slice(0,5));
}

async function loadData(type) {
  if (type === 'contacts') {
    const r = await fetch('/admin/api/contacts');
    contacts = await r.json();
    renderContacts(contacts);
  } else {
    const r = await fetch('/admin/api/appointments');
    appointments = await r.json();
    renderApts(appointments);
  }
}

function badge(status) {
  const map = { new:'badge-new', contacted:'badge-contacted', resolved:'badge-resolved', pending:'badge-pending', confirmed:'badge-confirmed', cancelled:'badge-cancelled' };
  return `<span class="badge ${map[status]||''}">${status}</span>`;
}

function fmtDate(dt) {
  if (!dt) return '–';
  return dt.split(' ')[0];
}

// ── CONTACTS TABLE ────────────────────────────────────────────────────────────
function renderContacts(data) {
  const tbody = document.getElementById('contacts-body');
  const empty = document.getElementById('contacts-empty');
  if (!data.length) { tbody.innerHTML=''; empty.style.display='block'; return; }
  empty.style.display = 'none';
  tbody.innerHTML = data.map(c => `
    <tr>
      <td>${c.id}</td>
      <td><div class="td-name">${esc(c.name)}</div></td>
      <td>
        <div class="td-email">${esc(c.email)}</div>
        <div style="font-size:0.78rem;color:#718096">${esc(c.phone||'')}</div>
      </td>
      <td>${esc(c.service||'—')}</td>
      <td><div class="td-msg" title="${esc(c.message)}">${esc(c.message||'—')}</div></td>
      <td>${badge(c.status)}</td>
      <td class="td-time">${fmtDate(c.created_at)}</td>
      <td>
        <div class="actions">
          <button class="btn btn-outline btn-sm" onclick="editContact(${c.id})">Edit</button>
          <button class="btn btn-danger btn-sm" onclick="delContact(${c.id})">Del</button>
        </div>
      </td>
    </tr>`).join('');
}

function filterContacts() {
  const q = document.getElementById('contact-search').value.toLowerCase();
  const st = document.getElementById('contact-filter').value;
  renderContacts(contacts.filter(c =>
    (!st || c.status === st) &&
    (!q || [c.name,c.email,c.phone,c.service,c.message].join(' ').toLowerCase().includes(q))
  ));
}

function renderDashContacts(data) {
  document.getElementById('dash-contacts').innerHTML = data.map(c=>`
    <tr>
      <td class="td-name">${esc(c.name)}</td>
      <td style="font-size:0.8rem">${esc(c.service||'—')}</td>
      <td>${badge(c.status)}</td>
      <td class="td-time">${fmtDate(c.created_at)}</td>
    </tr>`).join('') || '<tr><td colspan="4" class="empty">No data</td></tr>';
}

// ── APPOINTMENTS TABLE ────────────────────────────────────────────────────────
function renderApts(data) {
  const tbody = document.getElementById('apts-body');
  const empty = document.getElementById('apts-empty');
  if (!data.length) { tbody.innerHTML=''; empty.style.display='block'; return; }
  empty.style.display = 'none';
  tbody.innerHTML = data.map(a => `
    <tr>
      <td>${a.id}</td>
      <td><div class="td-name">${esc(a.name)}</div></td>
      <td>
        <div style="font-size:0.82rem">${esc(a.phone)}</div>
        <div class="td-email" style="font-size:0.78rem">${esc(a.email||'')}</div>
      </td>
      <td style="font-size:0.82rem">${esc(a.doctor)}</td>
      <td>
        <div>${esc(a.date||'—')}</div>
        <div style="font-size:0.78rem;color:#718096">${esc(a.time||'')}</div>
      </td>
      <td>${badge(a.status)}</td>
      <td class="td-time">${fmtDate(a.created_at)}</td>
      <td>
        <div class="actions">
          <button class="btn btn-outline btn-sm" onclick="editApt(${a.id})">Edit</button>
          <button class="btn btn-danger btn-sm" onclick="delApt(${a.id})">Del</button>
        </div>
      </td>
    </tr>`).join('');
}

function filterApts() {
  const q = document.getElementById('apt-search').value.toLowerCase();
  const st = document.getElementById('apt-filter').value;
  renderApts(appointments.filter(a =>
    (!st || a.status === st) &&
    (!q || [a.name,a.phone,a.email,a.doctor].join(' ').toLowerCase().includes(q))
  ));
}

function renderDashApts(data) {
  document.getElementById('dash-apts').innerHTML = data.map(a=>`
    <tr>
      <td class="td-name">${esc(a.name)}</td>
      <td style="font-size:0.78rem">${esc(a.doctor.split('–')[0].trim())}</td>
      <td>${badge(a.status)}</td>
      <td class="td-time">${esc(a.date||'—')}</td>
    </tr>`).join('') || '<tr><td colspan="4" class="empty">No data</td></tr>';
}

// ── EDIT / SAVE ───────────────────────────────────────────────────────────────
function editContact(id) {
  const c = contacts.find(x=>x.id===id);
  if (!c) return;
  editingContactId = id;
  document.getElementById('contact-modal-details').innerHTML =
    `<b>${esc(c.name)}</b><br>📧 ${esc(c.email)} &nbsp;📞 ${esc(c.phone||'—')}<br>🔧 ${esc(c.service||'—')}<br>💬 ${esc(c.message||'—')}`;
  document.getElementById('m-contact-status').value = c.status;
  document.getElementById('m-contact-notes').value = c.notes||'';
  openModal('contact-modal');
}

async function saveContact() {
  const status = document.getElementById('m-contact-status').value;
  const notes = document.getElementById('m-contact-notes').value;
  await fetch(`/admin/api/contacts/${editingContactId}`, {
    method:'PUT', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({status, notes})
  });
  closeModal('contact-modal');
  await loadData('contacts');
  loadStats();
  toast('Contact updated ✓');
}

async function delContact(id) {
  if (!confirm('Delete this enquiry?')) return;
  await fetch(`/admin/api/contacts/${id}`, {method:'DELETE'});
  contacts = contacts.filter(c=>c.id!==id);
  renderContacts(contacts);
  loadStats();
  toast('Deleted');
}

function editApt(id) {
  const a = appointments.find(x=>x.id===id);
  if (!a) return;
  editingAptId = id;
  document.getElementById('apt-modal-details').innerHTML =
    `<b>${esc(a.name)}</b><br>📞 ${esc(a.phone)} &nbsp;📧 ${esc(a.email||'—')}<br>🩺 ${esc(a.doctor)}<br>📅 ${esc(a.date||'—')} ${esc(a.time||'')}`;
  document.getElementById('m-apt-status').value = a.status;
  document.getElementById('m-apt-notes').value = a.notes||'';
  openModal('apt-modal');
}

async function saveApt() {
  const status = document.getElementById('m-apt-status').value;
  const notes = document.getElementById('m-apt-notes').value;
  await fetch(`/admin/api/appointments/${editingAptId}`, {
    method:'PUT', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({status, notes})
  });
  closeModal('apt-modal');
  await loadData('appointments');
  loadStats();
  toast('Appointment updated ✓');
}

async function delApt(id) {
  if (!confirm('Delete this appointment?')) return;
  await fetch(`/admin/api/appointments/${id}`, {method:'DELETE'});
  appointments = appointments.filter(a=>a.id!==id);
  renderApts(appointments);
  loadStats();
  toast('Deleted');
}

// ── SEED ──────────────────────────────────────────────────────────────────────
async function seedData() {
  const r = await fetch('/admin/api/seed', {method:'POST'});
  const d = await r.json();
  if (d.ok) { toast('Sample data loaded ✓'); loadStats(); loadDash(); loadData('contacts'); }
  else toast(d.msg);
}

// ── MODAL ─────────────────────────────────────────────────────────────────────
function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }
document.querySelectorAll('.modal-overlay').forEach(el => {
  el.addEventListener('click', e => { if (e.target===el) el.classList.remove('open'); });
});

// ── TOAST ─────────────────────────────────────────────────────────────────────
function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// ── UTILS ─────────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── INIT ──────────────────────────────────────────────────────────────────────
loadStats();
loadDash();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print("=" * 55)
    print("  Al Barakha Medical Tourism — Backend")
    print("=" * 55)
    print(f"  Website:   http://localhost:5000")
    print(f"  Admin:     http://localhost:5000/admin")
    print(f"  Password:  albarakha2024")
    print("=" * 55)
    app.run(debug=True, port=5000)
