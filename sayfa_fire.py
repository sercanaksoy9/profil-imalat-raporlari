"""Toplam Fire 2026 raporu (tarih aralıklı).

'Toplam Fire Listesi 2026' dosyasının ay sayfalarındaki günlük satırlardan
gelir. Oranlar Excel'deki gibi net kullanılan hammaddeye göredir:
  Pres firesi        = (net kullanılan − sepete giren) ÷ net kullanılan
  Pres sonrası fire  = (pres sonrası hurda + iade + stok hurda) ÷ net kullanılan
  Toplam fire        = pres firesi + pres sonrası fire
  Fabrika fire       = dışarı giden araiş ÷ net kullanılan
Net kullanılan hammadde günlük olarak sayım farkından hesaplandığı için gün
bazındaki oranlar dalgalı olabilir; hafta/ay kırılımı daha sağlıklıdır.
"""
import datetime as dt

import altair as alt
import pandas as pd
import streamlit as st

from ortak import PALET, TEK_RENK, ay_etiketi, donem_sec, kaynak_notu, rapor_verisi, sayi
from raporlar import FIRE_BASLANGIC, fire_ozet

ORAN_ADI = {"pres_fire": "Pres firesi", "ps_fire": "Pres sonrası fire",
            "toplam_fire": "Toplam fire", "fabrika_fire": "Fabrika fire (araiş)"}
ORAN_RENK = alt.Scale(domain=list(ORAN_ADI.values()), range=PALET[:4])
HURDA_ADI = {"pres_hurda": "Pres hurdası (net − testere)",
             "ps_tartim": "Pres sonrası hurda (tartım)", "iade": "İade hurda",
             "stok": "Stok hurda", "numune": "Numune hurda", "talas": "Talaş",
             "hassas": "Hassas kesim"}

st.title("♻️ Toplam Fire 2026")

veri_ = rapor_verisi("fire")
if veri_ is None or veri_[0].empty:
    st.error("Veri klasöründe 'Toplam Fire Listesi 2026' dosyası bulunamadı.")
    st.stop()
gunluk, kaynak_adi, degisme, mod = veri_
kaynak_notu(kaynak_adi, degisme, mod)
# Eski rapora ait aylar (Haziran 2026 öncesi) gösterilmez; bulut özeti
# eskiyse de burada ayıklanır
gunluk = gunluk[gunluk["tarih"] >= FIRE_BASLANGIC].reset_index(drop=True)
st.caption(f"Rapor {FIRE_BASLANGIC:%d.%m.%Y} tarihinden itibaren tutulan verileri kapsar.")

kayitli = gunluk[gunluk["kayitli"]]
ilk_gun = gunluk["tarih"].min().date()
son_gun = (kayitli["tarih"].max() if not kayitli.empty else gunluk["tarih"].max()).date()

bas, bit = donem_sec(ilk_gun, son_gun)


def sec(b, e):
    return gunluk[(gunluk["tarih"].dt.date >= b) & (gunluk["tarih"].dt.date <= e)].copy()


o = sec(bas, bit)
if not o["kayitli"].any():
    st.warning("Seçilen tarih aralığında kayıt yok.")
    st.stop()

gun_sayisi = (bit - bas).days + 1
onceki = sec(bas - dt.timedelta(days=30), bas - dt.timedelta(days=1))
g = fire_ozet(o)
p = fire_ozet(onceki) if onceki["kayitli"].any() else None


ORAN_ANAHTAR = {"toplam_fire", "pres_fire", "ps_fire", "fabrika_fire"}
KIYAS_GUN = 30


def fark(anahtar, carpan=1.0, ondalik=0, birim=""):
    """Önceki 30 günle fark. Oranlar doğrudan; miktarlar 30 günün günlük
    ortalaması seçili gün sayısına ölçeklenerek kıyaslanır."""
    if p is None or p[anahtar] is None or g[anahtar] is None:
        return None
    taban = p[anahtar] if anahtar in ORAN_ANAHTAR else p[anahtar] * gun_sayisi / KIYAS_GUN
    return f"{sayi((g[anahtar] - taban) * carpan, ondalik)}{birim}"


def yuzde(v):
    return sayi(v * 100, 1) if v is not None else "–"


st.markdown(f"#### {bas:%d.%m.%Y} – {bit:%d.%m.%Y}  ·  {gun_sayisi} gün  ·  "
            f"{sayi(g['gun'])} kayıtlı gün")
if p is not None:
    st.caption(f"Oklar seçili dönemden önceki 30 günle "
               f"({bas - dt.timedelta(days=KIYAS_GUN):%d.%m} – {bas - dt.timedelta(days=1):%d.%m}) kıyastır. "
               "Oranlar doğrudan, miktarlar 30 günün günlük ortalamasıyla "
               f"({gun_sayisi} güne ölçeklenerek) karşılaştırılır.")

