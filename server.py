#!/usr/bin/env python3
"""
Robodog OTA Kontrol Sunucusu
- Giriş şifresi korumalı
- Her yerden erişilebilir (Railway, Render, vb.)
- ESP32'lere güncelleme gönderir
"""

import os
import json
import time
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
from flask import (Flask, request, jsonify, render_template_string,
                   redirect, url_for, session, abort)

app = Flask(__name__)

# ─── Ayarlar (ortam değişkenlerinden veya varsayılanlardan) ───────────────────
app.secret_key = os.environ.get("SECRET_KEY", "robodog-gizli-anahtar-degistir-bunu")

# Giriş şifresi - ortam değişkeni ile ayarla (Railway'de bunu yapacaksın)
PANEL_USERNAME = os.environ.get("PANEL_USERNAME", "admin")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "robodog123")

# GitHub Actions webhook secret
WEBHOOK_SECRET  = os.environ.get("OTA_WEBHOOK_SECRET", "robodog-webhook-secret")

# Veri dosyası
DATA_FILE = Path("ota_data.json")

# ─── Veri ────────────────────────────────────────────────────────────────────
devices          = {}   # mac -> device_info
pending_updates  = {}   # mac -> True/False
latest_release   = {
    "version"      : "0.0.0",
    "firmware_url" : "",
    "sha"          : "",
    "updated_at"   : None,
    "force_update" : False,
}


def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "devices"        : devices,
                "pending_updates": pending_updates,
                "latest_release" : latest_release,
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
            print(f"[OK] Veri yuklendi: {len(devices)} cihaz")
        except Exception as e:
            print(f"[UYARI] Veri yuklenemedi: {e}")


# ─── Giriş yönetimi ──────────────────────────────────────────────────────────

def login_required(f):
    """Oturum açılmamışsa login sayfasına yönlendir"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


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
      background: #0f172a; color: #e2e8f0;
      min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
    }
    .card {
      background: #1e293b; border: 1px solid #334155;
      border-radius: 16px; padding: 40px;
      width: 100%; max-width: 380px;
      box-shadow: 0 25px 50px rgba(0,0,0,0.5);
    }
    .logo {
      text-align: center; margin-bottom: 32px;
    }
    .logo .icon { font-size: 3.5rem; display: block; margin-bottom: 8px; }
    .logo h1 { font-size: 1.4rem; font-weight: 700; }
    .logo p { color: #64748b; font-size: 0.85rem; margin-top: 4px; }
    
    .form-group { margin-bottom: 16px; }
    label { display: block; font-size: 0.8rem; color: #94a3b8;
            margin-bottom: 6px; font-weight: 500; }
    input {
      width: 100%; background: #0f172a; border: 1px solid #334155;
      border-radius: 8px; padding: 10px 14px;
      color: #e2e8f0; font-size: 0.95rem; transition: border 0.2s;
    }
    input:focus { outline: none; border-color: #3b82f6; }
    
    button {
      width: 100%; background: #3b82f6; color: white; border: none;
      border-radius: 8px; padding: 12px; font-size: 0.95rem;
      font-weight: 600; cursor: pointer; transition: background 0.2s;
      margin-top: 8px;
    }
    button:hover { background: #2563eb; }
    
    .error {
      background: #450a0a; border: 1px solid #7f1d1d;
      color: #fca5a5; border-radius: 8px;
      padding: 10px 14px; margin-bottom: 16px; font-size: 0.875rem;
    }
    .footer {
      text-align: center; margin-top: 24px;
      color: #475569; font-size: 0.75rem;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">
      <span class="icon">&#128021;</span>
      <h1>Robodog OTA</h1>
      <p>Kontrol Paneli</p>
    </div>
    
    {% if error %}
    <div class="error">&#x26A0; {{ error }}</div>
    {% endif %}
    
    <form method="POST">
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
    
    <div class="footer">
      Robodog OTA Panel v1.0
    </div>
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
        
        # Sabit süreli karşılaştırma (timing attack önlemi)
        u_ok = secrets.compare_digest(username, PANEL_USERNAME)
        p_ok = secrets.compare_digest(password, PANEL_PASSWORD)
        
        if u_ok and p_ok:
            session["logged_in"] = True
            session.permanent = True
            app.permanent_session_lifetime = timedelta(days=30)
            print(f"[LOGIN] Giris basarili: {request.remote_addr}")
            return redirect(url_for("index"))
        else:
            error = "Kullanici adi veya sifre yanlis!"
            print(f"[LOGIN] Basarisiz giris denemesi: {request.remote_addr}")
    
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── ESP32 API Endpoint'leri (şifre gerektirmez!) ────────────────────────────

@app.route("/ota/check", methods=["POST", "GET"])
def ota_check():
    """ESP32 boot'ta ve periyodik olarak buraya bağlanır"""
    mac        = request.headers.get("Device-Id", "unknown")
    client_id  = request.headers.get("Client-Id", "")
    user_agent = request.headers.get("User-Agent", "")
    current_version = "0.0.0"
    ip = request.remote_addr

    try:
        body = request.get_json(silent=True) or {}
        current_version = body.get("version", current_version)
    except Exception:
        pass

    now = datetime.now().isoformat()
    devices[mac] = {
        "mac"            : mac,
        "client_id"      : client_id,
        "ip"             : ip,
        "user_agent"     : user_agent,
        "current_version": current_version,
        "last_seen"      : now,
        "online"         : True,
    }

    wants_update = (pending_updates.get(mac) is True or
                    pending_updates.get("ALL") is True)

    response = {
        "server_time": {
            "timestamp"      : int(time.time() * 1000),
            "timezone_offset": 180   # UTC+3 Türkiye
        }
    }

    if wants_update and latest_release.get("firmware_url"):
        response["firmware"] = {
            "version": latest_release["version"],
            "url"    : latest_release["firmware_url"],
            "force"  : 1 if latest_release.get("force_update") else 0,
        }
        # Güncelleme gönderildi → işareti kaldır
        pending_updates.pop(mac, None)
        if "ALL" in pending_updates:
            pending_updates.pop("ALL", None)

        print(f"[OTA] {mac} ({ip}) -> guncelleme gonderildi: {latest_release['version']}")
    else:
        print(f"[CHECK] {mac} ({ip}) v{current_version} -> guncel")

    save_data()
    return jsonify(response)


