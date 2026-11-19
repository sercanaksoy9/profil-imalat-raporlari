"""Enerji Sarfiyatlar 2026 raporu.

'ENERJİ SARFİYATLAR 2026' dosyasının 6" PRES, 8" PRES, Termikler, Boyahane
ve TOPLAM sayfalarındaki aylık bloklardan gelir. Göstergeler Excel'deki
formüllerle hesaplanır (raporlar.enerji_ozet); birden çok ay seçildiğinde
oranlar ayların toplamından bulunur, $ çevrimi her ayın kendi kuruyla yapılır.
"""
import altair as alt
import pandas as pd
import streamlit as st

from ortak import PALET, ay_etiketi, kaynak_notu, rapor_verisi, sayi
from raporlar import enerji_ozet

st.title("⚡ Enerji Sarfiyatlar 2026")

veri_ = rapor_verisi("enerji")
if veri_ is None or veri_[0].empty:
    st.error("Veri klasöründe 'ENERJİ SARFİYATLAR' dosyası bulunamadı.")
    st.stop()
aylik, kaynak_adi, degisme, mod = veri_
kaynak_notu(kaynak_adi, degisme, mod)

aylar = list(aylik["tarih"])
if len(aylar) > 1:
    bas, bit = st.select_slider("Ay aralığı", options=aylar, value=(aylar[0], aylar[-1]),
                                format_func=ay_etiketi)
else:
    bas = bit = aylar[0]
t = aylik[aylik["tarih"].between(bas, bit)].reset_index(drop=True)
g = enerji_ozet(t)

# Önceki eşit uzunluktaki dönem (ör. tek ay seçiliyse bir önceki ay)
n = len(t)
i0 = aylar.index(bas)
onceki = aylik.iloc[i0 - n:i0] if i0 - n >= 0 else None
p = enerji_ozet(onceki) if onceki is not None and len(onceki) == n else None


def fark(anahtar, carpan=1.0, ondalik=0):
    if p is None or p.get(anahtar) is None or g.get(anahtar) is None:
        return None
    return sayi((g[anahtar] - p[anahtar]) * carpan, ondalik)


baslik = ay_etiketi(bas) if bas == bit else f"{ay_etiketi(bas)} – {ay_etiketi(bit)}"
st.markdown(f"#### {baslik}  ·  {n} ay")
if p is not None:
    st.caption(f"Oklar bir önceki {n} ayla ({ay_etiketi(onceki['tarih'].iloc[0])}"
               + (f" – {ay_etiketi(onceki['tarih'].iloc[-1])}" if n > 1 else "") + ") kıyastır.")

st.markdown("**Presler**")
k = st.columns(4)
k[0].metric("Pres Enerji ($/ton)", sayi(g["pres_enerji_usd_ton"], 1),
            fark("pres_enerji_usd_ton", 1, 1), delta_color="inverse",
            help="Pres hattı elektrik + presler ve termik doğalgaz maliyeti ÷ pres üretimi")
k[1].metric("Hat Elektrik (kWh/ton)", sayi(g["hat_kwh_ton"]), fark("hat_kwh_ton"),
            delta_color="inverse",
            help="Prese ait toplam tüketim (ana pano − kompresör ana hat + kompresör) ÷ üretim")
k[2].metric("Pres Sayaç (kWh/ton)", sayi(g["pres_kwh_ton"]), fark("pres_kwh_ton"),
            delta_color="inverse", help="6\" + 8\" pres sayaçları ÷ pres üretimi")
k[3].metric("Pres+Termik Gaz (m³/ton)", sayi(g["pres_gaz_ton"], 1), fark("pres_gaz_ton", 1, 1),
            delta_color="inverse")
st.markdown("**Fabrika ve Boyahane**")
k = st.columns(4)
k[0].metric("Fabrika Elektrik (MWh)", sayi((g["fab_kwh"] or 0) / 1000, 1),
            fark("fab_kwh", 1 / 1000, 1), delta_color="inverse",
            help=f"Fatura (KDV hariç) {sayi(g['fab_elk_tl'])} TL")
k[1].metric("Fabrika Gaz (bin m³)", sayi((g["fab_gaz_m3"] or 0) / 1000, 1),
            fark("fab_gaz_m3", 1 / 1000, 1), delta_color="inverse",
            help=f"Ödenen {sayi(g['fab_gaz_tl'])} TL")
k[2].metric("Elektrik Fiyatı (TL/kWh)", sayi(g["elk_birim"], 2), fark("elk_birim", 1, 2),
            delta_color="inverse", help=f"Doğalgaz {sayi(g['gaz_birim'], 2)} TL/m³")
