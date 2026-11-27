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

from ortak import SONUK, YAZI, AY_ADI, PALET, TEK_RENK, ay_etiketi, kaynak_notu, rapor_verisi, sayi

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

sekme = st.tabs(["📈 Aylık Trend", "🎯 Boya Sarfiyatı", "🧪 Kimyasal", "📊 Yıl Karşılaştırma",
                 "🏆 En İyi / En Zayıf", "📋 Tablo"])
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

with sekme[3]:
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

with sekme[4]:
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

with sekme[5]:
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


# ---------------------------------------------------------------------
# Boya sarfiyatı ve kimyasal ('2026 TOZ BOYA YILLIK ÜRETİM RAPORU' dosyası)
#   g/m² = boya kg × 1000 ÷ m²,  m²/kg = m² ÷ boya kg,  kg/ton = boya kg ÷ net ton
#   hurda boya % = hurda boya ÷ harcanan boya,  profil hurda % = hurda ÷ (net + hurda)
#   kimyasal g/m² = takviye kg × 1000 ÷ m² (kurulum hariç, Excel'deki gibi)
# ---------------------------------------------------------------------
detay_ = rapor_verisi("tozboya_detay")
hurda_ = rapor_verisi("tozboya_hurda_boya")
kim_ = rapor_verisi("tozboya_kimyasal")


@st.cache_data(show_spinner=False)
def aylik_boya(detay, hurda):
    a = (detay.assign(ay=detay["tarih"].dt.to_period("M").dt.to_timestamp())
         .groupby("ay").agg(m2=("m2", "sum"), net_kg=("net_kg", "sum"), hurda_kg=("hurda_kg", "sum"),
                            boya_kg=("boya_kg", "sum"), saat=("saat", "sum")).reset_index())
    a = a.merge(hurda, on="ay", how="left") if hurda is not None and not hurda.empty else \
        a.assign(hurda_boya_kg=float("nan"))
    return a


def boya_ozet(a):
    m2, net, hurda, boya = a["m2"].sum(), a["net_kg"].sum(), a["hurda_kg"].sum(), a["boya_kg"].sum()
    hb = a.dropna(subset=["hurda_boya_kg"])
    return {"m2": m2, "net": net, "boya": boya,
            "g_m2": boya * 1000 / m2 if m2 else None, "m2_kg": m2 / boya if boya else None,
            "kg_ton": boya / net * 1000 if net else None,
            "hurda_boya": hb["hurda_boya_kg"].sum() / hb["boya_kg"].sum() * 100
            if hb["boya_kg"].sum() else None,
            "profil_hurda": hurda / (net + hurda) * 100 if net + hurda else None,
            "m2_ton": m2 / net * 1000 if net else None}


def donem_ayi(aylar_):
    """Üstteki ay aralığı; kaydırıcı sondaysa daha yeni detay ayları da dahil."""
    son = bit if bit < aylar[-1] else max(aylar_.max(), bit)
    return aylar_.between(bas, son)