@app.route("/api/new-release", methods=["POST"])
def new_release():
    """GitHub Actions bu endpoint'i çağırır"""
    secret = request.headers.get("X-Secret", "")
    if not secrets.compare_digest(secret, WEBHOOK_SECRET):
        print(f"[GUVENLIK] Yetkisiz istek! IP: {request.remote_addr}")
        abort(403)

    data = request.get_json()
    if not data:
        abort(400)

    latest_release.update({
        "version"     : data.get("version", "0.0.0"),
        "firmware_url": data.get("firmware_url", ""),
        "sha"         : data.get("sha", ""),
        "updated_at"  : datetime.now().isoformat(),
        "force_update": data.get("force", False),
    })

    print(f"[RELEASE] Yeni versiyon: {latest_release['version']} -> {latest_release['firmware_url']}")
    save_data()
    return jsonify({"status": "ok", "version": latest_release["version"]})


# ─── Web Panel API'leri (şifre gerektirir) ───────────────────────────────────

@app.route("/api/status")
@login_required
def api_status():
    threshold = time.time() - 120   # 2 dakika
    for dev in devices.values():
        try:
            last = datetime.fromisoformat(dev["last_seen"]).timestamp()
            dev["online"] = last > threshold
        except Exception:
            dev["online"] = False

    return jsonify({
        "latest_release": latest_release,
        "devices"       : list(devices.values()),
        "pending_updates": pending_updates,
        "server_time"   : datetime.now().isoformat(),
    })


@app.route("/api/update/<mac>", methods=["POST"])
@login_required
def trigger_update(mac):
    if not latest_release.get("firmware_url"):
        return jsonify({"error": "Henuz yuklenmis bir firmware yok!"}), 400

    if mac == "ALL":
        pending_updates["ALL"] = True
        for m in devices:
            pending_updates[m] = True
        msg = f"Tum cihazlara ({len(devices)}) guncelleme isaretlendi"
    else:
        pending_updates[mac] = True
        msg = f"{mac} cihazina guncelleme isaretlendi"

    print(f"[PANEL] {msg}")
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


@app.route("/api/release", methods=["POST"])
@login_required
def manual_release():
    data = request.get_json()
    latest_release.update({
        "version"     : data.get("version", "manual"),
        "firmware_url": data.get("url", ""),
        "updated_at"  : datetime.now().isoformat(),
        "force_update": data.get("force", False),
    })
    save_data()
    return jsonify({"status": "ok"})


