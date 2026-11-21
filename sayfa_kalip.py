"""Kalıp Bazlı Arama sayfası.

Kalıp numarasıyla arama yapılır; seçilen kalıbın baskı hızı (piston),
firesi, saatlik üretimi ve baskı detayları gösterilir. Kayıtlar pres
DASHBOARD dosyasının 'Temiz veri' sayfasından gelir (her satır bir baskı).

Fire = (brüt kg − net kg) / brüt kg
kg/saat = net kg ÷ baskı süresi (saat)
Baskı hızı = piston hızı (mm/s), biyet adediyle ağırlıklı ortalama
Oklar: seçili dönem, aynı kalıbın dönem öncesi tüm baskılarıyla kıyaslanır.
"""
import altair as alt
import pandas as pd
import streamlit as st

import musteriler
from ortak import PRES_RENK, TEK_RENK, ay_etiketi, donem_sec, kaynak_notu, rapor_verisi, sayi

st.title("🔩 Kalıp Bazlı Arama")

veri_ = rapor_verisi("kalip_kayitlari")
if veri_ is None or veri_[0].empty:
    st.error("Veri klasöründe pres DASHBOARD dosyası ('Temiz veri' sayfası) bulunamadı.")
    st.stop()
kayit, kaynak_adi, degisme, mod = veri_
kaynak_notu(kaynak_adi, degisme, mod)
kayit = kayit[kayit["kalip"].notna()].copy()
kayit["kalip"] = kayit["kalip"].astype(int)
# Aynı müşterinin farklı yazılışları birleştirilir (tablo: musteriler.py)
kayit["musteri"] = musteriler.birlestir(kayit["musteri"])


def ozetle(t):
    """Bir baskı kümesinin göstergeleri."""
    brut, net = t["brut_kg"].sum(), t["net_kg"].sum()
    saat = t["sure_dk"].sum() / 60
    a = t["biyet_adet"].where(t["piston"].notna(), 0)
    biyet = t["biyet_adet"].sum()
    return {
        "net_kg": net, "brut_kg": brut, "saat": saat, "biyet": biyet,
        "fire": (brut - net) / brut if brut else None,
        "kg_saat": net / saat if saat else None,
        "piston": (t["piston"].fillna(0) * a).sum() / a.sum() if a.sum() else None,
        "kg_biyet": net / biyet if biyet else None,
        "gramaj": t["gramaj"].mean() if t["gramaj"].notna().any() else None,
        "gun": t["gun"].nunique(), "baski": len(t),
    }


def kalip_tablosu(t):
    """Her kalıp için dönem toplamları (arama listesi ve sıralama)."""
    t = t.assign(_p=t["piston"].fillna(0) * t["biyet_adet"].where(t["piston"].notna(), 0),
                 _a=t["biyet_adet"].where(t["piston"].notna(), 0))
    g = t.groupby("kalip").agg(
        net_kg=("net_kg", "sum"), brut_kg=("brut_kg", "sum"), sure_dk=("sure_dk", "sum"),
        biyet=("biyet_adet", "sum"), _p=("_p", "sum"), _a=("_a", "sum"),
        gun=("gun", "nunique"), son=("tarih", "max"),
        pres=("pres", lambda s: " · ".join(sorted(s.dropna().unique()))),
        musteri=("musteri", lambda s: s.dropna().mode().iat[0] if s.notna().any() else "")).reset_index()
    g["fire"] = ((g["brut_kg"] - g["net_kg"]) / g["brut_kg"] * 100).where(g["brut_kg"] > 0)
    g["kg_saat"] = (g["net_kg"] / (g["sure_dk"] / 60)).where(g["sure_dk"] > 0)
    g["piston"] = (g["_p"] / g["_a"]).where(g["_a"] > 0)
    return g.sort_values(["net_kg", "kalip"], ascending=[False, True]).reset_index(drop=True)