with sekme[1]:
    if detay_ is None or detay_[0].empty:
        st.info("'TOZ BOYA YILLIK ÜRETİM RAPORU' dosyası bulunamadı; boya sarfiyatı gösterilemiyor.")
    else:
        kaynak_notu(*detay_[1:])
        ab = aylik_boya(detay_[0], hurda_[0] if hurda_ else None)
        ab_d = ab[donem_ayi(ab["ay"])].copy()
        if ab_d.empty:
            st.info("Seçili aylarda boya sarfiyat verisi yok (dosya 2026 yılını kapsıyor).")
        else:
            b = boya_ozet(ab_d)
            onceki = ab[ab["ay"] < ab_d["ay"].min()].tail(len(ab_d))
            bp = boya_ozet(onceki) if len(onceki) == len(ab_d) else None

            def bfark(k, ondalik=0):
                return None if bp is None or bp[k] is None or b[k] is None else sayi(b[k] - bp[k], ondalik)

            st.caption(f"{ay_etiketi(ab_d['ay'].min())} – {ay_etiketi(ab_d['ay'].max())} · "
                       f"{sayi(b['m2'])} m² · {sayi(b['boya'])} kg boya"
                       + (f" · oklar önceki {len(ab_d)} ayla kıyas" if bp else ""))
            k = st.columns(5)
            k[0].metric("Boya sarfiyatı (g/m²)", sayi(b["g_m2"], 1), bfark("g_m2", 1),
                        delta_color="inverse", help="Harcanan boya × 1000 ÷ boyanan m²")
            k[1].metric("Verim (m²/kg boya)", sayi(b["m2_kg"], 2), bfark("m2_kg", 2),
                        help="Boyanan m² ÷ harcanan boya")
            k[2].metric("Boya (kg/ton profil)", sayi(b["kg_ton"], 1), bfark("kg_ton", 1),
                        delta_color="inverse", help=f"Ton başına {sayi(b['m2_ton'])} m² yüzey boyandı")
            k[3].metric("Hurda boya %", sayi(b["hurda_boya"], 1), bfark("hurda_boya", 1),
                        delta_color="inverse", help="Hurda boya kg ÷ harcanan boya (hurda boya girilen aylar)")
            k[4].metric("Profil hurda %", sayi(b["profil_hurda"], 2), bfark("profil_hurda", 2),
                        delta_color="inverse", help="Hurda kg ÷ (net + hurda kg)")

            ab_d["etiket"] = ab_d["ay"].map(ay_etiketi)
            ab_d["g_m2"] = ab_d["boya_kg"] * 1000 / ab_d["m2"]
            ab_d["kg_ton"] = ab_d["boya_kg"] / ab_d["net_kg"] * 1000
            ab_d["hurda_boya_yuzde"] = ab_d["hurda_boya_kg"] / ab_d["boya_kg"] * 100
            xb = alt.X("etiket:O", title=None, sort=list(ab_d["etiket"]), axis=alt.Axis(labelAngle=0))
            ip = [alt.Tooltip("etiket:N", title="Ay"), alt.Tooltip("m2:Q", title="m²", format=",.0f"),
                  alt.Tooltip("boya_kg:Q", title="Boya kg", format=",.0f"),
                  alt.Tooltip("g_m2:Q", title="g/m²", format=",.1f"),
                  alt.Tooltip("kg_ton:Q", title="kg/ton", format=",.1f"),
                  alt.Tooltip("hurda_boya_yuzde:Q", title="Hurda boya %", format=",.1f")]
            sol, sag = st.columns(2)
            with sol:
                st.subheader("Aylık boya sarfiyatı (g/m²)")
                cizgi = alt.Chart(ab_d).mark_line(strokeWidth=2, color=TEK_RENK,
                                                  point=alt.OverlayMarkDef(size=50, color=TEK_RENK)) \
                    .encode(x=xb, y=alt.Y("g_m2:Q", title="g/m²", scale=alt.Scale(zero=False)), tooltip=ip)
                ort = alt.Chart(pd.DataFrame({"y": [b["g_m2"]]})).mark_rule(
                    strokeDash=[4, 4], color=SONUK).encode(y="y:Q")
                st.altair_chart((cizgi + ort).properties(height=260), width="stretch")
                st.caption("Kesikli çizgi: dönem ortalaması. Düşük g/m² = daha az boya.")
            with sag:
                st.subheader("Hurda boya oranı (%)")
                st.altair_chart(
                    alt.Chart(ab_d.dropna(subset=["hurda_boya_yuzde"]))
                    .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=PALET[1])
                    .encode(x=xb, y=alt.Y("hurda_boya_yuzde:Q", title="%"), tooltip=ip)
                    .properties(height=260), width="stretch")

            dd = detay_[0][donem_ayi(detay_[0]["tarih"].dt.to_period("M").dt.to_timestamp())]

            def kirilim(alan):
                f = dd.groupby(alan).agg(boya=("boya_kg", "sum"), m2=("m2", "sum"),
                                         net=("net_kg", "sum"), parti=("parti", "nunique")).reset_index()
                f = f[(f["boya"] > 0) & (f["m2"] > 0)]
                f["g_m2"] = f["boya"] * 1000 / f["m2"]
                f["m2_kg"] = f["m2"] / f["boya"]
                return f.sort_values("boya", ascending=False)

            fr = kirilim("firma")
            st.subheader("Boya firmasına göre sarfiyat")
            st.altair_chart(
                alt.Chart(fr).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
                .encode(y=alt.Y("firma:N", title=None, sort=list(fr.sort_values("g_m2")["firma"])),
                        x=alt.X("g_m2:Q", title="g/m²"),
                        color=alt.condition(alt.datum.g_m2 > b["g_m2"], alt.value(PALET[1]),
                                            alt.value(TEK_RENK)),
                        tooltip=[alt.Tooltip("firma:N", title="Firma"),
                                 alt.Tooltip("boya:Q", title="Boya kg", format=",.0f"),
                                 alt.Tooltip("m2:Q", title="m²", format=",.0f"),
                                 alt.Tooltip("g_m2:Q", title="g/m²", format=",.1f"),
                                 alt.Tooltip("m2_kg:Q", title="m²/kg", format=",.2f"),
                                 alt.Tooltip("parti:Q", title="Parti")])
                .properties(height=34 * len(fr) + 20), width="stretch")
            st.caption(f"Turuncu: dönem ortalamasının ({sayi(b['g_m2'], 1)} g/m²) üstü. Boya, rengin "
                       "ilk satırına girildiği için sonraki satırlar aynı partiye (firmaya) sayılır.")

            def tablo(f, ad):
                return pd.DataFrame({ad: f[f.columns[0]], "Boya (kg)": f["boya"].map(sayi),
                                     "m²": f["m2"].map(sayi), "g/m²": f["g_m2"].map(lambda v: sayi(v, 1)),
                                     "m²/kg": f["m2_kg"].map(lambda v: sayi(v, 2)), "Parti": f["parti"]})
            a1, a2 = st.columns(2)
            a1.markdown("**Firma özeti**")
            a1.dataframe(tablo(fr, "Firma"), hide_index=True, width="stretch")
            a2.markdown("**En çok boya harcanan 10 renk**")
            a2.dataframe(tablo(kirilim("boya_kodu").head(10), "Renk"), hide_index=True, width="stretch")