k[3].metric("Boyahane Enerji ($/ton)", sayi(g["boya_enerji_usd_ton"], 1),
            fark("boya_enerji_usd_ton", 1, 1), delta_color="inverse",
            help="Boyahane elektrik + doğalgaz maliyeti ÷ boyahane üretimi")

sekme = st.tabs(["🏭 Presler", "💡 Elektrik", "🔥 Doğalgaz", "💵 Maliyet ($/ton)", "📋 Tablo"])

# Ay ay göstergeler
ay_ay = pd.DataFrame([{**enerji_ozet(t.iloc[[i]]), "tarih": t["tarih"].iloc[i]} for i in range(n)])
ay_ay["etiket"] = ay_ay["tarih"].map(ay_etiketi)
sira = list(ay_ay["etiket"])
x = alt.X("etiket:O", title=None, sort=sira, axis=alt.Axis(labelAngle=0))
EKSEN = alt.Axis(labelExpr="replace(datum.label, ',', '.')")


def uzun(kolonlar, adlar):
    u = ay_ay.melt(id_vars=["tarih", "etiket"], value_vars=kolonlar, var_name="k", value_name="deger")
    u["ad"] = u["k"].map(dict(zip(kolonlar, adlar)))
    return u.dropna(subset=["deger"])


def cizgi(u, baslik_y, renkler, adlar, bicim=",.1f"):
    return (alt.Chart(u).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60))
            .encode(x=x, y=alt.Y("deger:Q", title=baslik_y, axis=EKSEN),
                    color=alt.Color("ad:N", title=None, legend=alt.Legend(orient="top"),
                                    scale=alt.Scale(domain=adlar, range=renkler)),
                    tooltip=[alt.Tooltip("etiket:N", title="Ay"), alt.Tooltip("ad:N", title="Kalem"),
                             alt.Tooltip("deger:Q", title=baslik_y, format=bicim)])
            .properties(height=260))


def yigin(u, baslik_y, renkler, adlar, bicim=",.0f"):
    return (alt.Chart(u).mark_bar(stroke="#121b2d", strokeWidth=1)
            .encode(x=x, y=alt.Y("deger:Q", title=baslik_y, stack=True, axis=EKSEN),
                    color=alt.Color("ad:N", title=None, legend=alt.Legend(orient="top"),
                                    scale=alt.Scale(domain=adlar, range=renkler), sort=adlar),
                    order=alt.Order("sira:Q"),
                    tooltip=[alt.Tooltip("etiket:N", title="Ay"), alt.Tooltip("ad:N", title="Kalem"),
                             alt.Tooltip("deger:Q", title=baslik_y, format=bicim)])
            .transform_calculate(sira=f"indexof({adlar!r}, datum.ad)")
            .properties(height=300))


# ---------------------------------------------------------------------
# Presler
# ---------------------------------------------------------------------
with sekme[0]:
    sol, sag = st.columns(2)
    with sol:
        st.subheader("Ton başına elektrik (kWh/ton)")
        ad = ['6"', '8"']
        st.altair_chart(cizgi(uzun(["p6_kwh_ton", "p8_kwh_ton"], ad), "kWh/ton", PALET[:2], ad),
                        use_container_width=True)
    with sag:
        st.subheader("Ton başına doğalgaz (m³/ton)")
        ad = ['6"', '8"', "Termik"]
        st.altair_chart(cizgi(uzun(["p6_gaz_ton", "p8_gaz_ton", "termik_gaz_ton"], ad), "m³/ton",
                              [PALET[0], PALET[1], PALET[3]], ad), use_container_width=True)
    st.caption("6\" ve 8\" oranları her presin kullandığı hammaddeye, termik oranı toplam pres "
               "üretimine göredir (Excel'deki gibi).")
    st.subheader("Dönem özeti")
    satirlar = []
    for ad_, on in (('6" pres', "p6"), ('8" pres', "p8")):
        satirlar.append({
            "Pres": ad_, "Hammadde (ton)": sayi((g[f"{on}_hammadde"] or 0) / 1000, 1),
            "Elektrik (kWh)": sayi(g[f"{on}_kwh"]), "kWh/ton": sayi(g[f"{on}_kwh_ton"], 1),
            "Doğalgaz (m³)": sayi(g[f"{on}_gaz"]), "m³/ton": sayi(g[f"{on}_gaz_ton"], 1),
            "Kompresör (kWh)": sayi(g[f"{on}_komp_kwh"]),
            "Kompresör saati": sayi(g[f"{on}_komp_saat"], 1)})
    st.dataframe(pd.DataFrame(satirlar), hide_index=True, use_container_width=True)
    st.caption("Kompresör tüketimi Excel'de çalışma saati × sabit güçle hesaplanır "
               "(6\" için 10 kW, 8\" için 16 kW).")

