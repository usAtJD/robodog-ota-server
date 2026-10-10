# Robodog OTA Server

ESP32'lere WiFi üzerinden uzaktan firmware güncellemesi yapan web paneli.

## Hızlı Başlangıç (Lokal)

```bash
pip install flask
python server.py
# Panel: http://localhost:5000
```

## Railway'e Deploy (7/24 Online)

1. GitHub'a push et: `git push`
2. railway.app'e git → New Project → GitHub repo seç
3. Environment Variables ayarla:
   - `PANEL_USERNAME` = senin kullanıcı adın
   - `PANEL_PASSWORD` = senin şifren
   - `OTA_WEBHOOK_SECRET` = güçlü bir secret
   - `SECRET_KEY` = rastgele uzun bir string

## Ortam Değişkenleri

| Değişken | Açıklama | Varsayılan |
|---|---|---|
| `PANEL_USERNAME` | Giriş kullanıcı adı | `admin` |
| `PANEL_PASSWORD` | Giriş şifresi | `robodog123` |
| `OTA_WEBHOOK_SECRET` | GitHub Actions webhook secret | `robodog-webhook-secret` |
| `SECRET_KEY` | Flask session şifreleme | (değiştir!) |
| `PORT` | Sunucu portu | `5000` |

## API Endpoint'leri

- `GET /` - Web paneli (şifre gerekli)
- `GET/POST /ota/check` - ESP32'nin bağlandığı endpoint (şifresiz)
- `POST /api/new-release` - GitHub Actions webhook (secret ile)