with sekme[2]:
    if kim_ is None or kim_[0].empty:
        st.info("'TOZ BOYA YILLIK ÜRETİM RAPORU' dosyasında 'Kimyasal Takip' sayfası bulunamadı.")
    elif detay_ is None or detay_[0].empty:
        st.info("Kimyasal g/m² için boyanan m² gerekiyor; 'Yıllık Rapor' sayfası okunamadı.")
    else:
        kaynak_notu(*kim_[1:])
        km = kim_[0][donem_ayi(kim_[0]["ay"])]
        km = km[(km["takviye_kg"] + km["kurulum_kg"] + km["durulama_kg"]) > 0]
        ab = aylik_boya(detay_[0], None)
        ab_d = ab[donem_ayi(ab["ay"])]
        m2, ton = ab_d["m2"].sum(), ab_d["net_kg"].sum() / 1000
        if km.empty or not m2:
            st.info("Seçili aylarda kimyasal verisi yok.")
        else:
            st.caption(f"{ay_etiketi(km['ay'].min())} – {ay_etiketi(km['ay'].max())} · "
                       f"{sayi(m2)} m² · {sayi(ton, 1)} ton profil")
            k = st.columns(4)
            k[0].metric("Takviye kimyasal (kg)", sayi(km["takviye_kg"].sum()))
            k[1].metric("Kimyasal (g/m²)", sayi(km["takviye_kg"].sum() * 1000 / m2, 1),
                        help="Takviye kg × 1000 ÷ boyanan m² (kurulum hariç)")
            k[2].metric("Kimyasal (kg/ton profil)", sayi(km["takviye_kg"].sum() / ton, 2) if ton else "–")
            k[3].metric("Banyo kurulumu (kg)", sayi(km["kurulum_kg"].sum()),
                        help=f"Durulamaya eklenen: {sayi(km['durulama_kg'].sum() / 1000, 1)} ton")

            ks = km.groupby("kimyasal").agg(urun=("urun", "first"), kurulum=("kurulum_kg", "sum"),
                                            takviye=("takviye_kg", "sum"), alt_=("hedef_alt", "first"),
                                            ust=("hedef_ust", "first")).reset_index()
            ks["g_m2"] = ks["takviye"] * 1000 / m2

            def durum(r):
                if pd.isna(r["alt_"]):
                    return "–"
                return "🔺 Üstü" if r["g_m2"] > r["ust"] else "🔻 Altı" \
                    if r["g_m2"] < r["alt_"] else "✅ İçinde"
            st.subheader("Banyolara göre kimyasal tüketimi")
            st.dataframe(pd.DataFrame({
                "Banyo": ks["kimyasal"], "Ürün": ks["urun"], "Kurulum (kg)": ks["kurulum"].map(sayi),
                "Takviye (kg)": ks["takviye"].map(sayi), "g/m²": ks["g_m2"].map(lambda v: sayi(v, 2)),
                "kg/ton": (ks["takviye"] / ton).map(lambda v: sayi(v, 2)) if ton else "–",
                "Hedef (g/m²)": ks.apply(lambda r: f"{sayi(r['alt_'], 1)}–{sayi(r['ust'], 1)}"
                                         if pd.notna(r["alt_"]) else "–", axis=1),
                "Durum": ks.apply(durum, axis=1)}), hide_index=True, width="stretch")

            ka = km.groupby(["ay", "kimyasal"])["takviye_kg"].sum().reset_index() \
                .merge(ab_d[["ay", "m2"]], on="ay", how="left") \
                .merge(ks[["kimyasal", "alt_", "ust"]], on="kimyasal", how="left")
            ka["g_m2"] = ka["takviye_kg"] * 1000 / ka["m2"]
            ka["etiket"] = ka["ay"].map(ay_etiketi)
            sira_k = list(ab_d.sort_values("ay")["ay"].map(ay_etiketi))
            banyolar = list(ks["kimyasal"])
            st.subheader("Aylık kimyasal tüketimi (g/m²) ve hedef aralığı")
            kol = st.columns(2)
            for n, banyo in enumerate(banyolar):
                kb = ka[ka["kimyasal"] == banyo]
                renk = PALET[n % len(PALET)]
                with kol[n % 2]:
                    st.markdown(f"**{banyo}**")
                    katman = alt.Chart(kb).mark_line(strokeWidth=2, color=renk,
                                                     point=alt.OverlayMarkDef(size=50, color=renk)).encode(
                        x=alt.X("etiket:O", title=None, sort=sira_k, axis=alt.Axis(labelAngle=0)),
                        y=alt.Y("g_m2:Q", title="g/m²"),
                        tooltip=[alt.Tooltip("etiket:N", title="Ay"),
                                 alt.Tooltip("takviye_kg:Q", title="Takviye kg", format=",.0f"),
                                 alt.Tooltip("m2:Q", title="m²", format=",.0f"),
                                 alt.Tooltip("g_m2:Q", title="g/m²", format=",.2f")])
                    h = ks[ks["kimyasal"] == banyo].iloc[0]
                    if pd.notna(h["alt_"]):
                        bant = alt.Chart(pd.DataFrame({"a": [h["alt_"]], "u": [h["ust"]]})) \
                            .mark_rect(color=SONUK, opacity=0.18).encode(y="a:Q", y2="u:Q")
                        katman = bant + katman
                    st.altair_chart(katman.properties(height=200), width="stretch")
            st.caption("Gri bant: Excel'deki öngörülen aralık. Takviye ayın tamamına yazılır; az "
                       "üretimli aylarda g/m² şişer, dönem toplamına bakın.")

            st.subheader("Aylık takviye miktarı (kg)")
            st.altair_chart(
                alt.Chart(ka).mark_bar().encode(
                    x=alt.X("etiket:O", title=None, sort=sira_k, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("sum(takviye_kg):Q", title="kg"),
                    color=alt.Color("kimyasal:N", title=None, legend=alt.Legend(orient="top"),
                                    scale=alt.Scale(domain=banyolar, range=PALET[:len(banyolar)])),
                    tooltip=[alt.Tooltip("etiket:N", title="Ay"), alt.Tooltip("kimyasal:N", title="Banyo"),
                             alt.Tooltip("takviye_kg:Q", title="kg", format=",.0f")])
                .properties(height=260), width="stretch")