# ---------------------------------------------------------------------
# Filtreler: pres + tarih aralığı + kalıp
# ---------------------------------------------------------------------
f1, f2, f_donem = st.columns([1, 1.6, 3])
presler = f1.multiselect("Pres", ['6"', '8"'], default=['6"', '8"'])
# Ortak kayıtlar ('ASC / BG PLAST') her iki müşterinin listesinde de sayılır
_tek = kayit.assign(m=kayit["musteri"].map(musteriler.ayir)).explode("m")
secilen_musteri = f2.multiselect(
    "Müşteri", _tek.groupby("m")["net_kg"].sum().sort_values(ascending=False).index.tolist(),
    placeholder="Tümü")
with f_donem:
    bas, bit = donem_sec(kayit["tarih"].min().date(), kayit["tarih"].max().date())

kayit = kayit[kayit["pres"].isin(presler)]
if secilen_musteri:
    kayit = kayit[kayit["musteri"].map(lambda m: bool(set(musteriler.ayir(m)) & set(secilen_musteri)))]
o = kayit[(kayit["tarih"].dt.date >= bas) & (kayit["tarih"].dt.date <= bit)]
if o.empty:
    st.warning("Seçilen pres, müşteri ve tarih aralığında baskı kaydı yok.")
    st.stop()
liste = kalip_tablosu(o)

# Tablodan satır seçilirse o kalıp açılır; arama kutusu önceliklidir
tablo_secim = st.session_state.get("kalip_tablo", {}).get("selection", {}).get("rows", [])
# Seçenekler dönemden bağımsız (dönem değişince seçili kalıp kaybolmasın)
donem_kg = liste.set_index("kalip")["net_kg"]
aranan = st.selectbox(
    "Kalıp no", sorted(kayit["kalip"].unique().tolist()), index=None, key="kalip_ara",
    placeholder="Kalıp numarasını yazın ya da alttaki listeden seçin",
    format_func=lambda k: f"{k}  ·  {sayi(donem_kg[k])} kg" if k in donem_kg
    else f"{k}  ·  bu dönemde baskı yok")
secili = aranan if aranan is not None else (
    int(liste["kalip"].iat[tablo_secim[0]]) if tablo_secim and tablo_secim[0] < len(liste) else None)

genel = ozetle(o)

