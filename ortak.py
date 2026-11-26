"""Sayfaların ortak yardımcıları: biçimlendirme, renkler, veri yükleme."""
import altair as alt
import pandas as pd
import streamlit as st

import raporlar
import veri

AY_ADI = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki",
          "Kas", "Ara"]
# Doğrulanmış kategorik paletin açık zemin tonları, sabit sıra
# (renk varlığı izler, sırayı değil)
PALET = ["#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#008a17",
         "#6a4ce2", "#ec4647"]
PRES_RENK = alt.Scale(domain=['6"', '8"'], range=PALET[:2])
TEK_RENK = PALET[0]
ZEMIN = "#f4f5f2"      # sayfa / grafik zemini (çubuklar arası boşluk rengi)
SONUK = "#a3abb8"      # "geri kalanı" gibi ikincil kalemler
YAZI = "#3d4654"       # grafik üstü değer etiketleri

TEMA_CSS = """
<style>
/* Üst menü şeridi */
[data-testid="stHeader"] { background: #f4f5f2; border-bottom: 1px solid #e1e4e8; }
[data-testid="stAppDeployButton"] { display: none; }
.block-container { padding-top: 3.6rem; max-width: 1500px; }
[data-testid="stSidebar"] { background: #eceee9; border-right: 1px solid #e1e4e8; }
/* Sol sayfa menüsü (masaüstü) */
[data-testid="stSidebarNav"] a { border-radius: 8px; padding: 6px 10px; margin: 1px 0; }
[data-testid="stSidebarNav"] a span { color: #3d4654; font-weight: 500;
  white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: #e3ecf8; }
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: #1f4f8f; font-weight: 700; }

/* Marka şeridi: düz, sade */
.albond-bant { display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin: 0 0 1.1rem 0; padding: 10px 16px;
  background: #fcfcfb; border: 1px solid #e1e4e8; border-left: 3px solid #2f6fbf;
  border-radius: 10px; }
.albond-bant .marka { font-weight: 800; letter-spacing: .14em; color: #2b3340; font-size: .95rem; }
.albond-bant .marka span { color: #5b6b82; font-weight: 600; letter-spacing: .04em;
  margin-left: 10px; font-size: .9rem; }
.albond-bant .canli { color: #6b7585; font-size: .8rem; white-space: nowrap; }
.albond-bant .nokta { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: #2e9e5b; margin-right: 6px; vertical-align: middle; }

/* Başlıklar */
h1 { font-size: 1.85rem !important; font-weight: 800 !important; letter-spacing: -.01em;
  color: #232b37 !important; }
h3 { font-size: 1.05rem !important; font-weight: 700 !important; color: #3d4654 !important;
  text-transform: none; }
h4 { color: #2b3340 !important; font-weight: 700 !important; }

/* Gösterge kartları: düz zemin, ince çerçeve, gölgesiz */
[data-testid="stMetric"] { background: #fcfcfb;
  border: 1px solid #e1e4e8; border-left: 3px solid #2f6fbf; border-radius: 10px;
  padding: 14px 16px 12px 16px; }
[data-testid="stMetricLabel"] p { text-transform: uppercase; letter-spacing: .07em;
  font-size: .72rem !important; font-weight: 600; color: #6b7585 !important; }
[data-testid="stMetricValue"] { color: #232b37; font-size: 2rem !important; line-height: 1.15; }
/* Uzun kart başlıkları "..." ile kesilmesin, alt satıra geçsin */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
  white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }
/* Orta genişlikte (4 kart yan yana sığmayınca) rakamlar kesilmesin */
@media (max-width: 1150px) {
  [data-testid="stMetric"] { padding: 10px 10px 8px 12px; }
  [data-testid="stMetricValue"] { font-size: 1.45rem !important; }
  [data-testid="stMetricLabel"] p { font-size: .62rem !important; letter-spacing: .04em; }
  [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }
}

/* Grafik ve tablo kartları */
[data-testid="stVegaLiteChart"] { background: transparent; border: 1px solid #e1e4e8;
  border-radius: 10px; padding: 10px 8px 4px 8px; }
[data-testid="stDataFrame"] { border-radius: 10px; }

/* Sekmeler */
[data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #e1e4e8; }
[data-baseweb="tab"] { font-weight: 600; padding: 8px 14px !important; border-radius: 8px 8px 0 0; }
[data-baseweb="tab"][aria-selected="true"] { background: #e8eef7; }

/* Açıklama yazıları */
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #5f6978 !important; }
/* Telefon menüsü (yalnız dar ekranda görünür) */
.st-key-mobil_menu { display: none !important; }

/* ===== TELEFON (≤ 640 px): sade, tek sütun, büyük KPI ===== */
@media (max-width: 640px) {
  .block-container { padding: 3.3rem .7rem 2.5rem .7rem !important; }
  .albond-bant { padding: 8px 12px; margin-bottom: .5rem; border-radius: 8px; }
  .albond-bant .marka { font-size: .85rem; }
  .albond-bant .marka span { display: none; }
  .albond-bant .canli { font-size: .72rem; }
  h1 { font-size: 1.3rem !important; padding: .2rem 0 !important; }
  h3 { font-size: .95rem !important; }
  h4 { font-size: .95rem !important; padding: .3rem 0 !important; }

  /* Sayfa menüsü: kaydırılabilir hap düğmeler */
  .st-key-mobil_menu { display: flex !important; flex-wrap: nowrap !important;
    overflow-x: auto; gap: 6px !important; padding-bottom: 4px; scrollbar-width: none; }
  .st-key-mobil_menu::-webkit-scrollbar { display: none; }
  .st-key-mobil_menu > div { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
  .st-key-mobil_menu a { background: #fcfcfb; border: 1px solid #d9dde3; border-radius: 999px;
    padding: 6px 13px !important; min-height: 38px; white-space: nowrap; }
  .st-key-mobil_menu a[aria-current="page"], .st-key-mobil_menu a:has(span[data-testid="stPageLink-active"]) {
    background: #e3ecf8; border-color: #2f6fbf; }

  /* KPI kartları: 2'li ızgara */
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"]
    > [data-testid="stElementContainer"] > [data-testid="stMetric"]) { gap: .5rem !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has(> [data-testid="stVerticalBlock"]
    > [data-testid="stElementContainer"] > [data-testid="stMetric"]) {
    min-width: calc(50% - .25rem) !important; flex: 1 1 calc(50% - .25rem) !important; }
  [data-testid="stMetric"] { padding: 9px 10px 8px 11px; border-left-width: 3px; }
  [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
  [data-testid="stMetricLabel"] p { font-size: .6rem !important; letter-spacing: .03em; }
  [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }
  [data-testid="stMetricDelta"] { font-size: .75rem; }

  /* Seçimler: salt-okunur tarih kutusu başlıkta zaten yazıyor */
  [data-testid="stColumn"]:has(input[type="text"]:disabled):not(:has([data-baseweb="select"])) {
    display: none; }

  /* Sekmeler: parmakla dokunmaya uygun */
  [data-baseweb="tab"] { padding: 10px 12px !important; min-height: 44px; }

  /* Uyarı ve açıklamalar küçük */
  [data-testid="stAlert"] p, [data-testid="stAlert"] div { font-size: .8rem !important; }
  [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { font-size: .72rem !important; }

  /* Grafikler kenara kadar */
  [data-testid="stVegaLiteChart"] { padding: 6px 2px 2px 2px; }

  /* Kalabalık ayrıntı tabloları telefonda gizli (CSV düğmesi kalır) */
  [class*="st-key-masaustu_"] > * { display: none !important; }
  [class*="st-key-masaustu_"]::before { display: block; padding: 10px 12px; color: #6b7585;
    font-size: .8rem; border: 1px dashed #cfd4db; border-radius: 10px;
    content: "📋 Ayrıntılı tablo telefonda gizli. Masaüstünde açın ya da CSV indirin."; }
}
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


def masaustu_tablo(ad):
    """Telefonda gizlenen geniş tablo kabı: `with masaustu_tablo("x"): st.dataframe(...)`"""
    return st.container(key=f"masaustu_{ad}")


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
        try:
            return _excelden(anahtar, str(yol), degisme), yol.name, degisme, "excel"
        except PermissionError:
            # Excel'de açık olan dosya kilitli olabilir: son senkron özeti kullanılır
            st.caption(f"⚠️ {yol.name} şu an başka bir programda açık; son senkron "
                       "özeti gösteriliyor.")
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
        "Yılbaşından beri": (max(ilk_gun, bugun.replace(month=1, day=1)), bugun),
        "Özel aralık": None,
    }
    if ilk_gun < bugun.replace(month=1, day=1):  # birden çok yıllık veri
        hazir = {**dict(list(hazir.items())[:-1]), "Tüm kayıtlar": (ilk_gun, bugun),
                 "Özel aralık": None}
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
