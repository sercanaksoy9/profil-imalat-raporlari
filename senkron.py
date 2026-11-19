"""ALBOND RAPORLAR klasöründeki pres üretim verisini bulut uygulamasına taşır.

Windows Görev Zamanlayıcı bunu 15 dakikada bir çalıştırır. Dashboard
Excel'i değiştiyse temizlenmiş kayıtları veri/pres_kayitlari.parquet'e
yazar, private GitHub reposuna gönderir; Streamlit Cloud uygulaması da
birkaç dakika içinde yenilenir. Değişiklik yoksa hiçbir şey yapmaz.

Elle çalıştırma:  python senkron.py   (zorla: python senkron.py --zorla)
"""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import veri

KOK = Path(__file__).resolve().parent
GUNLUK = KOK / "senkron.log"


def yaz(mesaj):
    satir = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {mesaj}"
    print(satir)
    with GUNLUK.open("a", encoding="utf-8") as f:
        f.write(satir + "\n")


def git(*arg):
    return subprocess.run(["git", *arg], cwd=KOK, capture_output=True, text=True)


def main(zorla=False):
    dosya = veri.dashboard_dosyasi(veri.VARSAYILAN_KLASOR)
    if dosya is None:
        yaz(f"Dashboard dosyası bulunamadı: {veri.VARSAYILAN_KLASOR}")
        return 1
    degisme = round(dosya.stat().st_mtime)
    onceki = veri.bulut_bilgisi()
    if not zorla and onceki.get("kaynak") == dosya.name and onceki.get("degisme") == degisme:
        return 0  # değişiklik yok

    kayitlar = veri.pres_kayitlari(dosya)
    veri.BULUT_VERI.parent.mkdir(exist_ok=True)
    kayitlar.to_parquet(veri.BULUT_VERI, index=False)
    veri.BULUT_BILGI.write_text(json.dumps({
        "kaynak": dosya.name, "degisme": degisme, "kayit": len(kayitlar),
        "olusturma": dt.datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    git("add", "veri")
    sonuc = git("commit", "-m", f"Veri güncellendi: {dosya.name} ({len(kayitlar)} kayıt)")
    if sonuc.returncode != 0 and "nothing to commit" in (sonuc.stdout + sonuc.stderr):
        yaz("Veri aynı, gönderilecek değişiklik yok")
        return 0
    gonder = git("push", "-q")
    if gonder.returncode != 0:
        yaz(f"GÖNDERİLEMEDİ: {gonder.stderr.strip()}")
        return 1
    yaz(f"Gönderildi: {dosya.name} · {len(kayitlar)} kayıt")
    return 0


if __name__ == "__main__":
    sys.exit(main(zorla="--zorla" in sys.argv))