# ---------------------------------------------------------------------
# Elektrik
# ---------------------------------------------------------------------
with sekme[1]:
    ay_ay["diger_kwh"] = ay_ay["fab_kwh"] - ay_ay["prese_ait_kwh"] - ay_ay["boya_kwh"]
    ad = ["Pres hattı", "Boyahane", "Fabrikanın geri kalanı"]
    st.subheader("Fabrika elektrik tüketimi (MWh)")
    u = uzun(["prese_ait_kwh", "boya_kwh", "diger_kwh"], ad)
    u["deger"] = u["deger"] / 1000
    st.altair_chart(yigin(u, "MWh", [PALET[0], PALET[4], "#4f5a70"], ad, ",.1f"),
                    use_container_width=True)
    sol, sag = st.columns(2)
    with sol:
        st.subheader("Pres hattının payı (%)")
        u = uzun(["pres_elk_pay", "boya_elk_pay"], ["Pres hattı", "Boyahane"])
        u["deger"] = u["deger"] * 100
        st.altair_chart(cizgi(u, "%", [PALET[0], PALET[4]], ["Pres hattı", "Boyahane"]),
                        use_container_width=True)
    with sag:
        st.subheader("Ortalama elektrik fiyatı (TL/kWh)")
        ad = ["TL/kWh"]
        st.altair_chart(cizgi(uzun(["elk_birim"], ad), "TL/kWh", [PALET[2]], ad, ",.2f"),
                        use_container_width=True)
    st.caption("Pres hattı = ana pano − kompresör ana hat (12.000 kWh sabit) + preslerin kompresör "
               "tüketimi. Fiyat = fabrika faturası (KDV hariç) ÷ fabrika tüketimi.")

# ---------------------------------------------------------------------
# Doğalgaz
# ---------------------------------------------------------------------
with sekme[2]:
    ay_ay["diger_gaz"] = (ay_ay["fab_gaz_m3"] - ay_ay["p6_gaz"].fillna(0) - ay_ay["p8_gaz"].fillna(0)
                          - ay_ay["termik_gaz"].fillna(0) - ay_ay["boya_gaz"].fillna(0))
    ad = ['6" pres', '8" pres', "Termik", "Boyahane", "Fabrikanın geri kalanı"]
    st.subheader("Fabrika doğalgaz tüketimi (bin m³)")
    u = uzun(["p6_gaz", "p8_gaz", "termik_gaz", "boya_gaz", "diger_gaz"], ad)
    u["deger"] = u["deger"] / 1000
    st.altair_chart(yigin(u, "bin m³", [PALET[0], PALET[1], PALET[3], PALET[4], "#4f5a70"], ad,
                          ",.1f"), use_container_width=True)
    sol, sag = st.columns(2)
    with sol:
        st.subheader("Profil imalatı payı (%)")
        u = uzun(["pres_gaz_pay", "boya_gaz_pay"], ["Presler + termik", "Boyahane"])
        u["deger"] = u["deger"] * 100
        st.altair_chart(cizgi(u, "%", [PALET[0], PALET[4]], ["Presler + termik", "Boyahane"]),
                        use_container_width=True)
    with sag:
        st.subheader("Doğalgaz fiyatı (TL/m³)")
        ad = ["TL/m³"]
        st.altair_chart(cizgi(uzun(["gaz_birim"], ad), "TL/m³", [PALET[2]], ad, ",.2f"),
                        use_container_width=True)