k = st.columns(4)
k[0].metric("Toplam Fire (%)", yuzde(g["toplam_fire"]), fark("toplam_fire", 100, 1, " puan"),
            delta_color="inverse", help="Pres firesi + pres sonrası fire")
k[1].metric("Pres Firesi (%)", yuzde(g["pres_fire"]), fark("pres_fire", 100, 1, " puan"),
            delta_color="inverse", help="(Net kullanılan − sepete giren) ÷ net kullanılan")
k[2].metric("Pres Sonrası Fire (%)", yuzde(g["ps_fire"]), fark("ps_fire", 100, 1, " puan"),
            delta_color="inverse", help="(Pres sonrası hurda + iade + stok hurda) ÷ net kullanılan")
k[3].metric("Fabrika Fire – Araiş (%)", yuzde(g["fabrika_fire"]),
            fark("fabrika_fire", 100, 1, " puan"), delta_color="inverse",
            help="Dışarı giden araiş ÷ net kullanılan")
k = st.columns(4)
k[0].metric("Net Kullanılan Hammadde (ton)", sayi(g["net"] / 1000, 1), fark("net", 1 / 1000, 1),
            help=f"Teorik kullanılan {sayi(g['teorik'] / 1000, 1)} ton")
k[1].metric("Sepete Giren – Testere (ton)", sayi(g["sepete"] / 1000, 1), fark("sepete", 1 / 1000, 1))
k[2].metric("Dışarı Giden Araiş (ton)", sayi(g["arais"] / 1000, 1), fark("arais", 1 / 1000, 1),
            delta_color="inverse")
k[3].metric("Gelen Hammadde (ton)", sayi(g["gelen"] / 1000, 1), fark("gelen", 1 / 1000, 1))

sekme = st.tabs(["📈 Trend", "🧩 Fire Dağılımı", "⚖️ Araiş & Kantar", "📊 Aylık Özet",
                 "📋 Detay Tablo"])

# ---------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------
with sekme[0]:
    varsayilan = "Gün" if gun_sayisi <= 31 else ("Hafta" if gun_sayisi <= 120 else "Ay")
    kirilim = st.radio("Kırılım", ["Gün", "Hafta", "Ay"], horizontal=True,
                       index=["Gün", "Hafta", "Ay"].index(varsayilan))
    if kirilim == "Gün":
        st.caption("Net kullanılan hammadde günlük sayım farkından hesaplandığı için gün "
                   "bazında oranlar dalgalı olabilir.")
    t = o[o["kayitli"]].copy()
    if kirilim == "Gün":
        t["donem"] = t["tarih"]
        t["etiket"] = t["donem"].dt.strftime("%d.%m")
    elif kirilim == "Hafta":
        t["donem"] = t["tarih"] - pd.to_timedelta(t["tarih"].dt.weekday, unit="D")
        t["etiket"] = t["donem"].dt.strftime("%d.%m") + " haftası"
    else:
        t["donem"] = t["tarih"].dt.to_period("M").dt.to_timestamp()
        t["etiket"] = t["donem"].map(ay_etiketi)
    d = t.groupby(["donem", "etiket"]).apply(fire_ozet, include_groups=False).reset_index()
    sira = list(d.sort_values("donem")["etiket"])
    x = alt.X("etiket:O", title=None, sort=sira,
              axis=alt.Axis(labelAngle=0 if len(sira) <= 14 else -45))

    oranlar = d.melt(id_vars=["donem", "etiket"], value_vars=list(ORAN_ADI),
                     var_name="oran", value_name="deger").dropna(subset=["deger"])
    oranlar["deger"] = oranlar["deger"].astype(float) * 100
    oranlar["ad"] = oranlar["oran"].map(ORAN_ADI)
    st.subheader(f"Fire oranları (%) · {kirilim.lower()} bazında")
    st.altair_chart(
        alt.Chart(oranlar).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60))
        .encode(x=x, y=alt.Y("deger:Q", title="%"),
                color=alt.Color("ad:N", scale=ORAN_RENK, title=None, legend=alt.Legend(orient="top")),
                tooltip=[alt.Tooltip("etiket:N", title="Dönem"), alt.Tooltip("ad:N", title="Oran"),
                         alt.Tooltip("deger:Q", title="%", format=".1f")])
        .properties(height=300), width="stretch")

    miktar = d.melt(id_vars=["donem", "etiket"], value_vars=["net", "sepete"],
                    var_name="tur", value_name="kg")
    miktar["ad"] = miktar["tur"].map({"net": "Net kullanılan hammadde", "sepete": "Sepete giren"})
    miktar["ton"] = miktar["kg"] / 1000
    st.subheader("Net kullanılan hammadde ve sepete giren (ton)")
    st.altair_chart(
        alt.Chart(miktar).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(x=x, xOffset=alt.XOffset("ad:N", sort=["Net kullanılan hammadde", "Sepete giren"]),
                y=alt.Y("ton:Q", title="Ton"),
                color=alt.Color("ad:N", title=None, legend=alt.Legend(orient="top"),
                                scale=alt.Scale(domain=["Net kullanılan hammadde", "Sepete giren"],
                                                range=[PALET[0], PALET[2]])),
                tooltip=[alt.Tooltip("etiket:N", title="Dönem"), alt.Tooltip("ad:N", title="Kalem"),
                         alt.Tooltip("ton:Q", title="Ton", format=",.1f")])
        .properties(height=280), width="stretch")

