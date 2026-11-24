@echo off
rem Senkronu bu bilgisayarda 15 dakikada bir calisacak sekilde Gorev Zamanlayici'ya ekler.
cd /d "%~dp0"
schtasks /Create /F /SC MINUTE /MO 15 /TN "Profil Imalat Senkron" /TR "cmd /c cd /d \"%~dp0\" && git pull -q & python senkron.py"
echo.
echo Ilk senkron calisiyor...
python senkron.py --zorla
pause
