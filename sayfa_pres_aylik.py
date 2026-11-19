"""Pres Üretimler Aylık 2023-2026 raporu.

'ALBOND PRES ÜRETİMLER AYLIK' dosyasındaki 6" ve 8" pres sayfalarından
(kg/ay, kg/gün, kg/saat blokları) gelir. Ay bazında veri olduğu için dönem
ay aralığı olarak seçilir; oklar geçen yılın aynı aylarıyla kıyastır.

Toplamlar 6" ve 8" sayfalarından hesaplanır:
  çalışma saati = kg/ay ÷ kg/saat,  çalışma günü = kg/ay ÷ kg/gün
  kg/saat (dönem) = toplam kg ÷ toplam saat   (gerçek saatlik hız)
  kg/gün  (dönem) = her presin kg ÷ gün değerinin toplamı (Excel'deki gibi)
"""
import altair as alt
import pandas as pd
import streamlit as st

from ortak import AY_ADI, PALET, PRES_RENK, ay_etiketi, kaynak_notu, rapor_verisi, sayi

YIL_RENK = PALET  # yıllar sabit sırayla (2023 → mavi, 2024 → turuncu, ...)

st.title("📅 Pres Üretimler Aylık 2023–2026")

veri_ = rapor_verisi("uretim_aylik")
if veri_ is None or veri_[0].empty:
    st.error("Veri klasöründe 'PRES ÜRETİMLER AYLIK' dosyası bulunamadı.")
    st.stop()
ham, kaynak_adi, degisme, mod = veri_
kaynak_notu(kaynak_adi, degisme, mod)


@st.cache_data(show_spinner=False)
def aylik_tablo(ham):
    """Pres × ay satırları: kg, saat, gün, kg/gün, kg/saat."""
    d = ham[ham["kaynak"].isin(['6"', '8"'])]
    t = d.pivot_table(index=["kaynak", "tarih"], columns="olcu", values="deger",
                      aggfunc="sum").reset_index().rename(columns={"kaynak": "pres"})
    for c in ("kg/ay", "kg/gün", "kg/saat"):
        if c not in t:
            t[c] = float("nan")
    t = t[t["kg/ay"].fillna(0) > 0].copy()
    t["kg"] = t["kg/ay"]
    t["saat"] = (t["kg"] / t["kg/saat"]).where(t["kg/saat"] > 0)
    t["gun"] = (t["kg"] / t["kg/gün"]).where(t["kg/gün"] > 0)
    t["yil"] = t["tarih"].dt.year
    t["ay_no"] = t["tarih"].dt.month
    return t[["pres", "tarih", "yil", "ay_no", "kg", "saat", "gun", "kg/gün", "kg/saat"]]


t_hepsi = aylik_tablo(ham)
aylar = sorted(t_hepsi["tarih"].unique())


def ozet(t):
    """Dönem toplamları (seçili presler birlikte)."""
    kg = t["kg"].sum()
    saat = t["saat"].sum()
    ay_say = t["tarih"].nunique()
    kg_gun = sum((g["kg"].sum() / g["gun"].sum()) for _, g in t.groupby("pres")
                 if g["gun"].sum() > 0)
    return {"kg": kg, "ay": ay_say, "aylik_ort": kg / ay_say if ay_say else None,
            "kg_saat": kg / saat if saat else None, "saat": saat,
            "kg_gun": kg_gun or None}


# ---------------------------------------------------------------------
# Filtreler
# ---------------------------------------------------------------------
f1, f2 = st.columns([1, 3])
presler = f1.multiselect("Pres", ['6"', '8"'], default=['6"', '8"'])
bas, bit = f2.select_slider("Ay aralığı", options=aylar, value=(aylar[0], aylar[-1]),
                            format_func=ay_etiketi)
t = t_hepsi[t_hepsi["pres"].isin(presler) & t_hepsi["tarih"].between(bas, bit)].copy()
if t.empty:
    st.warning("Seçilen pres ve ay aralığında kayıt yok.")
    st.stop()

