"""Sayfaların ortak yardımcıları: biçimlendirme, renkler, veri yükleme."""
import altair as alt
import pandas as pd
import streamlit as st

import raporlar
import veri

AY_ADI = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki",
          "Kas", "Ara"]
# Doğrulanmış kategorik paletin sabit sırası (renk varlığı izler, sırayı değil)
PALET = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
         "#6250d6", "#e34948"]
PRES_RENK = alt.Scale(domain=['6"', '8"'], range=PALET[:2])
TEK_RENK = PALET[0]


def sayi(v, ondalik=0):
    """Türkçe sayı biçimi: 1.234.567,8"""
    if v is None or pd.isna(v):
        return "–"
    metin = f"{v:,.{ondalik}f}"
    return metin.replace(",", "X").replace(".", ",").replace("X", ".")


def ay_etiketi(t):
    t = pd.Timestamp(t)
    return f"{AY_ADI[t.month - 1]} {t.year}"


def tarih_saat(zaman):
    return (pd.Timestamp(zaman, unit="s", tz="UTC").tz_convert("Europe/Istanbul")
            .strftime("%d.%m.%Y %H:%M"))


@st.cache_data(show_spinner="Rapor okunuyor...")
def _excelden(anahtar, yol, degisme):
    return raporlar.oku(anahtar, yol)


@st.cache_data(show_spinner="Rapor okunuyor...")
def _ozetten(yol, degisme):
    return pd.read_parquet(yol)


def rapor_verisi(anahtar):
    """(tablo, kaynak dosya adı, değişme zamanı, mod) ya da veri yoksa None.
    Bu bilgisayarda Excel'den, bulutta senkron özetinden okunur."""
    yol = raporlar.kaynak_dosyasi(anahtar)
    if yol is not None:
        degisme = yol.stat().st_mtime
        return _excelden(anahtar, str(yol), degisme), yol.name, degisme, "excel"
    bulut = raporlar.bulut_dosyasi(anahtar)
    if bulut.exists():
        bilgi = veri.bulut_bilgisi().get("raporlar", {}).get(anahtar, {})
        degisme = bilgi.get("degisme", bulut.stat().st_mtime)
        return (_ozetten(str(bulut), bulut.stat().st_mtime),
                bilgi.get("kaynak", bulut.name), degisme, "bulut")
    return None


def kaynak_notu(ad, degisme, mod):
    ek = ("klasör 1 dakikada bir kontrol edilir" if mod == "excel"
          else "klasöre giren veri birkaç dakika içinde buraya gelir")
    st.caption(f"📁 Kaynak: **{ad}** · son değişiklik {tarih_saat(degisme)} · {ek}")


def donem_sec(ilk_gun, son_gun, varsayilan="Yılbaşından beri"):
    """Dönem seçimi (hazır dönemler + özel aralık). (başlangıç, bitiş) döner;
    özel aralıkta bitiş seçilmediyse sayfayı durdurur."""
    import datetime as dt
    bugun = son_gun
    ay_basi = bugun.replace(day=1)
    gecen_ay_sonu = ay_basi - dt.timedelta(days=1)
    hazir = {
        "Bu ay": (ay_basi, bugun),
        "Geçen ay": (gecen_ay_sonu.replace(day=1), gecen_ay_sonu),
        "Son 7 gün": (bugun - dt.timedelta(days=6), bugun),
        "Son 30 gün": (bugun - dt.timedelta(days=29), bugun),
        "Son 3 ay": ((pd.Timestamp(bugun) - pd.DateOffset(months=3)).date()
                     + dt.timedelta(days=1), bugun),
        "Yılbaşından beri": (ilk_gun, bugun),
        "Özel aralık": None,
    }
    f2, f3 = st.columns([1.3, 1.7])
    secilen = f2.selectbox("Dönem", list(hazir), index=list(hazir).index(varsayilan))
    if hazir[secilen] is None:
        secim = f3.date_input("Tarih aralığı", value=(ay_basi, bugun), min_value=ilk_gun,
                              max_value=bugun, format="DD.MM.YYYY")
        if not isinstance(secim, (tuple, list)) or len(secim) < 2:
            st.info("Bitiş tarihini de seçin.")
            st.stop()
        return secim[0], secim[1]
    bas, bit = hazir[secilen]
    bas = max(bas, ilk_gun)
    f3.text_input("Tarih aralığı", f"{bas:%d.%m.%Y} – {bit:%d.%m.%Y}", disabled=True)
    return bas, bit
