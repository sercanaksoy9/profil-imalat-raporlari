"""Profil İmalat Üretim Raporları (ALBOND).

Veri klasörüne giren üretim dosyalarını okur ve pano olarak gösterir.
Klasördeki dosyalar değişince pano kendini yeniler (1 dakikada bir bakar).
"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import veri

st.set_page_config(page_title="Profil İmalat Üretim Raporları", page_icon="📊",
                   layout="wide")

# Pres renkleri: doğrulanmış kategorik paletin ilk iki rengi (sabit sıra)
PRES_RENK = alt.Scale(domain=['6"', '8"'], range=["#2a78d6", "#eb6834"])
TEK_RENK = "#2a78d6"
AY_ADI = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki",
          "Kas", "Ara"]


def sayi(v, ondalik=0):
    """Türkçe sayı biçimi: 1.234.567,8"""
    metin = f"{v:,.{ondalik}f}"
    return metin.replace(",", "X").replace(".", ",").replace("X", ".")


def donem_etiketi(t, zaman):
    """Grafik ekseni için dönem adı: 'Oca 2026' ya da '17.11'."""
    t = pd.Timestamp(t)
    return f"{AY_ADI[t.month - 1]} {t.year}" if zaman == "ay" else f"{t:%d.%m}"


@st.cache_data(show_spinner="Üretim kayıtları okunuyor...")
def kayitlari_oku(yol, degisme_zamani):
    return veri.pres_kayitlari(yol)


@st.cache_data(show_spinner="Üretim kayıtları okunuyor...")
def ozet_oku(yol, degisme_zamani):
    return pd.read_parquet(yol)


@st.fragment(run_every="60s")
def klasor_izle():
    """Veri klasörü değişince sayfayı yeniden çalıştırır."""
    imza = veri.klasor_imzasi()
    onceki = st.session_state.get("klasor_imzasi")
    st.session_state["klasor_imzasi"] = imza
    if onceki is not None and imza != onceki:
        st.rerun(scope="app")


# ---------------------------------------------------------------------
# Başlık ve veri
# ---------------------------------------------------------------------
st.title("📊 Profil İmalat Üretim Raporları")
klasor_izle()

tur, dosya = veri.kaynak()
if dosya is None:
    st.error("Pres üretim verisi bulunamadı (veri klasöründe *DASHBOARD*.xlsx "
             f"ya da bulut özeti yok): {veri.veri_klasoru()}")
    st.stop()

if tur == "excel":
    degisme = dosya.stat().st_mtime
    tum = kayitlari_oku(str(dosya), degisme)
    kaynak_adi = dosya.name
    not_ = "klasör 1 dakikada bir kontrol edilir"
else:  # bulut: senkron.py'nin yazdığı özet
    tum = ozet_oku(str(dosya), dosya.stat().st_mtime)
    bilgi = veri.bulut_bilgisi()
    degisme = bilgi.get("degisme", dosya.stat().st_mtime)
    kaynak_adi = bilgi.get("kaynak", dosya.name)
    not_ = "klasöre giren veri birkaç dakika içinde buraya gelir"
st.caption(f"📁 Kaynak: **{kaynak_adi}** · son değişiklik "
           f"{pd.Timestamp(degisme, unit='s', tz='UTC').tz_convert('Europe/Istanbul'):%d.%m.%Y %H:%M}"
           f" · {sayi(len(tum))} kayıt · {not_}")

# ---------------------------------------------------------------------
# Filtreler (tek sıra, grafiklerin üstünde)
# ---------------------------------------------------------------------
en_eski, en_yeni = tum["gun"].min().date(), tum["gun"].max().date()
hazir = {
    "Bu ay": (en_yeni.replace(day=1), en_yeni),
    "Son 30 gün": (max(en_eski, (pd.Timestamp(en_yeni) - pd.Timedelta(days=29)).date()), en_yeni),
    "Son 3 ay": (max(en_eski, (pd.Timestamp(en_yeni) - pd.DateOffset(months=3)).date()), en_yeni),
    "Bu yıl": (max(en_eski, en_yeni.replace(month=1, day=1)), en_yeni),
    "Tümü": (en_eski, en_yeni),
}
f1, f2, f3, f4 = st.columns([1.2, 2, 1.2, 1.2])
donem = f1.selectbox("Dönem", list(hazir) + ["Özel aralık"], index=3)
if donem == "Özel aralık":
    aralik = f2.date_input("Tarih aralığı", value=hazir["Bu yıl"],
                           min_value=en_eski, max_value=en_yeni, format="DD.MM.YYYY")
    bas, son = (aralik if isinstance(aralik, tuple) and len(aralik) == 2
                else hazir["Bu yıl"])
else:
    bas, son = hazir[donem]
    f2.text_input("Tarih aralığı", f"{bas:%d.%m.%Y} – {son:%d.%m.%Y}", disabled=True)
presler = f3.multiselect("Pres", ['6"', '8"'], default=['6"', '8"'])
vardiyalar = sorted(int(v) for v in tum["vardiya"].dropna().unique())
secili_vardiya = f4.multiselect("Vardiya", vardiyalar, default=vardiyalar)

d = tum[(tum["gun"] >= pd.Timestamp(bas)) & (tum["gun"] <= pd.Timestamp(son))
        & tum["pres"].isin(presler)
        & (tum["vardiya"].isin(secili_vardiya) | tum["vardiya"].isna())]
if d.empty:
    st.warning("Seçilen filtrelerde kayıt yok.")
    st.stop()

# ---------------------------------------------------------------------
# Göstergeler
# ---------------------------------------------------------------------
o = veri.ozet(d)
k = st.columns(6)
k[0].metric("Net Üretim", f"{sayi(o['net_kg'] / 1000, 1)} ton")
k[1].metric("Net kg/saat", sayi(o["kg_saat"], 0))
k[2].metric("Fire", f"%{sayi(o['fire_oran'] * 100, 1)}")
k[3].metric("Çalışma", f"{sayi(o['saat'], 0)} saat")
k[4].metric("Biyet", sayi(o["biyet"]))
k[5].metric("Duruş", f"{sayi(o['durus_saat'], 0)} saat")

sekme = st.tabs(["📈 Özet", "🔩 Kalıplar", "⏸ Duruşlar", "👷 Vardiya & Operatör",
                 "📋 Kayıtlar"])

# ---------------------------------------------------------------------
# Özet: zaman içinde üretim, kg/saat ve fire
# ---------------------------------------------------------------------
with sekme[0]:
    gun_sayisi = (pd.Timestamp(son) - pd.Timestamp(bas)).days
    zaman = "gun" if gun_sayisi <= 45 else "hafta" if gun_sayisi <= 200 else "ay"
    zaman_adi = {"gun": "Gün", "hafta": "Hafta", "ay": "Ay"}[zaman]
    g = veri.grupla(d, [zaman, "pres"]).rename(columns={zaman: "donem"})
    g["net_ton"] = g["net_kg"] / 1000
    g["fire_yuzde"] = g["fire_oran"] * 100
    g["etiket"] = g["donem"].map(lambda t: donem_etiketi(t, zaman))
    sira = [donem_etiketi(t, zaman) for t in sorted(g["donem"].unique())]
    x_ekseni = alt.X("etiket:O", title=None, sort=sira,
                     axis=alt.Axis(labelAngle=0 if len(sira) <= 14 else -45))
    ipucu = [alt.Tooltip("etiket:N", title=zaman_adi),
             alt.Tooltip("pres:N", title="Pres"),
             alt.Tooltip("net_ton:Q", title="Net ton", format=",.1f"),
             alt.Tooltip("kg_saat:Q", title="Net kg/saat", format=",.0f"),
             alt.Tooltip("fire_yuzde:Q", title="Fire %", format=".1f"),
             alt.Tooltip("saat:Q", title="Saat", format=",.0f")]
    renk = alt.Color("pres:N", scale=PRES_RENK, title="Pres",
                     legend=alt.Legend(orient="top"))

    st.subheader(f"Net üretim ({zaman_adi.lower()}lük, ton)")
    st.altair_chart(
        alt.Chart(g).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                              stroke="white", strokeWidth=2)
        .encode(x=x_ekseni,
                y=alt.Y("net_ton:Q", title="Net ton", stack=True),
                color=renk, tooltip=ipucu)
        .properties(height=280), use_container_width=True)

    sol, sag = st.columns(2)
    with sol:
        st.subheader("Net kg/saat")
        st.altair_chart(
            alt.Chart(g).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60))
            .encode(x=x_ekseni,
                    y=alt.Y("kg_saat:Q", title="kg/saat"), color=renk, tooltip=ipucu)
            .properties(height=250), use_container_width=True)
    with sag:
        st.subheader("Fire %")
        st.altair_chart(
            alt.Chart(g).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60))
            .encode(x=x_ekseni,
                    y=alt.Y("fire_yuzde:Q", title="Fire %"), color=renk, tooltip=ipucu)
            .properties(height=250), use_container_width=True)

    pres_tablo = veri.grupla(d, "pres")
    st.dataframe(pd.DataFrame({
        "Pres": pres_tablo["pres"],
        "Net Üretim (ton)": (pres_tablo["net_kg"] / 1000).round(1),
        "Brüt (ton)": (pres_tablo["brut_kg"] / 1000).round(1),
        "Fire %": (pres_tablo["fire_oran"] * 100).round(1),
        "Çalışma Saati": pres_tablo["saat"].round(0),
        "Net kg/saat": pres_tablo["kg_saat"].round(0),
        "Biyet": pres_tablo["biyet"].astype(int),
    }), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------
# Kalıplar
# ---------------------------------------------------------------------
with sekme[1]:
    kg = veri.grupla(d[d["kalip"].notna()], ["kalip", "pres"])
    min_saat = st.slider("En az çalışma saati (kısa denemeleri ayıklar)", 0, 50, 5)
    kg = kg[kg["saat"] >= min_saat]
    ara = st.text_input("Kalıp no ara", placeholder="örn. 1051")
    if ara.strip().isdigit():
        kg = kg[kg["kalip"] == int(ara)]
    st.caption(f"{len(kg)} kalıp/pres satırı · varsayılan sıralama: net üretim")
    st.dataframe(pd.DataFrame({
        "Kalıp": kg["kalip"].astype(str).str.zfill(4).radd("A0"),
        "Pres": kg["pres"],
        "Net Üretim (kg)": kg["net_kg"].round(0),
        "Net kg/saat": kg["kg_saat"].round(0),
        "Fire %": (kg["fire_oran"] * 100).round(1),
        "Saat": kg["saat"].round(1),
        "Biyet": kg["biyet"].astype(int),
        "Kayıt": kg["kayit"],
    }).sort_values("Net Üretim (kg)", ascending=False),
        hide_index=True, use_container_width=True, height=420)

    if len(kg) >= 5:
        sol, sag = st.columns(2)
        en_cok = kg.nlargest(10, "net_kg").assign(
            ad=lambda x: "A0" + x["kalip"].astype(str).str.zfill(4) + " " + x["pres"])
        with sol:
            st.subheader("En çok üretilen 10 kalıp (ton)")
            st.altair_chart(
                alt.Chart(en_cok.assign(ton=en_cok["net_kg"] / 1000))
                .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color=TEK_RENK)
                .encode(y=alt.Y("ad:N", sort="-x", title=None, axis=alt.Axis(labelLimit=200)),
                        x=alt.X("ton:Q", title="Net ton"),
                        tooltip=[alt.Tooltip("ad:N", title="Kalıp"),
                                 alt.Tooltip("ton:Q", title="Net ton", format=",.1f"),
                                 alt.Tooltip("kg_saat:Q", title="kg/saat", format=",.0f")])
                .properties(height=300), use_container_width=True)
        en_fire = kg[kg["brut_kg"] >= 1000].nlargest(10, "fire_oran").assign(
            ad=lambda x: "A0" + x["kalip"].astype(str).str.zfill(4) + " " + x["pres"],
            yuzde=lambda x: x["fire_oran"] * 100)
        with sag:
            st.subheader("En yüksek fireli 10 kalıp (%)")
            st.altair_chart(
                alt.Chart(en_fire)
                .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color="#e34948")
                .encode(y=alt.Y("ad:N", sort="-x", title=None, axis=alt.Axis(labelLimit=200)),
                        x=alt.X("yuzde:Q", title="Fire %"),
                        tooltip=[alt.Tooltip("ad:N", title="Kalıp"),
                                 alt.Tooltip("yuzde:Q", title="Fire %", format=".1f"),
                                 alt.Tooltip("brut_kg:Q", title="Brüt kg", format=",.0f")])
                .properties(height=300), use_container_width=True)
            st.caption("En az 1 ton brüt üretimi olan kalıplar.")

# ---------------------------------------------------------------------
# Duruşlar
# ---------------------------------------------------------------------
with sekme[2]:
    du = d[d["durus_dk"] > 0].copy()
    if du.empty:
        st.info("Seçilen dönemde duruş kaydı yok.")
    else:
        du["durus_tipi"] = du["durus_tipi"].fillna("BELİRTİLMEMİŞ")
        tip = (du.groupby("durus_tipi")["durus_dk"].agg(["sum", "size"]).reset_index()
               .rename(columns={"sum": "dk", "size": "adet"}).sort_values("dk", ascending=False))
        tip["saat"] = tip["dk"] / 60
        tip["pay"] = tip["dk"] / tip["dk"].sum() * 100
        sol, sag = st.columns([3, 2])
        with sol:
            st.subheader("Duruş tipine göre süre (saat)")
            st.altair_chart(
                alt.Chart(tip.head(12))
                .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color=TEK_RENK)
                .encode(y=alt.Y("durus_tipi:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
                        x=alt.X("saat:Q", title="Saat"),
                        tooltip=[alt.Tooltip("durus_tipi:N", title="Tip"),
                                 alt.Tooltip("saat:Q", title="Saat", format=",.1f"),
                                 alt.Tooltip("adet:Q", title="Adet"),
                                 alt.Tooltip("pay:Q", title="Pay %", format=".1f")])
                .properties(height=34 * min(len(tip), 12) + 20), use_container_width=True)
        with sag:
            st.subheader("Tablo")
            st.dataframe(pd.DataFrame({
                "Duruş Tipi": tip["durus_tipi"], "Saat": tip["saat"].round(1),
                "Adet": tip["adet"], "Pay %": tip["pay"].round(1)}),
                hide_index=True, use_container_width=True)
        zaman_du = du.groupby(["ay", "pres"])["durus_dk"].sum().reset_index()
        zaman_du["saat"] = zaman_du["durus_dk"] / 60
        zaman_du["etiket"] = zaman_du["ay"].map(lambda t: donem_etiketi(t, "ay"))
        st.subheader("Aylık duruş (saat)")
        st.altair_chart(
            alt.Chart(zaman_du)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke="white", strokeWidth=2)
            .encode(x=alt.X("etiket:O", title=None, sort=[donem_etiketi(t, "ay") for t in sorted(zaman_du["ay"].unique())], axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("saat:Q", title="Saat"),
                    color=alt.Color("pres:N", scale=PRES_RENK, title="Pres",
                                    legend=alt.Legend(orient="top")),
                    tooltip=[alt.Tooltip("etiket:N", title="Ay"),
                             alt.Tooltip("pres:N", title="Pres"),
                             alt.Tooltip("saat:Q", title="Saat", format=",.1f")])
            .properties(height=250), use_container_width=True)

# ---------------------------------------------------------------------
# Vardiya ve operatör
# ---------------------------------------------------------------------
with sekme[3]:
    sol, sag = st.columns(2)
    v = veri.grupla(d[d["vardiya"].notna()], "vardiya")
    with sol:
        st.subheader("Vardiyalar")
        st.dataframe(pd.DataFrame({
            "Vardiya": v["vardiya"].astype(int),
            "Net Üretim (ton)": (v["net_kg"] / 1000).round(1),
            "Net kg/saat": v["kg_saat"].round(0),
            "Fire %": (v["fire_oran"] * 100).round(1),
            "Saat": v["saat"].round(0)}), hide_index=True, use_container_width=True)
    op = veri.grupla(d[d["operator"].notna()], "operator")
    op = op[op["saat"] >= 10].sort_values("kg_saat", ascending=False)
    with sag:
        st.subheader("Operatörler (en az 10 saat)")
        st.dataframe(pd.DataFrame({
            "Operatör": op["operator"],
            "Net Üretim (ton)": (op["net_kg"] / 1000).round(1),
            "Net kg/saat": op["kg_saat"].round(0),
            "Fire %": (op["fire_oran"] * 100).round(1),
            "Saat": op["saat"].round(0)}), hide_index=True, use_container_width=True,
            height=360)

# ---------------------------------------------------------------------
# Kayıtlar
# ---------------------------------------------------------------------
with sekme[4]:
    goster = d.sort_values("tarih", ascending=False)[[
        "tarih", "vardiya", "pres", "operator", "kalip", "musteri", "piston",
        "biyet_boyu", "biyet_adet", "brut_kg", "net_kg", "fire_kg", "sure_dk",
        "durus_tipi", "durus_dk"]].rename(columns={
            "tarih": "Tarih", "vardiya": "Vardiya", "pres": "Pres",
            "operator": "Operatör", "kalip": "Kalıp", "musteri": "Müşteri",
            "piston": "Piston mm/s", "biyet_boyu": "Biyet mm", "biyet_adet": "Biyet",
            "brut_kg": "Brüt kg", "net_kg": "Net kg", "fire_kg": "Fire kg",
            "sure_dk": "Süre dk", "durus_tipi": "Duruş Tipi", "durus_dk": "Duruş dk"})
    st.dataframe(goster, hide_index=True, use_container_width=True, height=520,
                 column_config={"Tarih": st.column_config.DateColumn(format="DD.MM.YYYY")})
    st.download_button("⬇️ CSV indir", goster.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"pres_kayitlari_{bas}_{son}.csv", mime="text/csv")