# Geçen yılın aynı ayları
gy_bas, gy_bit = bas - pd.DateOffset(years=1), bit - pd.DateOffset(years=1)
gy = t_hepsi[t_hepsi["pres"].isin(presler) & t_hepsi["tarih"].between(gy_bas, gy_bit)]
g = ozet(t)
# Kıyas: geçen yıl aynı ayda verisi olan pres-aylar karşılaştırılır (birebir)
gy_anahtar = set(zip(gy["pres"], gy["tarih"] + pd.DateOffset(years=1)))
t_es = t[[(pr, tr) in gy_anahtar for pr, tr in zip(t["pres"], t["tarih"])]]
gy_es = gy[[(pr, tr + pd.DateOffset(years=1)) in set(zip(t_es["pres"], t_es["tarih"]))
            for pr, tr in zip(gy["pres"], gy["tarih"])]]
g_es = ozet(t_es) if not t_es.empty else None
p = ozet(gy_es) if not t_es.empty else None
eksik = len(t) - len(t_es)


def fark(anahtar, carpan=1.0, ondalik=0):
    if p is None or p[anahtar] is None or g_es[anahtar] is None:
        return None
    return f"{sayi((g_es[anahtar] - p[anahtar]) * carpan, ondalik)}"


en_iyi = t.groupby("tarih")["kg"].sum().idxmax()
en_iyi_ton = t.groupby("tarih")["kg"].sum().max() / 1000
st.markdown(f"#### {ay_etiketi(bas)} – {ay_etiketi(bit)}  ·  {g['ay']} ay  ·  "
            f"en iyi ay {ay_etiketi(en_iyi)} ({sayi(en_iyi_ton, 1)} ton)")
if p is not None:
    st.caption(f"Oklar geçen yılın aynı aylarıyla ({ay_etiketi(gy_bas)} – {ay_etiketi(gy_bit)}) "
               "kıyastır." + (f" Geçen yıl verisi olmayan {eksik} pres-ay kıyasa katılmadı."
                              if eksik else ""))
else:
    st.caption("Geçen yılın aynı aylarında veri olmadığı için kıyas oku gösterilmiyor.")

k = st.columns(4)
k[0].metric("Toplam Üretim (ton)", sayi(g["kg"] / 1000, 1), fark("kg", 1 / 1000, 1))
k[1].metric("Aylık Ortalama (ton)", sayi(g["aylik_ort"] / 1000, 1), fark("aylik_ort", 1 / 1000, 1))
k[2].metric("Saatlik Üretim (kg/saat)", sayi(g["kg_saat"]), fark("kg_saat"),
            help="Toplam kg ÷ toplam çalışma saati (saat = kg/ay ÷ kg/saat)")
k[3].metric("Günlük Üretim (kg/gün)", sayi(g["kg_gun"]), fark("kg_gun"),
            help="Seçili preslerin çalışma günü başına üretimlerinin toplamı")

sekme = st.tabs(["📈 Aylık Trend", "📊 Yıl Karşılaştırma", "🏆 En İyi / En Zayıf",
                 "📋 Tablo"])

t["etiket"] = t["tarih"].map(ay_etiketi)
t["ton"] = t["kg"] / 1000
sira = [ay_etiketi(a) for a in sorted(t["tarih"].unique())]
x = alt.X("etiket:O", title=None, sort=sira,
          axis=alt.Axis(labelAngle=0 if len(sira) <= 14 else -45))
renk = alt.Color("pres:N", scale=PRES_RENK, title="Pres", legend=alt.Legend(orient="top"))
ipucu = [alt.Tooltip("etiket:N", title="Ay"), alt.Tooltip("pres:N", title="Pres"),
         alt.Tooltip("ton:Q", title="Ton", format=",.1f"),
         alt.Tooltip("kg/gün:Q", title="kg/gün", format=",.0f"),
         alt.Tooltip("kg/saat:Q", title="kg/saat", format=",.0f"),
         alt.Tooltip("saat:Q", title="Çalışma saati", format=",.0f")]

