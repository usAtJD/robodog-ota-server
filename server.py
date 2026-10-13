#!/usr/bin/env python3
"""
Robodog OTA Kontrol Sunucusu
- Giris sifresi korumali
- Kalici cihaz listesi (Cihaz bir kere kaydedildikten sonra asla kaybolmaz)
- Cevrimici / Cevrimdisi canli durum takibi
- Cihaz kapaliyken bile guncelleme isaretleme destegi (ESP internete baglandigi anda alir)
- Ozel robodog logo tasarimi
"""

import os
import json
import time
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
from flask import (Flask, request, jsonify, render_template_string,
                   redirect, url_for, session, abort, send_from_directory)

app = Flask(__name__)

# ─── Ayarlar ─────────────────────────────────────────────────────────────────
app.secret_key = os.environ.get("SECRET_KEY", "robodog-gizli-anahtar-degistir-bunu")
PANEL_USERNAME = os.environ.get("PANEL_USERNAME", "admin")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "robodog123")
WEBHOOK_SECRET = os.environ.get("OTA_WEBHOOK_SECRET", "robodog-webhook-secret")
DATA_FILE = Path(os.environ.get("DATA_DIR", ".")) / "ota_data.json"

# ─── Logo (Base64) ───────────────────────────────────────────────────────────
LOGO_IMG_SRC = "data:image/png;base64,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"

# ─── Veri Yapisi ──────────────────────────────────────────────────────────────
devices = {}          # mac -> device dict
pending_updates = {}  # mac -> True/False
latest_release = {
    "version": "0.0.0",
    "firmware_url": "",
    "sha": "",
    "updated_at": None,
    "force_update": False,
}

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "devices": devices,
                "pending_updates": pending_updates,
                "latest_release": latest_release,
            }, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"[HATA] Veri kaydedilemedi: {e}")

def load_data():
    global devices, pending_updates, latest_release
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                devices.update(data.get("devices", {}))
                pending_updates.update(data.get("pending_updates", {}))
                latest_release.update(data.get("latest_release", {}))
            print(f"[OK] Kalici veri yuklendi: {len(devices)} cihaz")
        except Exception as e:
            print(f"[UYARI] Veri yuklenemedi: {e}")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/static/<path:filename>")
