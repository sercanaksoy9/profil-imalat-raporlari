"""Toz Boya Üretimleri Aylık 2025-2026 raporu.

'ALBOND TOZ BOYA ÜRETİMLERİ AYLIK' dosyasının 'TOZ BOYA TOPLAM' sayfasından
(kg/ay, kg/gün, kg/saat blokları) gelir; o sayfa diğerinden daha eksiksizdir.
Ay bazında veri olduğu için dönem ay aralığı olarak seçilir; oklar geçen
yılın aynı aylarıyla (verisi olan aylar) kıyastır.
  çalışma saati = kg/ay ÷ kg/saat,  çalışma günü = kg/ay ÷ kg/gün
  kg/saat (dönem) = toplam kg ÷ toplam saat,  kg/gün = toplam kg ÷ toplam gün
"""
import altair as alt
import pandas as pd
import streamlit as st

from ortak import YAZI, AY_ADI, PALET, TEK_RENK, ay_etiketi, kaynak_notu, rapor_verisi, sayi

st.title("🎨 Toz Boya Üretimleri Aylık 2025–2026")

veri_ = rapor_verisi("tozboya_aylik")
if veri_ is None or veri_[0].empty:
    st.error("Veri klasöründe 'TOZ BOYA ÜRETİMLERİ AYLIK' dosyası bulunamadı.")
    st.stop()
ham, kaynak_adi, degisme, mod = veri_
kaynak_notu(kaynak_adi, degisme, mod)


@st.cache_data(show_spinner=False)
def aylik_tablo(ham):
    d = ham[ham["kaynak"] == "Toz Boya Toplam"]
    if d.empty:                       # eski düzende yalnız 'TOZ BOYA' sayfası olabilir
        d = ham
    t = d.pivot_table(index="tarih", columns="olcu", values="deger", aggfunc="sum").reset_index()
    for c in ("kg/ay", "kg/gün", "kg/saat"):
        if c not in t:
            t[c] = float("nan")
    t = t[t["kg/ay"].fillna(0) > 0].copy()
    t["kg"] = t["kg/ay"]
    t["saat"] = (t["kg"] / t["kg/saat"]).where(t["kg/saat"] > 0)
    t["gun"] = (t["kg"] / t["kg/gün"]).where(t["kg/gün"] > 0)
    t["yil"] = t["tarih"].dt.year
    t["ay_no"] = t["tarih"].dt.month
    return t[["tarih", "yil", "ay_no", "kg", "saat", "gun", "kg/gün", "kg/saat"]].reset_index(drop=True)


t_hepsi = aylik_tablo(ham)
aylar = list(t_hepsi["tarih"])


def ozet(t):
    kg, saat, gun, n = t["kg"].sum(), t["saat"].sum(), t["gun"].sum(), len(t)
    return {"kg": kg, "ay": n, "aylik_ort": kg / n if n else None,
            "kg_saat": kg / saat if saat else None, "kg_gun": kg / gun if gun else None,
            "saat": saat, "gun": gun}


if len(aylar) > 1:
    bas, bit = st.select_slider("Ay aralığı", options=aylar, value=(aylar[0], aylar[-1]),
                                format_func=ay_etiketi)
else:
    bas = bit = aylar[0]
t = t_hepsi[t_hepsi["tarih"].between(bas, bit)].copy()
g = ozet(t)

# Geçen yılın aynı ayları (yalnız iki yılda da verisi olan aylar kıyaslanır)
gecen = set(t_hepsi["tarih"] + pd.DateOffset(years=1))
t_es = t[t["tarih"].isin(gecen)]
gy_es = t_hepsi[t_hepsi["tarih"].isin(set(t_es["tarih"] - pd.DateOffset(years=1)))]
g_es = ozet(t_es) if not t_es.empty else None
p = ozet(gy_es) if not t_es.empty else None


def fark(anahtar, carpan=1.0, ondalik=0):
    if p is None or p[anahtar] is None or g_es[anahtar] is None:
        return None
    return sayi((g_es[anahtar] - p[anahtar]) * carpan, ondalik)