# ---------------------------------------------------------------------
# Seçili kalıbın raporu
# ---------------------------------------------------------------------
if secili is not None:
    t = o[o["kalip"] == secili]
    if t.empty:
        son = kayit.loc[kayit["kalip"] == secili, "tarih"].max()
        st.info(f"Kalıp {secili} seçilen dönemde basılmamış. Son baskı: {son:%d.%m.%Y}. "
                "Dönemi genişletin (ör. 'Tüm kayıtlar').")
        st.stop()
    onceki = kayit[(kayit["kalip"] == secili) & (kayit["tarih"].dt.date < bas)]
    g = ozetle(t)
    p = ozetle(onceki) if not onceki.empty else None

    def fark(anahtar, carpan=1.0, ondalik=0, birim=""):
        if p is None or p[anahtar] is None or g[anahtar] is None:
            return None
        return f"{sayi((g[anahtar] - p[anahtar]) * carpan, ondalik)}{birim}"

    musteri = ", ".join(t["musteri"].dropna().value_counts().index[:3])
    alasim = ", ".join(t["alasim"].dropna().value_counts().index[:2])
    st.markdown(f"#### Kalıp {secili}  ·  {bas:%d.%m.%Y} – {bit:%d.%m.%Y}  ·  "
                f"{g['gun']} baskı günü  ·  {' · '.join(sorted(t['pres'].unique()))}")
    st.caption(" · ".join(x for x in (f"Müşteri: {musteri}" if musteri else "",
                                       f"Alaşım: {alasim}" if alasim else "",
                                       f"İlk baskı: {kayit.loc[kayit['kalip'] == secili, 'tarih'].min():%d.%m.%Y}")
                          if x))
    if p is not None:
        st.caption(f"Oklar bu kalıbın {bas:%d.%m.%Y} öncesi tüm baskılarıyla "
                   f"({sayi(p['baski'])} baskı, {sayi(p['net_kg'])} kg) kıyastır. "
                   f"Aynı dönemde tüm kalıplar: fire %{sayi((genel['fire'] or 0) * 100, 1)}, "
                   f"{sayi(genel['kg_saat'])} kg/saat, {sayi(genel['piston'], 1)} mm/s.")

    k = st.columns(4)
    k[0].metric("Net Üretim (kg)", sayi(g["net_kg"]), help=f"Brüt {sayi(g['brut_kg'])} kg")
    k[1].metric("Fire (%)", sayi(g["fire"] * 100, 1) if g["fire"] is not None else "–",
                fark("fire", 100, 1, " puan"), delta_color="inverse",
                help="(Brüt kg − net kg) ÷ brüt kg")
    k[2].metric("Saatlik Üretim (kg/saat)", sayi(g["kg_saat"]), fark("kg_saat"),
                help="Net kg ÷ baskı süresi")
    k[3].metric("Baskı Hızı (mm/s)", sayi(g["piston"], 1), fark("piston", 1, 1),
                help="Piston hızı, biyet adediyle ağırlıklı ortalama")
    k = st.columns(4)
    k[0].metric("Biyet (adet)", sayi(g["biyet"]))
    k[1].metric("Baskı Süresi (saat)", sayi(g["saat"], 1))
    k[2].metric("Biyet Başına Net (kg)", sayi(g["kg_biyet"], 1), fark("kg_biyet", 1, 1))
    k[3].metric("Ort. Gramaj (kg/m)", sayi(g["gramaj"], 3))

    sekme = st.tabs(["📈 Trend", "👷 Operatör / Pres", "📋 Baskı Detayı"])
    with sekme[0]:
        gun_sayisi = t["gun"].nunique()
        tr = t.assign(donem=t["gun"] if gun_sayisi <= 40 else t["ay"])
        d = tr.groupby(["donem", "pres"]).apply(lambda x: pd.Series(ozetle(x)),
                                                include_groups=False).reset_index()
        d["etiket"] = (d["donem"].dt.strftime("%d.%m.%y") if gun_sayisi <= 40
                       else d["donem"].map(ay_etiketi))
        d["fire_yuzde"] = d["fire"].astype(float) * 100
        sira = list(d.sort_values("donem")["etiket"].unique())
        x = alt.X("etiket:O", title=None, sort=sira,
                  axis=alt.Axis(labelAngle=0 if len(sira) <= 14 else -45))
        renk = alt.Color("pres:N", scale=PRES_RENK, title="Pres", legend=alt.Legend(orient="top"))
        ipucu = [alt.Tooltip("etiket:N", title="Dönem"), alt.Tooltip("pres:N", title="Pres"),
                 alt.Tooltip("net_kg:Q", title="Net kg", format=",.0f"),
                 alt.Tooltip("fire_yuzde:Q", title="Fire %", format=".1f"),
                 alt.Tooltip("kg_saat:Q", title="kg/saat", format=",.0f"),
                 alt.Tooltip("piston:Q", title="Baskı hızı mm/s", format=".1f"),
                 alt.Tooltip("biyet:Q", title="Biyet")]
        st.subheader("Net üretim (kg) · " + ("baskı günü" if gun_sayisi <= 40 else "ay") + " bazında")
        st.altair_chart(alt.Chart(d).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                              stroke="#121b2d", strokeWidth=2)
                        .encode(x=x, y=alt.Y("net_kg:Q", title="kg", stack=True), color=renk,
                                tooltip=ipucu).properties(height=250), use_container_width=True)
        cizgi = alt.Chart(d).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60))
        for kolon, (alan, baslik) in zip(st.columns(3), [("fire_yuzde", "Fire %"),
                                                         ("kg_saat", "Saatlik üretim (kg/saat)"),
                                                         ("piston", "Baskı hızı (mm/s)")]):
            with kolon:
                st.subheader(baslik)
                st.altair_chart(cizgi.encode(x=x, y=alt.Y(f"{alan}:Q", title=None), color=renk,
                                             tooltip=ipucu).properties(height=230),
                                use_container_width=True)
    with sekme[1]:
        for anahtar, ad in (("operator", "Operatör"), ("pres", "Pres")):
            gr = (t.groupby(anahtar).apply(lambda x: pd.Series(ozetle(x)), include_groups=False)
                  .reset_index().sort_values("net_kg", ascending=False))
            st.subheader(f"{ad} bazında")
            st.dataframe(pd.DataFrame({
                ad: gr[anahtar], "Net (kg)": gr["net_kg"].round(0),
                "Fire %": (gr["fire"].astype(float) * 100).round(1),
                "kg/saat": gr["kg_saat"].astype(float).round(0),
                "Baskı hızı (mm/s)": gr["piston"].astype(float).round(1),
                "Biyet": gr["biyet"], "Baskı günü": gr["gun"]}),
                hide_index=True, use_container_width=True)
    with sekme[2]:
        dt_ = t.sort_values(["tarih", "vardiya"])
        cikti = pd.DataFrame({
            "Tarih": dt_["tarih"].dt.strftime("%d.%m.%Y"), "Vardiya": dt_["vardiya"],
            "Pres": dt_["pres"], "Operatör": dt_["operator"], "Biyet": dt_["biyet_adet"],
            "Brüt (kg)": dt_["brut_kg"].round(1), "Net (kg)": dt_["net_kg"].round(1),
            "Fire %": ((dt_["brut_kg"] - dt_["net_kg"]) / dt_["brut_kg"] * 100)
            .where(dt_["brut_kg"] > 0).round(1),
            "kg/saat": (dt_["net_kg"] / (dt_["sure_dk"] / 60)).where(dt_["sure_dk"] > 0).round(0),
            "Baskı hızı (mm/s)": dt_["piston"], "Süre (dk)": dt_["sure_dk"],
            "Kalıp °C": dt_["kalip_sic"], "Biyet °C": dt_["biyet_sic"],
            "Biyet boyu (mm)": dt_["biyet_boyu"], "Gramaj (kg/m)": dt_["gramaj"],
            "Alaşım": dt_["alasim"], "Yüzey": dt_["yuzey"], "Müşteri": dt_["musteri"],
            "Açıklama": dt_["aciklama"]})
        st.dataframe(cikti, hide_index=True, use_container_width=True)
        st.download_button("⬇️ CSV indir", cikti.to_csv(index=False, sep=";", decimal=",")
                           .encode("utf-8-sig"),
                           file_name=f"kalip_{secili}_{bas:%Y%m%d}_{bit:%Y%m%d}.csv",
                           mime="text/csv")
    st.divider()
