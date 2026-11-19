"""Profil İmalat Üretim Raporları: veri bulma ve temizleme.

Veri klasörü (öncelik sırasıyla):
1. URETIM_VERI_KLASORU ortam değişkeni
2. OneDrive'daki ALBOND RAPORLAR klasörü (bu bilgisayar)
3. Uygulamanın yanındaki 'veri' klasörü (bulut kopyası)

Pres üretim kayıtları, klasördeki en yeni *DASHBOARD*.xlsx dosyasının
'Temiz veri' sayfasından okunur ('Eski' adlı klasörler atlanır).
"""
import json
import os
from pathlib import Path

import pandas as pd

UYGULAMA_KLASORU = Path(__file__).resolve().parent
VARSAYILAN_KLASOR = Path(r"C:\Users\seco_\OneDrive\Masaüstü\ALBOND RAPORLAR")
PRES_ADI = {"6''": '6"', "8''": '8"'}


def veri_klasoru():
    aday = os.environ.get("URETIM_VERI_KLASORU")
    for yol in (Path(aday) if aday else None, VARSAYILAN_KLASOR,
                UYGULAMA_KLASORU / "veri"):
        if yol and yol.exists():
            return yol
    return UYGULAMA_KLASORU / "veri"


def _eski_mi(yol, kok):
    return any("eski" in p.lower() for p in yol.relative_to(kok).parts[:-1])


def dashboard_dosyasi(kok=None):
    """Klasördeki en yeni pres üretim dashboard dosyası (yoksa None)."""
    kok = Path(kok or veri_klasoru())
    adaylar = [y for y in kok.rglob("*.xlsx")
               if "dashboard" in y.name.lower() and not y.name.startswith("~$")
               and not _eski_mi(y, kok)]
    return max(adaylar, key=lambda y: y.stat().st_mtime) if adaylar else None


# Bulut kopyası: senkron.py, Excel'den temizlenmiş kayıtları buraya yazar
BULUT_VERI = UYGULAMA_KLASORU / "veri" / "pres_kayitlari.parquet"
BULUT_BILGI = UYGULAMA_KLASORU / "veri" / "kaynak.json"


def kaynak():
    """Panonun okuyacağı veri: ('excel', yol) bu bilgisayarda, yoksa
    ('ozet', parquet yolu) bulutta. Hiçbiri yoksa (None, None)."""
    dosya = dashboard_dosyasi()
    if dosya is not None:
        return "excel", dosya
    if BULUT_VERI.exists():
        return "ozet", BULUT_VERI
    return None, None


def bulut_bilgisi():
    try:
        return json.loads(BULUT_BILGI.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def klasor_imzasi(kok=None):
    """Klasördeki Excel dosyalarının adı + değişme zamanı; değişince
    pano kendini yeniler."""
    kok = Path(kok or veri_klasoru())
    if not kok.exists():
        return ()
    return tuple(sorted(
        (str(y.relative_to(kok)), round(y.stat().st_mtime))
        for y in kok.rglob("*.xls*") if not y.name.startswith("~$")))


def _dakika(seri):
    """'0:15:00', timedelta, datetime.time ya da sayı -> dakika."""
    def cevir(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if hasattr(v, "total_seconds"):
            return v.total_seconds() / 60
        if hasattr(v, "hour"):
            return v.hour * 60 + v.minute + v.second / 60
        try:
            return pd.to_timedelta(str(v).strip()).total_seconds() / 60
        except (ValueError, TypeError):
            return 0.0
    return seri.map(cevir)


def pres_kayitlari(yol):
    """'Temiz veri' sayfasını okuyup sade sütunlara çevirir."""
    ham = pd.read_excel(yol, sheet_name="Temiz veri")
    sutun = {
        "Tarih": "tarih", "Vardiya": "vardiya", "Operatör": "operator",
        "PRES ADI": "pres", "Kalıp No Normalize": "kalip",
        "Piston Hızı (mm/s)": "piston", "Kalıp Sıcaklığı (°C)": "kalip_sic",
        "Billet Sıcaklığı (°C)": "biyet_sic", "Biyet Boyu (mm)": "biyet_boyu",
        "Adet": "biyet_adet", "Kg": "brut_kg", "Gramaj (kg/mt)": "gramaj",
        "Net Üretim (kg)": "net_kg", "Fark": "sure_dk", "Alaşım": "alasim",
        "Yüzey": "yuzey", "Duruş Tipi": "durus_tipi", "Sütun1": "musteri",
        "Açıklama": "aciklama",
    }
    d = ham.rename(columns=sutun)
    d = d[[c for c in sutun.values() if c in d.columns]].copy()
    d["durus_dk"] = _dakika(ham["Duruş Süresi"]) if "Duruş Süresi" in ham else 0.0
    d["tarih"] = pd.to_datetime(d["tarih"], errors="coerce")
    d = d[d["tarih"].notna() & d["pres"].notna()]
    d["pres"] = d["pres"].map(PRES_ADI).fillna(d["pres"].astype(str))
    for k in ("piston", "kalip_sic", "biyet_sic", "biyet_boyu", "biyet_adet",
              "brut_kg", "gramaj", "net_kg", "sure_dk", "kalip", "vardiya"):
        if k in d:
            d[k] = pd.to_numeric(d[k], errors="coerce")
    for k in ("brut_kg", "net_kg", "sure_dk", "biyet_adet", "durus_dk"):
        d[k] = d[k].fillna(0).clip(lower=0)
    d["fire_kg"] = (d["brut_kg"] - d["net_kg"]).clip(lower=0)
    d["kalip"] = d["kalip"].astype("Int64")
    for k in ("operator", "durus_tipi", "musteri", "alasim", "yuzey"):
        if k in d:
            d[k] = d[k].astype("string").str.strip().str.upper()
    d["ay"] = d["tarih"].dt.to_period("M").dt.to_timestamp()
    d["hafta"] = d["tarih"].dt.to_period("W").dt.start_time
    d["gun"] = d["tarih"].dt.normalize()
    return d.reset_index(drop=True)


def ozet(d):
    """Seçili kayıtların ana göstergeleri."""
    brut, net = d["brut_kg"].sum(), d["net_kg"].sum()
    saat = d["sure_dk"].sum() / 60
    return {
        "net_kg": net, "brut_kg": brut,
        "fire_oran": (brut - net) / brut if brut else 0.0,
        "saat": saat, "kg_saat": net / saat if saat else 0.0,
        "biyet": d["biyet_adet"].sum(),
        "kalip": d["kalip"].nunique(),
        "durus_saat": d["durus_dk"].sum() / 60,
        "kayit": len(d),
    }


def grupla(d, anahtar):
    """Gruplara göre net/brüt üretim, fire %, saat ve net kg/saat."""
    g = d.groupby(anahtar, dropna=False).agg(
        net_kg=("net_kg", "sum"), brut_kg=("brut_kg", "sum"),
        sure_dk=("sure_dk", "sum"), biyet=("biyet_adet", "sum"),
        kayit=("net_kg", "size")).reset_index()
    g["saat"] = g["sure_dk"] / 60
    g["kg_saat"] = (g["net_kg"] / g["saat"]).where(g["saat"] > 0)
    g["fire_oran"] = ((g["brut_kg"] - g["net_kg"]) / g["brut_kg"]).where(g["brut_kg"] > 0)
    return g.drop(columns="sure_dk")