# ---------------------------------------------------------------------
# Aylık trend
# ---------------------------------------------------------------------
with sekme[0]:
    st.subheader("Aylık üretim (ton)")
    st.altair_chart(
        alt.Chart(t).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3,
                              stroke="white", strokeWidth=1)
        .encode(x=x, y=alt.Y("ton:Q", title="Ton", stack=True), color=renk, tooltip=ipucu)
        .properties(height=300), use_container_width=True)
    sol, sag = st.columns(2)
    cizgi = alt.Chart(t).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=40))
    with sol:
        st.subheader("Saatlik üretim (kg/saat)")
        st.altair_chart(cizgi.encode(x=x, y=alt.Y("kg/saat:Q", title="kg/saat"), color=renk,
                                     tooltip=ipucu).properties(height=250),
                        use_container_width=True)
    with sag:
        st.subheader("Günlük üretim (kg/gün)")
        st.altair_chart(cizgi.encode(x=x, y=alt.Y("kg/gün:Q", title="kg/gün"), color=renk,
                                     tooltip=ipucu).properties(height=250),
                        use_container_width=True)

# ---------------------------------------------------------------------
# Yıl karşılaştırma (aynı ayların yıllara göre durumu)
# ---------------------------------------------------------------------
with sekme[1]:
    olcu = st.radio("Gösterge", ["Üretim (ton)", "kg/saat", "kg/gün"], horizontal=True)
    yg = t_hepsi[t_hepsi["pres"].isin(presler)]
    satir = []
    for (yil, ay_no), grp in yg.groupby(["yil", "ay_no"]):
        o_ = ozet(grp)
        satir.append({"yil": str(yil), "ay_no": ay_no, "ay": AY_ADI[ay_no - 1],
                      "Üretim (ton)": o_["kg"] / 1000, "kg/saat": o_["kg_saat"],
                      "kg/gün": o_["kg_gun"]})
    yt = pd.DataFrame(satir)
    yillar = sorted(yt["yil"].unique())
    st.subheader(f"Aylara göre {olcu} · yıl yıl")
    st.altair_chart(
        alt.Chart(yt).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=50))
        .encode(x=alt.X("ay:O", sort=AY_ADI, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y(f"{olcu}:Q", title=olcu),
                color=alt.Color("yil:N", title="Yıl", legend=alt.Legend(orient="top"),
                                scale=alt.Scale(domain=yillar, range=YIL_RENK[:len(yillar)])),
                tooltip=[alt.Tooltip("ay:N", title="Ay"), alt.Tooltip("yil:N", title="Yıl"),
                         alt.Tooltip(f"{olcu}:Q", title=olcu, format=",.1f")])
        .properties(height=300), use_container_width=True)

    st.subheader("Yıllık özet")
    yil_satir = []
    for yil, grp in yg.groupby("yil"):
        for pres in presler + (["Toplam"] if len(presler) > 1 else []):
            gg = grp if pres == "Toplam" else grp[grp["pres"] == pres]
            if gg.empty:
                continue
            o_ = ozet(gg)
            yil_satir.append({"Yıl": str(yil), "Pres": pres,
                              "Ay sayısı": o_["ay"],
                              "Toplam (ton)": round(o_["kg"] / 1000, 1),
                              "Aylık ort. (ton)": round(o_["aylik_ort"] / 1000, 1),
                              "kg/saat": round(o_["kg_saat"]) if o_["kg_saat"] else None,
                              "kg/gün": round(o_["kg_gun"]) if o_["kg_gun"] else None,
                              "Çalışma saati": round(o_["saat"])})
    st.dataframe(pd.DataFrame(yil_satir), hide_index=True, use_container_width=True,
                 column_config={c: st.column_config.NumberColumn(format="localized")
                                for c in ["Toplam (ton)", "Aylık ort. (ton)", "kg/saat",
                                          "kg/gün", "Çalışma saati"]})
    st.caption("Yıllar eksik aylarla başlayabilir: 6\" pres Ağustos 2023'ten, 8\" pres "
               "Mayıs 2024'ten itibaren veri var; içinde bulunulan yıl da henüz tamamlanmadı.")