else:
    k = st.columns(4)
    k[0].metric("Çalışan Kalıp", sayi(len(liste)))
    k[1].metric("Net Üretim (ton)", sayi(genel["net_kg"] / 1000, 1))
    k[2].metric("Fire (%)", sayi((genel["fire"] or 0) * 100, 1))
    k[3].metric("Baskı Hızı (mm/s)", sayi(genel["piston"], 1))

# ---------------------------------------------------------------------
# Dönemde çalışan tüm kalıplar (satıra tıklayınca kalıp açılır)
# ---------------------------------------------------------------------
st.subheader(f"Dönemde çalışan kalıplar ({len(liste)})")
st.caption("Bir satıra tıklayınca o kalıbın raporu açılır. Sütun başlığına tıklayarak sıralayabilirsiniz.")
st.dataframe(pd.DataFrame({
    "Kalıp": liste["kalip"], "Pres": liste["pres"], "Müşteri": liste["musteri"],
    "Net (kg)": liste["net_kg"].round(0), "Fire %": liste["fire"].round(1),
    "kg/saat": liste["kg_saat"].round(0), "Baskı hızı (mm/s)": liste["piston"].round(1),
    "Biyet": liste["biyet"], "Baskı günü": liste["gun"],
    "Son baskı": liste["son"].dt.strftime("%d.%m.%Y")}),
    hide_index=True, use_container_width=True, key="kalip_tablo",
    on_select="rerun", selection_mode="single-row")