# ---------------------------------------------------------------------
# Fire dağılımı (Excel'deki alt bloktaki gibi)
# ---------------------------------------------------------------------
with sekme[1]:
    dag = pd.DataFrame({"kalem": list(HURDA_ADI.values()),
                        "kg": [g[c] for c in HURDA_ADI]})
    dag["oran"] = dag["kg"] / g["net"] * 100 if g["net"] else None
    dag["pay"] = dag["kg"] / dag["kg"].sum() * 100 if dag["kg"].sum() else None
    sol, sag = st.columns([3, 2])
    with sol:
        st.subheader("Hurda kalemleri (kg)")
        goster = dag[dag["kg"] != 0]
        st.altair_chart(
            alt.Chart(goster).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                                       color=TEK_RENK)
            .encode(y=alt.Y("kalem:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240)),
                    x=alt.X("kg:Q", title="kg"),
                    tooltip=[alt.Tooltip("kalem:N", title="Kalem"),
                             alt.Tooltip("kg:Q", title="kg", format=",.0f"),
                             alt.Tooltip("oran:Q", title="Net hammaddeye oranı %", format=".2f"),
                             alt.Tooltip("pay:Q", title="Hurda içindeki pay %", format=".1f")])
            .properties(height=42 * max(len(goster), 1) + 30), width="stretch")
    with sag:
        st.subheader("Oranlar")
        st.dataframe(pd.DataFrame({
            "Kalem": dag["kalem"], "kg": dag["kg"].map(sayi),
            "Net hammaddeye %": dag["oran"].map(lambda v: sayi(v, 2)),
            "Hurda içinde pay %": dag["pay"].map(lambda v: sayi(v, 1)),
        }), hide_index=True, width="stretch")
        st.metric("Toplam kantar hurdası (ton)", sayi(g["toplam_hurda"] / 1000, 1),
                  help="Pres hurdası + pres sonrası + iade + stok + numune + talaş + hassas kesim")
    st.caption("Excel'de 'İşlem firesi (hassas kesim + talaş)' satırı yalnız talaşı alıyor; "
               "burada talaş ve hassas kesim ayrı ayrı gösterilir.")

# ---------------------------------------------------------------------
# Araiş ve kantar
# ---------------------------------------------------------------------
with sekme[2]:
    a = st.columns(4)
    a[0].metric("Dışarı giden araiş (ton)", sayi(g["arais"] / 1000, 1))
    a[1].metric("Araiş tartım – kantar (ton)", sayi(g["arais_kantar"] / 1000, 1)
                if g["arais_kantar"] else "–", help="Temmuz 2026'dan itibaren tutuluyor")
    a[2].metric("Toplam kantar hurdası (ton)", sayi(g["toplam_hurda"] / 1000, 1))
    a[3].metric("Fark: hurda − giden araiş (ton)", sayi(g["fark"] / 1000, 1),
                help="Excel'deki 'GİDEN ARAİŞ/HURDA – FARK' satırı: içeride kalan hurda")
    ay_ = o[o["kayitli"]].copy()
    ay_["ay"] = ay_["tarih"].dt.to_period("M").dt.to_timestamp()
    m = ay_.groupby("ay").apply(fire_ozet, include_groups=False).reset_index()
    m["etiket"] = m["ay"].map(ay_etiketi)
    karsi = m.melt(id_vars=["ay", "etiket"], value_vars=["arais", "arais_kantar", "toplam_hurda"],
                   var_name="tur", value_name="kg")
    adlar = {"arais": "Dışarı giden araiş", "arais_kantar": "Araiş tartım (kantar)",
             "toplam_hurda": "Toplam kantar hurdası"}
    karsi["ad"] = karsi["tur"].map(adlar)
    karsi["ton"] = karsi["kg"] / 1000
    karsi = karsi[karsi["kg"] > 0]
    sira = list(m.sort_values("ay")["etiket"])
    st.subheader("Aylık araiş ve hurda (ton)")
    st.altair_chart(
        alt.Chart(karsi).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(x=alt.X("etiket:O", title=None, sort=sira, axis=alt.Axis(labelAngle=0)),
                xOffset=alt.XOffset("ad:N", sort=list(adlar.values())),
                y=alt.Y("ton:Q", title="Ton"),
                color=alt.Color("ad:N", title=None, legend=alt.Legend(orient="top"),
                                scale=alt.Scale(domain=list(adlar.values()), range=PALET[1:4])),
                tooltip=[alt.Tooltip("etiket:N", title="Ay"), alt.Tooltip("ad:N", title="Kalem"),
                         alt.Tooltip("ton:Q", title="Ton", format=",.1f")])
        .properties(height=300), width="stretch")
    st.caption("Kantar sütunları (araiş tartım, kantara göre net kullanılan hammadde) "
               "Temmuz 2026'dan itibaren dosyada var.")