en_iyi = t.loc[t["kg"].idxmax()]
st.markdown(f"#### {ay_etiketi(bas)} – {ay_etiketi(bit)}  ·  {g['ay']} ay  ·  en iyi ay "
            f"{ay_etiketi(en_iyi['tarih'])} ({sayi(en_iyi['kg'] / 1000, 1)} ton)")
if p is not None:
    eksik = len(t) - len(t_es)
    st.caption("Oklar geçen yılın aynı aylarıyla kıyastır"
               + (f"; geçen yıl verisi olmayan {eksik} ay kıyasa katılmadı." if eksik else "."))
else:
    st.caption("Geçen yılın aynı aylarında veri olmadığı için kıyas oku gösterilmiyor.")

k = st.columns(4)
k[0].metric("Toplam Üretim (ton)", sayi(g["kg"] / 1000, 1), fark("kg", 1 / 1000, 1))
k[1].metric("Aylık Ortalama (ton)", sayi(g["aylik_ort"] / 1000, 1), fark("aylik_ort", 1 / 1000, 1))
k[2].metric("Saatlik Üretim (kg/saat)", sayi(g["kg_saat"]), fark("kg_saat"),
            help="Toplam kg ÷ toplam çalışma saati (saat = kg/ay ÷ kg/saat)")
k[3].metric("Günlük Üretim (kg/gün)", sayi(g["kg_gun"]), fark("kg_gun"),
            help="Toplam kg ÷ toplam çalışma günü")

sekme = st.tabs(["📈 Aylık Trend", "📊 Yıl Karşılaştırma", "🏆 En İyi / En Zayıf", "📋 Tablo"])
t["etiket"] = t["tarih"].map(ay_etiketi)
t["ton"] = t["kg"] / 1000
sira = list(t["etiket"])
x = alt.X("etiket:O", title=None, sort=sira, axis=alt.Axis(labelAngle=0 if len(sira) <= 12 else -45))
EKSEN = alt.Axis(labelExpr="replace(datum.label, ',', '.')")
ipucu = [alt.Tooltip("etiket:N", title="Ay"), alt.Tooltip("ton:Q", title="Ton", format=",.1f"),
         alt.Tooltip("kg/gün:Q", title="kg/gün", format=",.0f"),
         alt.Tooltip("kg/saat:Q", title="kg/saat", format=",.0f"),
         alt.Tooltip("saat:Q", title="Çalışma saati", format=",.0f")]

with sekme[0]:
    st.subheader("Aylık toz boya üretimi (ton)")
    st.altair_chart(
        alt.Chart(t).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=TEK_RENK)
        .encode(x=x, y=alt.Y("ton:Q", title="Ton", axis=EKSEN), tooltip=ipucu)
        .properties(height=300), width="stretch")
    sol, sag = st.columns(2)
    for kolon, alan, baslik, renk in ((sol, "kg/saat", "Saatlik üretim (kg/saat)", PALET[1]),
                                      (sag, "kg/gün", "Günlük üretim (kg/gün)", PALET[2])):
        with kolon:
            st.subheader(baslik)
            st.altair_chart(
                alt.Chart(t).mark_line(strokeWidth=2, color=renk,
                                       point=alt.OverlayMarkDef(size=50, color=renk))
                .encode(x=x, y=alt.Y(f"{alan}:Q", title=alan, axis=EKSEN), tooltip=ipucu)
                .properties(height=250), width="stretch")

