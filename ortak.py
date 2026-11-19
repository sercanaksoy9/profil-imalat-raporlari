"""Sayfaların ortak yardımcıları: biçimlendirme, renkler, veri yükleme."""
import altair as alt
import pandas as pd
import streamlit as st

import raporlar
import veri

AY_ADI = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki",
          "Kas", "Ara"]
# Doğrulanmış kategorik paletin koyu zemin tonları, sabit sıra
# (renk varlığı izler, sırayı değil)
PALET = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c",
         "#9085e9", "#e66767"]
PRES_RENK = alt.Scale(domain=['6"', '8"'], range=PALET[:2])
TEK_RENK = PALET[0]
ZEMIN = "#121b2d"      # kart / grafik zemini (çubuklar arası boşluk rengi)
SONUK = "#4f5a70"      # "geri kalanı" gibi ikincil kalemler

TEMA_CSS = """
<style>
/* Üst menü şeridi */
[data-testid="stHeader"] { background: #0a101c; border-bottom: 1px solid #1c2740; }
[data-testid="stAppDeployButton"] { display: none; }
.block-container { padding-top: 3.6rem; max-width: 1500px; }

/* Marka şeridi */
.albond-bant { display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin: 0 0 1.1rem 0; padding: 12px 18px;
  background: linear-gradient(90deg, #13213d 0%, #0f1a30 60%, #0b1324 100%);
  border: 1px solid #22304a; border-left: 4px solid #3987e5; border-radius: 10px; }
.albond-bant .marka { font-weight: 800; letter-spacing: .14em; color: #fff; font-size: .95rem; }
.albond-bant .marka span { color: #8fb4f0; font-weight: 600; letter-spacing: .04em;
  margin-left: 10px; font-size: .9rem; }
.albond-bant .canli { color: #9fb0cc; font-size: .8rem; white-space: nowrap; }
.albond-bant .nokta { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: #22c55e; box-shadow: 0 0 0 0 rgba(34,197,94,.6); margin-right: 6px;
  animation: nabiz 2s infinite; vertical-align: middle; }
@keyframes nabiz { 0% { box-shadow: 0 0 0 0 rgba(34,197,94,.55); }
  70% { box-shadow: 0 0 0 8px rgba(34,197,94,0); } 100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); } }

/* Başlıklar */
h1 { font-size: 1.85rem !important; font-weight: 800 !important; letter-spacing: -.01em; }
h3 { font-size: 1.05rem !important; font-weight: 700 !important; color: #cfd9ea !important;
  text-transform: none; }
h4 { color: #e4eaf4 !important; font-weight: 700 !important; }

/* Gösterge kartları */
[data-testid="stMetric"] { background: linear-gradient(180deg, #152038 0%, #111a2c 100%);
  border: 1px solid #22304a; border-left: 4px solid #3987e5; border-radius: 10px;
  padding: 14px 16px 12px 16px; box-shadow: 0 4px 14px rgba(0,0,0,.25); }
[data-testid="stMetricLabel"] p { text-transform: uppercase; letter-spacing: .07em;
  font-size: .72rem !important; font-weight: 600; color: #8b9bb8 !important; }
[data-testid="stMetricValue"] { color: #ffffff; font-size: 2rem !important; line-height: 1.15; }

/* Grafik ve tablo kartları */
[data-testid="stVegaLiteChart"] { background: #121b2d; border: 1px solid #22304a;
  border-radius: 10px; padding: 10px 8px 4px 8px; }
[data-testid="stDataFrame"] { border-radius: 10px; }

/* Sekmeler */
[data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #22304a; }
[data-baseweb="tab"] { font-weight: 600; padding: 8px 14px !important; border-radius: 8px 8px 0 0; }
[data-baseweb="tab"][aria-selected="true"] { background: #16213a; }

/* Açıklama yazıları */
[data-testid="stCaptionContainer"] { color: #8392ad !important; }
</style>
"""


def tema_uygula():
    """Kart/şerit stilleri ve üstte marka şeridi (app.py her çalışmada çağırır)."""
    import time
    st.markdown(TEMA_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="albond-bant"><div class="marka">ALBOND<span>Profil İmalat Üretim '
        'Raporları</span></div><div class="canli"><span class="nokta"></span>CANLI · '
        f'{tarih_saat(time.time())}</div></div>', unsafe_allow_html=True)


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
