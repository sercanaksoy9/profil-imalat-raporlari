"""ALBOND RAPORLAR klasöründeki raporları bulut uygulamasına taşır.

Windows Görev Zamanlayıcı bunu her gün 12:00 ve 18:00'de çalıştırır. Ekrandaki
raporların (raporlar.AKTIF_RAPORLAR) kaynak Excel'i değiştiyse temizlenmiş
veriyi veri/<anahtar>.parquet'e yazar ve private GitHub reposuna gönderir;
Streamlit Cloud uygulaması birkaç dakika içinde yenilenir. Değişiklik
yoksa hiçbir şey yapmaz.

Elle çalıştırma:  python senkron.py   (zorla: python senkron.py --zorla)
"""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import raporlar
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
    # Senkron birden çok bilgisayarda çalışabilir: önce diğerinin gönderdiğini al
    cek = git("pull", "--rebase", "--autostash", "-q")
    if cek.returncode != 0:
        yaz(f"ÇEKİLEMEDİ: {cek.stderr.strip()}")
    bilgi = veri.bulut_bilgisi()
    onceki = bilgi.get("raporlar", {})
    yeni, degisen = {}, []
    for anahtar in raporlar.AKTIF_RAPORLAR:
        yol = raporlar.kaynak_dosyasi(anahtar)
        if yol is None:
            yaz(f"{anahtar}: kaynak dosya bulunamadı")
            if anahtar in onceki:
                yeni[anahtar] = onceki[anahtar]
            continue
        durum = {"kaynak": yol.name, "degisme": round(yol.stat().st_mtime)}
        yeni[anahtar] = durum
        eski = onceki.get(anahtar, {})
        if zorla or (eski.get("kaynak"), eski.get("degisme")) != (durum["kaynak"], durum["degisme"]):
            tablo = raporlar.oku(anahtar, yol)
            hedef = raporlar.bulut_dosyasi(anahtar)
            hedef.parent.mkdir(exist_ok=True)
            tablo.to_parquet(hedef, index=False)
            durum["kayit"] = len(tablo)
            degisen.append(f"{anahtar} ({len(tablo)})")
        else:
            durum["kayit"] = onceki[anahtar].get("kayit")
    # Ekrandan kaldırılmış raporların eski bulut dosyaları silinir
    for eski in (veri.UYGULAMA_KLASORU / "veri").glob("*.parquet"):
        if eski.stem not in raporlar.AKTIF_RAPORLAR:
            eski.unlink()
            degisen.append(f"{eski.stem} kaldırıldı")
    if not degisen:
        return 0

    veri.BULUT_BILGI.write_text(json.dumps({
        "raporlar": yeni, "olusturma": dt.datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    git("add", "-A", "veri")
    sonuc = git("commit", "-m", "Veri güncellendi: " + ", ".join(degisen))
    if sonuc.returncode != 0 and "nothing to commit" in (sonuc.stdout + sonuc.stderr):
        return 0
    gonder = git("push", "-q")
    if gonder.returncode != 0:
        # Diğer bilgisayar arada göndermişse: üstüne al (çakışmada bizimki geçerli), tekrar dene
        git("pull", "--rebase", "-X", "theirs", "-q")
        gonder = git("push", "-q")
    if gonder.returncode != 0:
        yaz(f"GÖNDERİLEMEDİ: {gonder.stderr.strip()}")
        return 1
    yaz("Gönderildi: " + ", ".join(degisen))
    return 0


if __name__ == "__main__":
    sys.exit(main(zorla="--zorla" in sys.argv))