# ─── Ana Sayfa ────────────────────────────────────────────────────────────────

PANEL_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Robodog OTA Paneli</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: #0f172a; color: #e2e8f0;
      min-height: 100vh; padding: 20px;
    }
    .header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 24px; padding: 16px 24px;
      background: #1e293b; border-radius: 12px; border: 1px solid #334155;
      flex-wrap: wrap; gap: 12px;
    }
    .header-left { display: flex; align-items: center; gap: 12px; }
    .header h1 { font-size: 1.4rem; font-weight: 700; }
    .header .sub { color: #94a3b8; font-size: 0.8rem; margin-top: 2px; }
    .logout-btn {
      background: #334155; color: #94a3b8; border: none;
      padding: 8px 16px; border-radius: 8px; cursor: pointer;
      font-size: 0.85rem; text-decoration: none; display: inline-block;
    }
    .logout-btn:hover { background: #475569; color: #e2e8f0; }
    
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
    @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
    
    .card {
      background: #1e293b; border: 1px solid #334155;
      border-radius: 12px; padding: 20px;
    }
    .card h2 {
      font-size: 0.8rem; font-weight: 600; margin-bottom: 16px;
      color: #64748b; text-transform: uppercase; letter-spacing: 0.08em;
    }
    .info-box {
      background: #0f172a; border-radius: 8px; padding: 14px;
      border-left: 3px solid #3b82f6;
    }
    .version-num { font-size: 2rem; font-weight: 700; color: #60a5fa; }
    .meta { color: #64748b; font-size: 0.78rem; margin-top: 4px; }
    .url-text {
      color: #34d399; font-size: 0.72rem;
      word-break: break-all; margin-top: 8px;
    }
    .btn {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 9px 16px; border: none; border-radius: 8px;
      font-size: 0.875rem; font-weight: 500; cursor: pointer;
      transition: all 0.15s;
    }
    .btn-green  { background: #10b981; color: #fff; }
    .btn-green:hover  { background: #059669; }
    .btn-blue   { background: #3b82f6; color: #fff; }
    .btn-blue:hover   { background: #2563eb; }
    .btn-red    { background: #ef4444; color: #fff; }
    .btn-red:hover    { background: #dc2626; }
    .btn-gray   { background: #334155; color: #e2e8f0; }
    .btn-gray:hover   { background: #475569; }
    .btn:disabled { opacity: 0.4; cursor: not-allowed; }
    
    /* Stats */
    .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .stat-box {
      background: #0f172a; border-radius: 8px; padding: 14px;
      text-align: center;
    }
    .stat-num { font-size: 2rem; font-weight: 700; }
    .stat-label { color: #64748b; font-size: 0.75rem; margin-top: 2px; }
    
    /* Form */
    .form-group { margin-bottom: 12px; }
    label { display: block; font-size: 0.78rem; color: #94a3b8; margin-bottom: 5px; }
    input[type=text], input[type=url] {
      width: 100%; background: #0f172a; border: 1px solid #334155;
      border-radius: 6px; padding: 9px 12px; color: #e2e8f0; font-size: 0.875rem;
    }
    input:focus { outline: none; border-color: #3b82f6; }
    .check-row { display: flex; align-items: center; gap: 8px; }
    input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; }
    
    /* Toplu bar */
    .bulk-bar {
      background: #1e293b; border: 1px solid #334155;
      border-radius: 12px; padding: 16px 20px;
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 16px; gap: 12px; flex-wrap: wrap;
    }
    .bulk-bar p { color: #94a3b8; font-size: 0.85rem; margin-top: 3px; }
    
    /* Cihaz */
    .device {
      background: #0f172a; border-radius: 8px; padding: 12px 16px;
      margin-bottom: 8px; display: flex; align-items: center; gap: 12px;
      border: 1px solid #1e293b; transition: border 0.2s;
    }
    .device.pending-border { border-color: #f59e0b; }
    .dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
    .dot-green  { background: #10b981; box-shadow: 0 0 6px #10b981; }
    .dot-yellow { background: #f59e0b; box-shadow: 0 0 6px #f59e0b; }
    .dot-gray   { background: #475569; }
    .dev-info { flex: 1; min-width: 0; }
    .dev-mac { font-family: monospace; font-size: 0.88rem; font-weight: 600; }
    .dev-meta { color: #64748b; font-size: 0.73rem; margin-top: 3px; }
    .dev-actions { display: flex; gap: 6px; }
    
    .badge {
      display: inline-block; padding: 2px 9px; border-radius: 9999px;
      font-size: 0.68rem; font-weight: 600;
    }
    .badge-green  { background: #064e3b; color: #34d399; }
    .badge-yellow { background: #451a03; color: #fbbf24; }
    .badge-gray   { background: #1e293b; color: #64748b; }
    
    .no-dev {
      text-align: center; padding: 48px 20px; color: #475569;
    }
    .no-dev .icon { font-size: 3rem; display: block; margin-bottom: 10px; }
    
    #toast {
      position: fixed; bottom: 24px; right: 24px;
      background: #10b981; color: #fff; padding: 12px 20px;
      border-radius: 10px; font-weight: 500; z-index: 999;
      display: none;
    }
    .hint { color: #475569; font-size: 0.72rem; text-align: center; margin-top: 16px; }
  </style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <span style="font-size:2rem">&#128021;</span>
    <div>
      <h1>Robodog OTA Paneli</h1>
      <div class="sub" id="srv-time">Yukleniyor...</div>
    </div>
  </div>
  <a href="/logout" class="logout-btn">Cikis Yap</a>
</div>

<!-- Toplu güncelleme -->
<div class="bulk-bar">
  <div>
    <strong>Toplu Guncelleme</strong>
    <p>Tum cihazlara ayni anda guncelleme gonder</p>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <button class="btn btn-green" onclick="updateAll()">Tumunu Guncelle</button>
    <button class="btn btn-gray"  onclick="cancelAll()">Iptal Et</button>
  </div>
</div>

<div class="grid">
  <!-- Firmware bilgisi + elle giriş -->
  <div class="card">
    <h2>Mevcut Firmware</h2>
    <div class="info-box">
      <div class="version-num" id="rel-ver">-</div>
      <div class="meta"        id="rel-date">-</div>
      <div class="url-text"   id="rel-url">-</div>
    </div>

    <div style="margin-top:20px">
      <h2 style="margin-bottom:14px">Elle Firmware URL Gir</h2>
      <div class="form-group">
        <label>Versiyon (orn: 2.2.7)</label>
        <input type="text" id="in-ver" placeholder="2.2.7">
      </div>
      <div class="form-group">
        <label>Firmware URL (.bin dosyasi)</label>
        <input type="url" id="in-url" placeholder="https://github.com/.../firmware.bin">
      </div>
      <div class="form-group">
        <div class="check-row">
          <input type="checkbox" id="in-force">
          <label for="in-force" style="margin:0">Zorla yukle (ayni surum olsa bile)</label>
        </div>
      </div>
      <button class="btn btn-blue" onclick="setRelease()">Kaydet</button>
    </div>
  </div>

  <!-- İstatistikler -->
  <div class="card">
    <h2>Istatistikler</h2>
    <div class="stats-grid">
      <div class="stat-box">
        <div class="stat-num" id="s-online"  style="color:#10b981">0</div>
        <div class="stat-label">Online</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" id="s-pending" style="color:#f59e0b">0</div>
        <div class="stat-label">Bekleyen</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" id="s-total"   style="color:#60a5fa">0</div>
        <div class="stat-label">Toplam</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" id="s-old"     style="color:#a78bfa">0</div>
        <div class="stat-label">Eski Surum</div>
      </div>
    </div>
  </div>
</div>

<!-- Cihaz listesi -->
<div class="card">
  <h2>Bagli Cihazlar</h2>
  <div id="dev-list">
    <div class="no-dev">
      <span class="icon">&#128225;</span>
      Henuz baglanan cihaz yok.<br>
      ESP karta yuklendikten sonra burada gorunecek.
    </div>
  </div>
</div>

<div class="hint">Otomatik yenileme: 5sn | OTA URL: /ota/check</div>
<div id="toast"></div>

<script>
function toast(msg, color='#10b981') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.background = color;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

async function fetchStatus() {
  try {
    const r = await fetch('/api/status');
    if (r.status === 401 || r.redirected) { location.reload(); return; }
    const d = await r.json();
    render(d);
  } catch(e) { console.error(e); }
}

function render(data) {
  document.getElementById('srv-time').textContent =
    'Sunucu: ' + new Date(data.server_time).toLocaleString('tr-TR');

  const rel = data.latest_release;
  document.getElementById('rel-ver').textContent  = rel.version || '-';
  document.getElementById('rel-date').textContent =
    rel.updated_at ? new Date(rel.updated_at).toLocaleString('tr-TR') : '-';
  document.getElementById('rel-url').textContent  = rel.firmware_url || 'URL girilmedi';

  const devs    = data.devices || [];
  const pending = data.pending_updates || {};
  const online  = devs.filter(d => d.online).length;
  const pend    = devs.filter(d => pending[d.mac]).length;
  const old     = devs.filter(d => d.current_version !== rel.version &&
                                   rel.version !== '0.0.0').length;

  document.getElementById('s-online').textContent  = online;
  document.getElementById('s-pending').textContent = pend;
  document.getElementById('s-total').textContent   = devs.length;
  document.getElementById('s-old').textContent     = old;

  const list = document.getElementById('dev-list');
  if (!devs.length) {
    list.innerHTML = `<div class="no-dev">
      <span class="icon">&#128225;</span>
      Henuz baglanan cihaz yok.<br>ESP karta yuklendikten sonra burada gorunecek.
    </div>`;
    return;
  }

  list.innerHTML = devs.map(dev => {
    const isPend    = pending[dev.mac] === true || pending['ALL'] === true;
    const isOnline  = dev.online;
    const isOld     = dev.current_version !== rel.version && rel.version !== '0.0.0';

    const dotCls = isPend ? 'dot-yellow' : (isOnline ? 'dot-green' : 'dot-gray');
    const badge  = isPend
      ? '<span class="badge badge-yellow">Bekliyor</span>'
      : isOld
        ? '<span class="badge badge-gray">Eski</span>'
        : '<span class="badge badge-green">Guncel</span>';

    return `<div class="device ${isPend ? 'pending-border' : ''}">
      <div class="dot ${dotCls}"></div>
      <div class="dev-info">
        <div class="dev-mac">${dev.mac}</div>
        <div class="dev-meta">
          IP: ${dev.ip || '-'} &nbsp;|&nbsp;
          v${dev.current_version || '?'} &nbsp;|&nbsp;
          ${dev.last_seen ? new Date(dev.last_seen).toLocaleTimeString('tr-TR') : '-'} &nbsp;
          ${badge}
        </div>
      </div>
      <div class="dev-actions">
        ${isPend
          ? `<button class="btn btn-gray" onclick="cancelDev('${dev.mac}')">Iptal</button>`
          : `<button class="btn btn-green" onclick="triggerDev('${dev.mac}')">Guncelle</button>`}
      </div>
    </div>`;
  }).join('');
}

async function triggerDev(mac) {
  const r = await fetch('/api/update/'+mac, {method:'POST'});
  const d = await r.json();
  r.ok ? toast('Guncelleme isaretlendi: ' + mac)
       : toast(d.error || 'Hata!', '#ef4444');
  fetchStatus();
}
async function updateAll() {
  const r = await fetch('/api/update/ALL', {method:'POST'});
  const d = await r.json();
  r.ok ? toast(d.message) : toast(d.error || 'Hata!', '#ef4444');
  fetchStatus();
}
async function cancelDev(mac) {
  await fetch('/api/cancel/'+mac, {method:'POST'});
  toast('Iptal edildi'); fetchStatus();
}
async function cancelAll() {
  await fetch('/api/cancel/ALL', {method:'POST'});
  toast('Tum guncellemeler iptal edildi'); fetchStatus();
}
async function setRelease() {
  const version = document.getElementById('in-ver').value.trim();
  const url     = document.getElementById('in-url').value.trim();
  const force   = document.getElementById('in-force').checked;
  if (!version || !url) { toast('Versiyon ve URL zorunlu!', '#ef4444'); return; }
  const r = await fetch('/api/release', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({version, url, force})
  });
  r.ok ? toast('Firmware kaydedildi: v'+version) : toast('Hata!', '#ef4444');
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
    return render_template_string(PANEL_HTML)


if __name__ == "__main__":
    load_data()
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("[ROBODOG] OTA Sunucusu baslatiliyor...")
    print(f"[OK] http://0.0.0.0:{port}")
    print(f"[OK] Kullanici: {PANEL_USERNAME}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)