# ---------------------------------------------------------------------
# Maliyet ($/ton)
# ---------------------------------------------------------------------
with sekme[3]:
    sol, sag = st.columns(2)
    ad = ["Elektrik", "Doğalgaz"]
    with sol:
        st.subheader("Presler enerji maliyeti ($/ton)")
        st.altair_chart(yigin(uzun(["pres_elk_usd_ton", "pres_gaz_usd_ton"], ad), "$/ton",
                              [PALET[0], PALET[1]], ad, ",.1f"), use_container_width=True)
    with sag:
        st.subheader("Boyahane enerji maliyeti ($/ton)")
        st.altair_chart(yigin(uzun(["boya_elk_usd_ton", "boya_gaz_usd_ton"], ad), "$/ton",
                              [PALET[0], PALET[1]], ad, ",.1f"), use_container_width=True)
    sol, sag = st.columns(2)
    with sol:
        st.subheader("Boyahane ton başına tüketim")
        ad2 = ["Elektrik (kWh/ton)", "Doğalgaz (m³/ton)"]
        st.altair_chart(cizgi(uzun(["boya_kwh_ton", "boya_gaz_ton"], ad2), "Birim/ton",
                              [PALET[0], PALET[1]], ad2), use_container_width=True)
    with sag:
        st.subheader("Dönem toplamı (TL)")
        st.dataframe(pd.DataFrame({
            "Kalem": ["Pres hattı elektrik", "Presler + termik doğalgaz", "Boyahane elektrik",
                      "Boyahane doğalgaz"],
            "TL": [sayi(g[c]) for c in ("pres_elk_tl", "pres_gaz_tl", "boya_elk_tl", "boya_gaz_tl")],
            "$": [sayi(g[c]) for c in ("pres_elk_usd", "pres_gaz_usd", "boya_elk_usd", "boya_gaz_usd")],
        }), hide_index=True, use_container_width=True)
    st.caption("Bölüm maliyeti = bölüm tüketimi × o ayın fabrika ortalama birim fiyatı; $ için "
               "TOPLAM sayfasındaki aylık dolar kuru kullanılır.")

# ---------------------------------------------------------------------
# Tablo
# ---------------------------------------------------------------------
with sekme[4]:
    kalemler = [
        ("Pres üretimi (kg)", "pres_uretim", 0), ("Boyahane üretimi (kg)", "boya_uretim", 0),
        ("Fabrika elektrik (kWh)", "fab_kwh", 0), ("Ana pano (kWh)", "ana_pano_kwh", 0),
        ("Pres hattı (kWh)", "prese_ait_kwh", 0), ('6" pres (kWh)', "p6_kwh", 0),
        ('8" pres (kWh)', "p8_kwh", 0), ("Kompresör (kWh)", "komp_kwh", 0),
        ("Boyahane (kWh)", "boya_kwh", 0), ("Fabrika doğalgaz (m³)", "fab_gaz_m3", 0),
        ('6" pres doğalgaz (m³)', "p6_gaz", 0), ('8" pres doğalgaz (m³)', "p8_gaz", 0),
        ("Termik doğalgaz (m³)", "termik_gaz", 0), ("Boyahane doğalgaz (m³)", "boya_gaz", 0),
        ("Elektrik faturası (TL)", "fab_elk_tl", 0), ("Doğalgaz faturası (TL)", "fab_gaz_tl", 0),
        ("Elektrik fiyatı (TL/kWh)", "elk_birim", 2), ("Doğalgaz fiyatı (TL/m³)", "gaz_birim", 2),
        ("Dolar kuru", "dolar", 2),
        ("Hat elektrik (kWh/ton)", "hat_kwh_ton", 1), ("Pres sayaç (kWh/ton)", "pres_kwh_ton", 1),
        ("Pres+termik doğalgaz (m³/ton)", "pres_gaz_ton", 1),
        ("Pres elektrik ($/ton)", "pres_elk_usd_ton", 1), ("Pres doğalgaz ($/ton)", "pres_gaz_usd_ton", 1),
        ("Pres enerji ($/ton)", "pres_enerji_usd_ton", 1),
        ("Boyahane elektrik (kWh/ton)", "boya_kwh_ton", 1), ("Boyahane doğalgaz (m³/ton)", "boya_gaz_ton", 1),
        ("Boyahane enerji ($/ton)", "boya_enerji_usd_ton", 1),
    ]
    tablo = {"Kalem": [a for a, _, _ in kalemler]}
    for i in range(n):
        s = ay_ay.iloc[i]
        tablo[s["etiket"]] = [sayi(s[c], o) for _, c, o in kalemler]
    if n > 1:
        tablo["Dönem"] = [sayi(g[c] if c != "dolar" else (g["fab_elk_tl"] / g["fab_elk_usd"]
                                                           if g.get("fab_elk_usd") else None), o)
                          for _, c, o in kalemler]
    tablo = pd.DataFrame(tablo)
    st.dataframe(tablo, hide_index=True, use_container_width=True, height=36 * len(kalemler) + 40)
    st.caption("'Dönem' sütununda miktarlar toplam, oranlar dönem toplamlarından hesaplanır; "
               "dolar kuru faturaya göre ağırlıklı ortalamadır.")
    st.download_button("⬇️ CSV indir", tablo.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name=f"enerji_{bas:%Y%m}_{bit:%Y%m}.csv", mime="text/csv")