with sekme[1]:
    olcu = st.radio("Gösterge", ["Üretim (ton)", "kg/saat", "kg/gün"], horizontal=True)
    yt = t_hepsi.assign(**{"Üretim (ton)": t_hepsi["kg"] / 1000, "yil": t_hepsi["yil"].astype(str),
                           "ay": t_hepsi["ay_no"].map(lambda a: AY_ADI[a - 1])})
    yillar = sorted(yt["yil"].unique())
    st.subheader(f"Aylara göre {olcu} · yıl yıl")
    st.altair_chart(
        alt.Chart(yt).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=50))
        .encode(x=alt.X("ay:O", sort=AY_ADI, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y(f"{olcu}:Q", title=olcu, axis=EKSEN),
                color=alt.Color("yil:N", title="Yıl", legend=alt.Legend(orient="top"),
                                scale=alt.Scale(domain=yillar, range=PALET[:len(yillar)])),
                tooltip=[alt.Tooltip("ay:N", title="Ay"), alt.Tooltip("yil:N", title="Yıl"),
                         alt.Tooltip(f"{olcu}:Q", title=olcu, format=",.1f")])
        .properties(height=300), width="stretch")

    st.subheader("Yıllık özet")
    yo = pd.DataFrame([{**ozet(grp), "Yıl": str(yil)} for yil, grp in t_hepsi.groupby("yil")])
    yo["ton"] = yo["kg"] / 1000
    yo["ton_yazi"] = yo["ton"].map(lambda v: sayi(v, 1))
    temel = alt.Chart(yo).encode(x=alt.X("Yıl:O", title=None, axis=alt.Axis(
        labelAngle=0, labelPadding=26, labelFontSize=14, labelFontWeight="bold", ticks=False)))
    cubuk = temel.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=TEK_RENK,
                           size=70).encode(
        y=alt.Y("ton:Q", title="Ton", axis=EKSEN),
        tooltip=[alt.Tooltip("Yıl:N"), alt.Tooltip("ay:Q", title="Ay sayısı"),
                 alt.Tooltip("ton:Q", title="Toplam ton", format=",.1f"),
                 alt.Tooltip("kg_saat:Q", title="kg/saat", format=",.0f"),
                 alt.Tooltip("kg_gun:Q", title="kg/gün", format=",.0f")])
    yazi = temel.mark_text(baseline="top", dy=6, fontSize=12, color=YAZI).encode(
        y=alt.datum(0), text="ton_yazi:N")
    st.altair_chart((cubuk + yazi).properties(height=300), width="stretch")
    st.caption("2025 Mayıs'tan itibaren veri var (Ağustos–Eylül 2025 üretim yok); 2026 henüz "
               "tamamlanmadı. Yıl toplamları farklı ay sayılarını kapsar.")

with sekme[2]:
    def liste(tt, sutun, artan):
        s = tt.sort_values(sutun, ascending=artan).head(5)
        return pd.DataFrame({"Ay": s["etiket"], "Üretim (ton)": s["ton"].map(lambda v: sayi(v, 1)),
                             "kg/saat": s["kg/saat"].map(sayi), "kg/gün": s["kg/gün"].map(sayi)})
    a1, a2 = st.columns(2)
    a1.markdown("**🏆 En yüksek üretim**")
    a1.dataframe(liste(t, "kg", False), hide_index=True, width="stretch")
    a2.markdown("**⬇️ En düşük üretim**")
    a2.dataframe(liste(t, "kg", True), hide_index=True, width="stretch")
    a1.markdown("**⚡ En yüksek kg/saat**")
    a1.dataframe(liste(t, "kg/saat", False), hide_index=True, width="stretch")
    a2.markdown("**🐢 En düşük kg/saat**")
    a2.dataframe(liste(t, "kg/saat", True), hide_index=True, width="stretch")

with sekme[3]:
    tablo_olcu = st.selectbox("Gösterge ", ["Üretim (kg/ay)", "kg/gün", "kg/saat"])
    alan = {"Üretim (kg/ay)": "kg", "kg/gün": "kg/gün", "kg/saat": "kg/saat"}[tablo_olcu]
    pv = (t.assign(Ay=t["ay_no"].map(lambda a: AY_ADI[a - 1]), yil=t["yil"].astype(str))
          .pivot_table(index=["ay_no", "Ay"], columns="yil", values=alan).reset_index()
          .drop(columns="ay_no"))
    yil_sut = [c for c in pv.columns if c != "Ay"]
    alt_sat = [{"Ay": "Ortalama", **{c: pv[c].mean() for c in yil_sut}}]
    if alan == "kg":
        alt_sat.append({"Ay": "TOPLAM", **{c: pv[c].sum() for c in yil_sut}})
    pv = pd.concat([pv, pd.DataFrame(alt_sat)], ignore_index=True)
    st.dataframe(pv.round(0), hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="localized") for c in yil_sut})
    st.caption("Ortalama satırı Excel'deki gibi ayların basit ortalamasıdır; üstteki göstergeler "
               "ise toplam kg ÷ toplam saat/gün ile hesaplanır.")
    st.download_button("⬇️ CSV indir", pv.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name="toz_boya_aylik.csv", mime="text/csv")