def serve_static(filename):
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    return send_from_directory(static_dir, filename)

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Robodog OTA - Giris</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: #090d16; color: #e2e8f0;
      min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      padding: 16px;
    }
    .card {
      background: #111827; border: 1px solid #1f2937;
      border-radius: 20px; padding: 40px 32px;
      width: 100%; max-width: 390px;
      box-shadow: 0 25px 60px rgba(0,0,0,0.7), 0 0 35px rgba(6,182,212,0.15);
      text-align: center;
    }
    .logo-img {
      width: 130px; height: auto;
      border-radius: 14px; margin: 0 auto 16px;
      display: block;
      box-shadow: 0 0 25px rgba(6, 182, 212, 0.4);
      border: 1px solid rgba(6, 182, 212, 0.3);
    }
    .logo h1 { font-size: 1.5rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.02em; }
    .logo p { color: #06b6d4; font-size: 0.85rem; margin-top: 4px; font-weight: 500; }
    
    .form-group { margin-bottom: 16px; text-align: left; }
    label { display: block; font-size: 0.8rem; color: #94a3b8; margin-bottom: 6px; font-weight: 500; }
    input {
      width: 100%; background: #0b1120; border: 1px solid #1f2937;
      border-radius: 10px; padding: 12px 14px;
      color: #e2e8f0; font-size: 0.95rem; transition: all 0.2s;
    }
    input:focus { outline: none; border-color: #06b6d4; box-shadow: 0 0 10px rgba(6,182,212,0.25); }
    
    button {
      width: 100%; background: linear-gradient(135deg, #06b6d4, #2563eb);
      color: white; border: none;
      border-radius: 10px; padding: 13px; font-size: 0.95rem;
      font-weight: 600; cursor: pointer; transition: opacity 0.2s;
      margin-top: 8px; box-shadow: 0 4px 15px rgba(6,182,212,0.35);
    }
    button:hover { opacity: 0.92; }
    
    .error {
      background: #450a0a; border: 1px solid #7f1d1d;
      color: #fca5a5; border-radius: 10px;
      padding: 10px 14px; margin-bottom: 16px; font-size: 0.875rem;
    }
    .footer { text-align: center; margin-top: 24px; color: #475569; font-size: 0.75rem; }
  </style>
</head>
<body>
  <div class="card">
    <img src="{{ logo_src }}" alt="Robodog Logo" class="logo-img">
    <div class="logo">
      <h1>Robodog OTA</h1>
      <p>Yonetim Paneli</p>
    </div>
    
    {% if error %}
    <div class="error" style="margin-top: 16px;">&#x26A0; {{ error }}</div>
    {% endif %}
    
    <form method="POST" style="margin-top: 22px;">
      <div class="form-group">
        <label>Kullanici Adi</label>
        <input type="text" name="username" placeholder="admin" autofocus required>
      </div>
      <div class="form-group">
        <label>Sifre</label>
        <input type="password" name="password" placeholder="••••••••" required>
      </div>
      <button type="submit">Giris Yap</button>
    </form>
    
    <div class="footer">Robodog Firmware Control System</div>
  </div>
</body>
</html>
"""

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        u_ok = secrets.compare_digest(username, PANEL_USERNAME)
        p_ok = secrets.compare_digest(password, PANEL_PASSWORD)
        if u_ok and p_ok:
            session["logged_in"] = True
            session.permanent = True
            app.permanent_session_lifetime = timedelta(days=30)
            return redirect(url_for("index"))
        else:
            error = "Kullanici adi veya sifre hatali!"
    return render_template_string(LOGIN_HTML, error=error, logo_src=LOGO_IMG_SRC)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── ESP32 OTA Endpoint ──────────────────────────────────────────────────────
@app.route("/ota/check", methods=["POST", "GET"])
def ota_check():
    mac = request.headers.get("Device-Id", "").strip()
    if not mac or mac == "unknown":
        mac = request.remote_addr or "unknown_device"
    
    client_id = request.headers.get("Client-Id", "")
    user_agent = request.headers.get("User-Agent", "")
    current_version = "0.0.0"
    ip = request.remote_addr

    try:
        body = request.get_json(silent=True) or {}
        current_version = body.get("version", current_version)
    except Exception:
        pass

    now = datetime.now().isoformat()
    
    existing = devices.get(mac, {})
    devices[mac] = {
        "mac": mac,
        "name": existing.get("name", ""),
        "saved": existing.get("saved", True),
        "client_id": client_id or existing.get("client_id", ""),
        "ip": ip,
        "user_agent": user_agent or existing.get("user_agent", ""),
        "current_version": current_version if current_version != "0.0.0" else existing.get("current_version", "0.0.0"),
        "last_seen": now,
        "online": True,
    }

    wants_update = (pending_updates.get(mac) is True or pending_updates.get("ALL") is True)
    response = {
        "server_time": {
            "timestamp": int(time.time() * 1000),
            "timezone_offset": 180
        }
    }

    if wants_update and latest_release.get("firmware_url"):
        response["firmware"] = {
            "version": latest_release["version"],
            "url": latest_release["firmware_url"],
            "force": 1 if latest_release.get("force_update") else 0,
        }
        pending_updates.pop(mac, None)
        if "ALL" in pending_updates:
            pending_updates.pop("ALL", None)
        print(f"[OTA] {mac} ({ip}) -> Guncelleme gonderildi: {latest_release['version']}")
    else:
        print(f"[CHECK] {mac} ({ip}) v{current_version} -> Kontrol tamam")

    save_data()
    return jsonify(response)

@app.route("/api/new-release", methods=["POST"])
def new_release():
    secret = request.headers.get("X-Secret", "")
    if not secrets.compare_digest(secret, WEBHOOK_SECRET):
        abort(403)
    data = request.get_json()
    if not data:
        abort(400)

    latest_release.update({
        "version": data.get("version", "0.0.0"),
        "firmware_url": data.get("firmware_url", ""),
        "sha": data.get("sha", ""),
        "updated_at": datetime.now().isoformat(),
        "force_update": data.get("force", False),
    })
    save_data()
    return jsonify({"status": "ok", "version": latest_release["version"]})

@app.route("/api/status")
@login_required
def api_status():
    threshold = time.time() - 360  # 6 dakika (ESP her 5 dk'da bir baglaniyor)
    for dev in devices.values():
        last_seen = dev.get("last_seen")
        if not last_seen:
            dev["online"] = False  # Hic baglanmamis - cevrimdisi gozuksun
            continue
        try:
            last = datetime.fromisoformat(last_seen).timestamp()
            dev["online"] = (last > threshold)
        except Exception:
            dev["online"] = False

    return jsonify({
        "latest_release": latest_release,
        "devices": list(devices.values()),
        "pending_updates": pending_updates,
        "server_time": datetime.now().isoformat(),
    })

@app.route("/api/update/<mac>", methods=["POST"])
@login_required
def trigger_update(mac):
    if not latest_release.get("firmware_url"):
        return jsonify({"error": "Henuz yayinlanmis bir firmware (.bin) URL yok!"}), 400

    if mac == "ALL":
        pending_updates["ALL"] = True
        for m in devices:
            pending_updates[m] = True
        msg = f"Tum cihazlara ({len(devices)} adet) guncelleme isaretlendi. Baglandiklarinda yukleyecekler."
    else:
        pending_updates[mac] = True
        dev_info = devices.get(mac, {})
        is_online = dev_info.get("online", False)
        dev_name = dev_info.get("name", "") or mac
        if is_online:
            status_note = "Cihaz cevrimici, guncelleme hemen indirilecek!"
        else:
            status_note = "Cihaz su an cevrimdisi. Guncelleme kuyruğa alindi — kart internete baglanir baglanmaz otomatik yuklenecek!"
        msg = f"{dev_name}: {status_note}"

    save_data()
    return jsonify({"status": "ok", "message": msg})

@app.route("/api/cancel/<mac>", methods=["POST"])
@login_required
def cancel_update(mac):
    if mac == "ALL":
        pending_updates.clear()
    else:
        pending_updates.pop(mac, None)
    save_data()
    return jsonify({"status": "ok"})

@app.route("/api/device/save", methods=["POST"])
@login_required
def save_device_meta():
    data = request.get_json() or {}
    mac = data.get("mac", "").strip()
    name = data.get("name", "").strip()
    if not mac:
        return jsonify({"error": "Gecersiz MAC"}), 400

    if mac not in devices:
        devices[mac] = {
            "mac": mac,
            "name": name,
            "saved": True,
            "ip": "-",
            "current_version": "0.0.0",
            "last_seen": None,
            "online": False
        }
    else:
        devices[mac]["name"] = name
        devices[mac]["saved"] = True

    save_data()
    return jsonify({"status": "ok", "message": f"Cihaz kaydedildi: {name or mac}"})

@app.route("/api/device/delete/<mac>", methods=["POST"])
@login_required
def delete_device(mac):
    if mac in devices:
        devices.pop(mac)
        pending_updates.pop(mac, None)
        save_data()
        return jsonify({"status": "ok", "message": f"Cihaz silindi: {mac}"})
    return jsonify({"error": "Cihaz bulunamadi"}), 404

@app.route("/api/release", methods=["POST"])
@login_required
def manual_release():
    data = request.get_json() or {}
    latest_release.update({
        "version": data.get("version", "manual"),
        "firmware_url": data.get("url", ""),
        "updated_at": datetime.now().isoformat(),
        "force_update": data.get("force", False),
    })
    save_data()
    return jsonify({"status": "ok"})

PANEL_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Robodog OTA Kontrol Paneli</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: #090d16; color: #e2e8f0;
      min-height: 100vh; padding: 20px;
    }
    .header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 24px; padding: 16px 24px;
      background: #111827; border-radius: 16px; border: 1px solid #1f2937;
      flex-wrap: wrap; gap: 16px;
      box-shadow: 0 4px 25px rgba(0,0,0,0.4);
    }
    .header-left { display: flex; align-items: center; gap: 16px; }
    .header-logo {
      height: 48px; width: auto; border-radius: 10px;
      box-shadow: 0 0 15px rgba(6, 182, 212, 0.45);
      border: 1px solid rgba(6, 182, 212, 0.35);
    }
    .header h1 { font-size: 1.35rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.02em; }
    .header .sub { color: #06b6d4; font-size: 0.8rem; margin-top: 3px; font-weight: 500; }
    .logout-btn {
      background: #1f2937; color: #94a3b8; border: 1px solid #374151;
      padding: 9px 18px; border-radius: 10px; cursor: pointer;
      font-size: 0.85rem; text-decoration: none; font-weight: 500;
      transition: all 0.2s;
    }
    .logout-btn:hover { background: #374151; color: #e2e8f0; }
    
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; }
    @media (max-width: 860px) { .grid { grid-template-columns: 1fr; } }
    
    .card {
      background: #111827; border: 1px solid #1f2937;
      border-radius: 16px; padding: 22px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .card h2 {
      font-size: 0.82rem; font-weight: 700; margin-bottom: 16px;
      color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em;
      display: flex; align-items: center; justify-content: space-between;
    }
    .info-box {
      background: #0b1120; border-radius: 12px; padding: 16px;
      border-left: 4px solid #06b6d4;
    }
    .version-num { font-size: 2.2rem; font-weight: 800; color: #38bdf8; letter-spacing: -0.03em; }
    .meta { color: #64748b; font-size: 0.8rem; margin-top: 4px; }
    .url-text {
      color: #34d399; font-size: 0.75rem;
      word-break: break-all; margin-top: 8px; font-family: monospace;
    }
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 6px;
      padding: 9px 16px; border: none; border-radius: 8px;
      font-size: 0.85rem; font-weight: 600; cursor: pointer;
      transition: all 0.15s;
    }
    .btn-cyan   { background: #06b6d4; color: #000; font-weight: 700; }
    .btn-cyan:hover  { background: #0891b2; color: #fff; }
    .btn-green  { background: #10b981; color: #fff; }
    .btn-green:hover  { background: #059669; }
    .btn-blue   { background: #3b82f6; color: #fff; }
    .btn-blue:hover   { background: #2563eb; }
    .btn-red    { background: #ef4444; color: #fff; }
    .btn-red:hover    { background: #dc2626; }
    .btn-gray   { background: #1f2937; color: #e2e8f0; border: 1px solid #374151; }
    .btn-gray:hover   { background: #374151; }
    
    .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .stat-box {
      background: #0b1120; border-radius: 12px; padding: 16px;
      text-align: center; border: 1px solid #1f2937;
    }
    .stat-num { font-size: 2.2rem; font-weight: 800; }
    .stat-label { color: #64748b; font-size: 0.78rem; margin-top: 2px; font-weight: 600; }
    
    .form-group { margin-bottom: 12px; }
    label { display: block; font-size: 0.78rem; color: #94a3b8; margin-bottom: 5px; font-weight: 500; }
    input[type=text], input[type=url] {
      width: 100%; background: #0b1120; border: 1px solid #1f2937;
      border-radius: 8px; padding: 10px 12px; color: #e2e8f0; font-size: 0.88rem;
    }
    input:focus { outline: none; border-color: #06b6d4; }
    .check-row { display: flex; align-items: center; gap: 8px; }
    input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; }
    
    .bulk-bar {
      background: #111827; border: 1px solid #1f2937;
      border-radius: 16px; padding: 18px 24px;
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 18px; gap: 16px; flex-wrap: wrap;
    }
    .bulk-bar strong { font-size: 1rem; color: #f8fafc; }
    .bulk-bar p { color: #94a3b8; font-size: 0.85rem; margin-top: 3px; }
    
    .device {
      background: #0b1120; border-radius: 12px; padding: 14px 18px;
      margin-bottom: 10px; display: flex; align-items: center; gap: 14px;
      border: 1px solid #1f2937; transition: all 0.2s;
    }
    .device.pending-border { border-color: #f59e0b; box-shadow: 0 0 15px rgba(245,158,11,0.15); }
    .dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
    .dot-online  { background: #10b981; box-shadow: 0 0 10px #10b981; }
    .dot-offline { background: #64748b; }
    
    .dev-info { flex: 1; min-width: 0; }
    .dev-title-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .dev-name { font-weight: 700; font-size: 0.95rem; color: #f8fafc; }
    .dev-mac { font-family: monospace; font-size: 0.82rem; color: #06b6d4; }
    .dev-meta { color: #64748b; font-size: 0.76rem; margin-top: 5px; }
    .dev-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    
    .badge {
      display: inline-block; padding: 3px 10px; border-radius: 9999px;
      font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
    }
    .badge-online   { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #059669; }
    .badge-offline  { background: rgba(100, 116, 139, 0.2); color: #94a3b8; border: 1px solid #475569; }
    .badge-pending  { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #d97706; }
    .badge-updated  { background: rgba(6, 182, 212, 0.15); color: #38bdf8; border: 1px solid #0891b2; }
    .badge-old      { background: rgba(245, 158, 11, 0.1); color: #f59e0b; border: 1px solid #b45309; }
    
    .name-edit-input {
      background: #111827; border: 1px solid #374151; color: #e2e8f0;
      border-radius: 6px; padding: 4px 8px; font-size: 0.82rem; width: 140px;
    }
    
    .no-dev { text-align: center; padding: 40px 20px; color: #475569; }
    .no-dev img { width: 64px; opacity: 0.35; margin-bottom: 12px; }
    
    #toast {
      position: fixed; bottom: 24px; right: 24px;
      background: #06b6d4; color: #000; padding: 14px 24px;
      border-radius: 12px; font-weight: 600; z-index: 9999;
      display: none; box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }
    .hint { color: #475569; font-size: 0.75rem; text-align: center; margin-top: 20px; }
  </style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <img src="{{ logo_src }}" alt="Robodog Logo" class="header-logo">
    <div>
      <h1>Robodog OTA Kontrol Paneli</h1>
      <div class="sub" id="srv-time">Sunucu baglantisi bekleniyor...</div>
    </div>
  </div>
  <a href="/logout" class="logout-btn">Guvenli Cikis</a>
</div>

<!-- Toplu Guncelleme -->
<div class="bulk-bar">
  <div>
    <strong>Toplu Cihaz Guncellemesi</strong>
    <p>Kayitli tum cihazlara ayni anda guncelleme gonder. Cihaz kapali bile olsa internete girdiginde yukler.</p>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <button class="btn btn-green" onclick="updateAll()">Tumunu Guncelle</button>
    <button class="btn btn-gray"  onclick="cancelAll()">Iptal Et</button>
  </div>
</div>

<div class="grid">
  <!-- Firmware Bilgisi + Elle Giris -->
  <div class="card">
    <h2>Mevcut Yayindaki Firmware</h2>
    <div class="info-box">
      <div class="version-num" id="rel-ver">-</div>
      <div class="meta" id="rel-date">-</div>
      <div class="url-text" id="rel-url">Henuz dosya yuklenmedi</div>
    </div>

    <div style="margin-top:22px">
      <h2 style="margin-bottom:12px">Yeni Firmware URL Kaydet</h2>
      <div class="form-group">
        <label>Versiyon (Orn: 2.2.8)</label>
        <input type="text" id="in-ver" placeholder="2.2.8">
      </div>
      <div class="form-group">
        <label>Firmware Indirme URL (.bin linki)</label>
        <input type="url" id="in-url" placeholder="https://github.com/usAtJD/robodog-esp32/releases/download/v2.2.8/xiaozhi.bin">
      </div>
      <div class="form-group">
        <div class="check-row">
          <input type="checkbox" id="in-force">
          <label for="in-force" style="margin:0">Zorla Yukle (Cihaz ayni surumde olsa bile tekrar yukletir)</label>
        </div>
      </div>
      <button class="btn btn-cyan" style="width:100%" onclick="setRelease()">Firmware'i Kaydet</button>
    </div>
  </div>

  <!-- Istatistikler -->
  <div class="card">
    <h2>Cihaz Durum Ozeti</h2>
    <div class="stats-grid">
      <div class="stat-box">
        <div class="stat-num" id="s-online" style="color:#10b981">0</div>
        <div class="stat-label">Cevrimici (Online)</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" id="s-offline" style="color:#94a3b8">0</div>
        <div class="stat-label">Cevrimdisi (Offline)</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" id="s-pending" style="color:#f59e0b">0</div>
        <div class="stat-label">Guncelleme Bekleyen</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" id="s-total" style="color:#38bdf8">0</div>
        <div class="stat-label">Kayitli Toplam Cihaz</div>
      </div>
    </div>
    
    <div style="margin-top: 18px; padding: 14px; background: #0b1120; border-radius: 10px; border: 1px dashed #1f2937;">
      <p style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">
        <span style="color:#10b981; font-weight:bold;">● Cevrimici:</span> Son 5 dakikada panele sinyal gonderdi.<br>
        <span style="color:#94a3b8; font-weight:bold;">● Cevrimdisi:</span> Kapali veya internet baglantisi yok. "Guncelle"ye basarsaniz ilk internete baglandiginda guncellenir!
      </p>
    </div>
  </div>
</div>

<!-- Cihaz Listesi -->
<div class="card">
  <h2>
    <span>Kayitli Cihazlar</span>
    <span style="font-size: 0.75rem; color: #64748b; font-weight: normal;">Otomatik Yenileme: 5sn</span>
  </h2>
  <div id="dev-list">
    <div class="no-dev">
      <img src="{{ logo_src }}" alt="Robodog Logo">
      <br>Henuz hicbir cihaz baglanmadi.<br>ESP32 calistiginda bu listede kalici olarak yer alacaktir.
    </div>
  </div>
</div>

<div class="hint">Robodog OTA Server • Cihazlar kalici olarak hafizada saklanir</div>
<div id="toast"></div>

<script>
const LOGO_SRC = "{{ logo_src }}";

function toast(msg, color='#06b6d4') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = color;
  t.style.color = (color === '#06b6d4' || color === '#fbbf24') ? '#000' : '#fff';
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3500);
}

let lastData = {devices:[], pending_updates:{}, latest_release:{}};

async function fetchStatus() {
  try {
    const r = await fetch('/api/status');
    if (r.status === 401 || r.redirected) { location.reload(); return; }
    const d = await r.json();
    lastData = d;
    render(d);
  } catch(e) { console.error(e); }
}

function render(data) {
  document.getElementById('srv-time').textContent =
    'Sunucu Saati: ' + new Date(data.server_time).toLocaleString('tr-TR');

  const rel = data.latest_release || {};
  document.getElementById('rel-ver').textContent = rel.version || '-';
  document.getElementById('rel-date').textContent =
    rel.updated_at ? 'Guncellendi: ' + new Date(rel.updated_at).toLocaleString('tr-TR') : 'Guncelleme yok';
  document.getElementById('rel-url').textContent = rel.firmware_url || 'Henuz dosya yuklenmedi';

  const devs = data.devices || [];
  const pending = data.pending_updates || {};
  const onlineCount = devs.filter(d => d.online).length;
  const offlineCount = devs.length - onlineCount;
  const pendingCount = devs.filter(d => pending[d.mac] === true || pending['ALL'] === true).length;

  document.getElementById('s-online').textContent = onlineCount;
  document.getElementById('s-offline').textContent = offlineCount;
  document.getElementById('s-pending').textContent = pendingCount;
  document.getElementById('s-total').textContent = devs.length;

  const list = document.getElementById('dev-list');
  if (!devs.length) {
    list.innerHTML = `<div class="no-dev">
      <img src="${LOGO_SRC}" alt="Robodog" style="width:64px;opacity:0.3;margin-bottom:8px;"><br>
      Henuz hicbir cihaz baglanmadi.<br>ESP32 calistiginda bu listede kalici olarak gorunecektir.
    </div>`;
    return;
  }

  list.innerHTML = devs.map(dev => {
    const isPend = pending[dev.mac] === true || pending['ALL'] === true;
    const isOnline = dev.online;
    const dotCls = isOnline ? 'dot-online' : 'dot-offline';

    let badges = '';
    if (isOnline) {
      badges += '<span class="badge badge-online">Cevrimici</span> ';
    } else {
      badges += '<span class="badge badge-offline">Cevrimdisi</span> ';
    }

    if (isPend) {
      badges += '<span class="badge badge-pending">⏳ Bekleniyor</span> ';
    } else if (rel.version && rel.version !== '0.0.0' && dev.current_version === rel.version) {
      badges += '<span class="badge badge-updated">✅ Guncel</span> ';
    } else if (rel.version && rel.version !== '0.0.0' && dev.current_version && dev.current_version !== '0.0.0' && dev.current_version !== rel.version) {
      badges += '<span class="badge badge-old">⚠️ Eski Surum</span> ';
    }

    const hasCustomName = (dev.name && dev.name.trim().length > 0);
    const devDisplayName = hasCustomName ? dev.name : 'Robodog Kart';
    const lastSeenFormatted = dev.last_seen ? new Date(dev.last_seen).toLocaleString('tr-TR') : 'Bilinmiyor';

    let nameSection = '';
    if (editingMac === dev.mac) {
      nameSection = `
        <div style="display:flex;align-items:center;gap:6px;">
          <input type="text" class="name-edit-input" id="name-${dev.mac}" value="${dev.name || ''}" placeholder="Karta İsim Ver" autofocus onkeydown="if(event.key==='Enter') saveName('${dev.mac}')">
          <button class="btn btn-cyan" style="padding:5px 12px;font-size:0.78rem;" onclick="saveName('${dev.mac}')">Kaydet</button>
          <button class="btn btn-gray" style="padding:5px 10px;font-size:0.78rem;" onclick="cancelEditName()">İptal</button>
        </div>
      `;
    } else {
      nameSection = `
        <span class="dev-name" style="font-size:1.05rem;color:${hasCustomName ? '#38bdf8' : '#f8fafc'};">${devDisplayName}</span>
        <button onclick="startEditName('${dev.mac}')" style="background:none;border:none;color:#64748b;cursor:pointer;font-size:0.85rem;padding:2px 6px;" title="İsmi Değiştir">✏️</button>
      `;
    }

    return `<div class="device ${isPend ? 'pending-border' : ''}">
      <div class="dot ${dotCls}" title="${isOnline ? 'Çevrimiçi' : 'Çevrimdışı'}"></div>
      <div class="dev-info">
        <div class="dev-title-row">
          ${nameSection}
          <span class="dev-mac">[${dev.mac}]</span>
          ${badges}
        </div>
        <div class="dev-meta">
          IP: ${dev.ip || '-'} &nbsp;|&nbsp; 
          Yüklü Sürüm: <strong>v${dev.current_version || '0.0.0'}</strong> &nbsp;|&nbsp; 
          Son Bağlantı: ${lastSeenFormatted}
        </div>
      </div>
      <div class="dev-actions">
        ${isPend
          ? `<button class="btn btn-red" onclick="cancelDev('${dev.mac}')">Güncellemeyi İptal Et</button>`
          : `<button class="btn btn-green" style="font-size:0.95rem;padding:10px 20px;box-shadow:0 0 15px rgba(16,185,129,0.3);" onclick="triggerDev('${dev.mac}')">🚀 Güncelle</button>`}
        <button class="btn btn-gray" style="color:#ef4444;padding:8px 12px;" onclick="deleteDev('${dev.mac}')" title="Cihazı Listeden Sil">Sil</button>
      </div>
    </div>`;
  }).join('');
}

async function triggerDev(mac) {
  const r = await fetch('/api/update/' + mac, {method: 'POST'});
  const d = await r.json();
  r.ok ? toast(d.message || 'Guncelleme isaretlendi') : toast(d.error || 'Hata!', '#ef4444');
  fetchStatus();
}

async function updateAll() {
  const r = await fetch('/api/update/ALL', {method: 'POST'});
  const d = await r.json();
  r.ok ? toast(d.message) : toast(d.error || 'Hata!', '#ef4444');
  fetchStatus();
}

async function cancelDev(mac) {
  await fetch('/api/cancel/' + mac, {method: 'POST'});
  toast('Guncelleme iptal edildi');
  fetchStatus();
}

async function cancelAll() {
  await fetch('/api/cancel/ALL', {method: 'POST'});
  toast('Tum guncellemeler iptal edildi');
  fetchStatus();
}

let editingMac = null;

function startEditName(mac) {
  editingMac = mac;
  render(lastData);
}

function cancelEditName() {
  editingMac = null;
  render(lastData);
}

async function saveName(mac) {
  const input = document.getElementById('name-' + mac);
  const name = input ? input.value.trim() : '';
  const r = await fetch('/api/device/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mac: mac, name: name})
  });
  const d = await r.json();
  if (r.ok) {
    editingMac = null;
    toast(d.message || 'İsim başarıyla kaydedildi!');
  } else {
    toast(d.error || 'Hata!', '#ef4444');
  }
  fetchStatus();
}

async function deleteDev(mac) {
  if (!confirm(mac + ' cihazini listeden silmek istediginize emin misiniz?')) return;
  const r = await fetch('/api/device/delete/' + mac, {method: 'POST'});
  const d = await r.json();
  if (r.ok) {
    toast(d.message || 'Cihaz silindi');
  } else {
    toast(d.error || 'Hata!', '#ef4444');
  }
  fetchStatus();
}

async function setRelease() {
  const version = document.getElementById('in-ver').value.trim();
  const url = document.getElementById('in-url').value.trim();
  const force = document.getElementById('in-force').checked;
  if (!version || !url) { toast('Versiyon ve URL alanlari zorunludur!', '#ef4444'); return; }
  const r = await fetch('/api/release', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({version, url, force})
  });
  r.ok ? toast('Yeni Firmware kaydedildi: v' + version) : toast('Hata olustu!', '#ef4444');
  fetchStatus();
}

fetchStatus();
setInterval(fetchStatus, 5000);
</script>
</body>
</html>
"""

@app.route("/")
@login_required
def index():
    return render_template_string(PANEL_HTML, logo_src=LOGO_IMG_SRC)

if __name__ == "__main__":
    load_data()
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("[ROBODOG] OTA Sunucusu baslatiliyor...")
    print(f"[OK] Port: {port}")
    print(f"[OK] Kullanici: {PANEL_USERNAME}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)