# ---------------------------------------------------------------------
# En iyi / en zayıf aylar
# ---------------------------------------------------------------------
with sekme[2]:
    def liste(tt, sutun, artan):
        s = tt.sort_values(sutun, ascending=artan).head(5)
        return pd.DataFrame({"Ay": s["tarih"].map(ay_etiketi), "Pres": s["pres"],
                             "Üretim (ton)": s["ton"].map(lambda v: sayi(v, 1)),
                             "kg/saat": s["kg/saat"].map(sayi), "kg/gün": s["kg/gün"].map(sayi)})
    for pres in presler:
        tt = t[t["pres"] == pres]
        if tt.empty:
            continue
        st.subheader(f'{pres} pres')
        a1, a2 = st.columns(2)
        a1.markdown("**🏆 En yüksek üretim**")
        a1.dataframe(liste(tt, "kg", False), hide_index=True, use_container_width=True)
        a2.markdown("**⬇️ En düşük üretim**")
        a2.dataframe(liste(tt, "kg", True), hide_index=True, use_container_width=True)
        a1.markdown("**⚡ En yüksek kg/saat**")
        a1.dataframe(liste(tt, "kg/saat", False), hide_index=True, use_container_width=True)
        a2.markdown("**🐢 En düşük kg/saat**")
        a2.dataframe(liste(tt, "kg/saat", True), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------
# Tablo (Excel'deki gibi: aylar satırda, yıllar sütunda)
# ---------------------------------------------------------------------
with sekme[3]:
    c1, c2 = st.columns(2)
    tablo_pres = c1.selectbox("Pres", presler + (["Toplam"] if len(presler) > 1 else []),
                              index=len(presler) if len(presler) > 1 else 0)
    tablo_olcu = c2.selectbox("Gösterge ", ["Üretim (kg/ay)", "kg/gün", "kg/saat"])
    tp = t if tablo_pres == "Toplam" else t[t["pres"] == tablo_pres]
    satir = []
    for (yil, ay_no), grp in tp.groupby(["yil", "ay_no"]):
        o_ = ozet(grp)
        satir.append({"Ay": AY_ADI[ay_no - 1], "ay_no": ay_no, "yil": str(yil),
                      "deger": {"Üretim (kg/ay)": o_["kg"], "kg/gün": o_["kg_gun"],
                                "kg/saat": o_["kg_saat"]}[tablo_olcu]})
    pv = (pd.DataFrame(satir).pivot_table(index=["ay_no", "Ay"], columns="yil", values="deger")
          .reset_index().drop(columns="ay_no"))
    yil_sut = [c for c in pv.columns if c != "Ay"]
    alt_satir = {"Ay": "Ortalama", **{c: pv[c].mean() for c in yil_sut}}
    if tablo_olcu == "Üretim (kg/ay)":
        pv = pd.concat([pv, pd.DataFrame([alt_satir, {"Ay": "TOPLAM", **{c: pv[c].sum() for c in yil_sut}}])],
                       ignore_index=True)
    else:
        pv = pd.concat([pv, pd.DataFrame([alt_satir])], ignore_index=True)
    st.dataframe(pv.round(0), hide_index=True, use_container_width=True,
                 column_config={c: st.column_config.NumberColumn(format="localized") for c in yil_sut})
    if tablo_pres == "Toplam" and tablo_olcu == "kg/saat":
        st.caption("Toplam kg/saat burada iki presin gerçek ortalama hızıdır (toplam kg ÷ toplam "
                   "saat). Excel'deki 'PRESLER TOPLAM' sayfası iki presin kg/saat değerlerini "
                   "topluyor, o yüzden orada yaklaşık iki katı görünür.")
    st.download_button("⬇️ CSV indir", pv.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=f"pres_aylik_{tablo_pres.replace(chr(34), 'inc')}.csv", mime="text/csv")
