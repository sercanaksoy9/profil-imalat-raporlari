@echo off
rem Senkronu bu bilgisayarda her gun 12:00 ve 18:00'de calisacak sekilde Gorev Zamanlayici'ya ekler.
cd /d "%~dp0"
schtasks /Create /F /SC DAILY /ST 12:00 /RI 360 /DU 0007:00 /TN "Profil Imalat Senkron" /TR "cmd /c cd /d \"%~dp0.\" && git pull -q & python senkron.py"
echo.
echo Ilk senkron calisiyor...
python senkron.py --zorla
pause