# ---------------------------------------------------------------------
# Aylık özet (DASBORD sayfası gibi)
# ---------------------------------------------------------------------
with sekme[3]:
    satir = m.sort_values("ay")
    toplam = fire_ozet(o)
    tablo = pd.DataFrame({
        "Ay": list(satir["etiket"]) + ["TOPLAM"],
        "Teorik Kullanılan (kg)": list(satir["teorik"]) + [toplam["teorik"]],
        "Net Kullanılan (kg)": list(satir["net"]) + [toplam["net"]],
        "Sepete Giren (kg)": list(satir["sepete"]) + [toplam["sepete"]],
        "Dışarı Giden Araiş (kg)": list(satir["arais"]) + [toplam["arais"]],
        "Gelen Hammadde (kg)": list(satir["gelen"]) + [toplam["gelen"]],
        "Araiş Tartım (kg)": list(satir["arais_kantar"]) + [toplam["arais_kantar"]],
        "Pres Firesi %": [round(v * 100, 1) if v is not None else None
                          for v in list(satir["pres_fire"]) + [toplam["pres_fire"]]],
        "Pres Sonrası %": [round(v * 100, 1) if v is not None else None
                           for v in list(satir["ps_fire"]) + [toplam["ps_fire"]]],
        "Toplam Fire %": [round(v * 100, 1) if v is not None else None
                          for v in list(satir["toplam_fire"]) + [toplam["toplam_fire"]]],
        "Fabrika Fire %": [round(v * 100, 1) if v is not None else None
                           for v in list(satir["fabrika_fire"]) + [toplam["fabrika_fire"]]],
    })
    st.dataframe(tablo, hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="localized")
                                for c in tablo.columns if c != "Ay"})
    st.caption("Ay kısmen seçiliyse o ayın yalnız seçili günleri toplanır. TOPLAM satırındaki "
               "oranlar dönemin toplamlarından hesaplanır.")

# ---------------------------------------------------------------------
# Detay tablo
# ---------------------------------------------------------------------
with sekme[4]:
    dt_ = o[o["kayitli"]].sort_values("tarih")
    net = dt_["net"].where(dt_["net"] > 0)
    cikti = pd.DataFrame({
        "Tarih": dt_["tarih"].dt.strftime("%d.%m.%Y"),
        "Teorik Kullanılan (kg)": dt_["teorik"], "Net Kullanılan (kg)": dt_["net"],
        "Sepete Giren (kg)": dt_["sepete"], "Pres Hurdası (kg)": dt_["net"] - dt_["sepete"],
        "Pres Firesi %": ((dt_["net"] - dt_["sepete"]) / net * 100).round(1),
        "Dışarı Giden Araiş (kg)": dt_["arais"],
        "Pres Sonrası Hurda (kg)": dt_["ps_tartim"], "İade (kg)": dt_["iade"],
        "Stok (kg)": dt_["stok"], "Numune (kg)": dt_["numune"], "Talaş (kg)": dt_["talas"],
        "Hassas Kesim (kg)": dt_["hassas"], "Gelen Hammadde (kg)": dt_["gelen"],
        "Hammadde Sayım (kg)": dt_["sayim"], "Araiş Tartım (kg)": dt_["arais_kantar"],
    })
    bos = [c for c in cikti.columns[1:] if pd.to_numeric(cikti[c], errors="coerce").fillna(0).eq(0).all()]
    cikti = cikti.drop(columns=bos)
    st.dataframe(cikti, hide_index=True, width="stretch")
    if bos:
        st.caption("Seçilen aralıkta hiç değeri olmayan sütunlar gizlendi: " + ", ".join(bos))
    st.download_button("⬇️ CSV indir", cikti.to_csv(index=False, sep=";", decimal=",")
                       .encode("utf-8-sig"),
                       file_name=f"toplam_fire_{bas:%Y%m%d}_{bit:%Y%m%d}.csv", mime="text/csv")
