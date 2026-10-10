@echo off
echo ============================================
echo  Robodog OTA Sunucusu Baslatiyor...
echo ============================================

cd /d "%~dp0"

:: Python yoksa uyar
python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi! python.org'dan yukleyin.
    pause
    exit /b 1
)

:: Flask yoksa kur
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [BILGI] Flask kuruluyor...
    pip install flask
)

:: IP adresini goster
echo.
echo Bilgisayarinizin IP adresi:
ipconfig | findstr /i "IPv4"
echo.
echo Sunucu baslatiliyor: http://0.0.0.0:5000
echo Web paneli: http://localhost:5000
echo ESP32 OTA URL: http://[BU_IP]:5000/ota/check
echo.
echo sdkconfig.defaults dosyasindaki IP'yi yukardaki ile ayni yapin!
echo.

python server.py
pause
