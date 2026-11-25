"""İK: norm kadro, yıllık izin bakiyesi ve profil yoklama (devamsızlık).

Kaynaklar (ALBOND RAPORLAR, her biri adındaki kelimeyle bulunan en yeni dosya):
  GÜNCEL NORM KADRO  -> 'PROFİL İMALAT NORM KADRO' ve 'PROFİL İMALAT KADRO' sayfaları
  YILLIK İZİN MEVCUT -> kişi başı hak / kullanılan / kalan gün
  PROFİL YOKLAMA     -> ay sayfaları, kişi × gün devamsızlık saati (8 saat = 1 gün)
Devamsızlık oranı = devamsızlık saati ÷ (kişi sayısı × iş günü × 8).
İş günü: Pazar hariç takvim günleri (bu ay için bugüne kadar); resmi tatiller düşülmez.
"""

import altair as alt
import pandas as pd
import streamlit as st

from ortak import (PALET, SONUK, TEK_RENK, ay_etiketi, kaynak_notu, rapor_verisi,
                   sayi)
from raporlar import izin_turleri

EKSEN = alt.Axis(labelExpr="replace(datum.label, ',', '.')")
GUN_SAAT = 8

st.title("👥 İK · Kadro, İzin, Yoklama")
st.caption("🔒 Kişisel veri içerir. Bulut panosu şifre arkasındadır; doğum tarihi alınmaz.")

norm_v, kadro_v = rapor_verisi("ik_norm"), rapor_verisi("ik_kadro")
izin_v, yok_v = rapor_verisi("ik_izin"), rapor_verisi("ik_yoklama")

sekme = st.tabs(["Kadro", "Yıllık İzin", "Yoklama"])


def yok_mesaji(dosya):
    st.warning(f"Veri klasöründe '{dosya}' dosyası bulunamadı.")


# ---------------------------------------------------------------- Kadro
with sekme[0]:
    if norm_v is None or norm_v[0].empty:
        yok_mesaji("GÜNCEL NORM KADRO")
    else:
        norm, ad_, degisme, mod = norm_v
        kaynak_notu(ad_, degisme, mod)
        n, m = norm["norm"].sum(), norm["mevcut"].sum()
        acik = norm["ihtiyac"].clip(lower=0).sum()
        fazla = (-norm["ihtiyac"].clip(upper=0)).sum()
        k = st.columns(4)
        k[0].metric("Norm kadro", sayi(n))
        k[1].metric("Mevcut", sayi(m))
        k[2].metric("Açık pozisyon", sayi(acik),
                    help="Norm − mevcut, yalnız eksik olan görevler" +
                         (f" (normu aşan {sayi(fazla)} kişi ayrıca)" if fazla else ""))
        k[3].metric("Doluluk", f"%{sayi(m / n * 100, 1)}" if n else "–")

        b = (norm.groupby("bolum", sort=False)[["norm", "mevcut"]].sum().reset_index())
        b["doluluk"] = b["mevcut"] / b["norm"]
        uzun = b.melt(id_vars=["bolum", "doluluk"], value_vars=["norm", "mevcut"],
                      var_name="tür", value_name="kişi")
        uzun["tür"] = uzun["tür"].map({"norm": "Norm", "mevcut": "Mevcut"})
        st.subheader("Bölüm bazında norm ve mevcut")
        st.altair_chart(
            alt.Chart(uzun).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("bolum:N", title=None, sort=list(b["bolum"]),
                        axis=alt.Axis(labelAngle=0)),
                xOffset=alt.XOffset("tür:N", sort=["Norm", "Mevcut"]),
                y=alt.Y("kişi:Q", title="Kişi", axis=EKSEN),
                color=alt.Color("tür:N", title=None, legend=alt.Legend(orient="top"),
                                scale=alt.Scale(domain=["Norm", "Mevcut"],
                                                range=[SONUK, TEK_RENK])),
                tooltip=[alt.Tooltip("bolum:N", title="Bölüm"), alt.Tooltip("tür:N"),
                         alt.Tooltip("kişi:Q"),
                         alt.Tooltip("doluluk:Q", title="Doluluk", format=".0%")])
            .properties(height=280), width="stretch")

        st.subheader("Görev bazında ihtiyaç")
        g = norm.rename(columns={"bolum": "Bölüm", "vardiya": "Vardiya", "gorev": "Görev",
                                 "norm": "Norm", "mevcut": "Mevcut", "ihtiyac": "İhtiyaç"})
        g = g.sort_values(["İhtiyaç", "Bölüm"], ascending=[False, True])
        st.dataframe(g, hide_index=True, width="stretch",
                     column_config={"İhtiyaç": st.column_config.NumberColumn(
                         help="Eksi değer: normun üstünde personel")})

    if kadro_v is not None and not kadro_v[0].empty:
        kadro = kadro_v[0].copy()
        bugun = pd.Timestamp.today().normalize()
        kadro["Kıdem (yıl)"] = ((bugun - kadro["giris"]).dt.days / 365.25).round(1)
        st.subheader(f"Personel listesi · {len(kadro)} kişi")
        bolumler = ["Tümü"] + sorted(kadro["bolum"].dropna().unique())
        sec = st.selectbox("Bölüm", bolumler, key="ik_kadro_bolum")
        if sec != "Tümü":
            kadro = kadro[kadro["bolum"] == sec]
        c1, c2 = st.columns([1.6, 1])
        c1.dataframe(kadro.rename(columns={"bolum": "Bölüm", "ad": "Ad Soyad",
                                           "pozisyon": "Pozisyon", "giris": "İşe giriş"}),
                     hide_index=True, width="stretch",
                     column_config={"İşe giriş": st.column_config.DateColumn(format="DD.MM.YYYY")})
        kd = kadro["Kıdem (yıl)"]
        bant = pd.cut(kd, [-0.01, 1, 2, 3, 5, 100],
                      labels=["< 1 yıl", "1–2 yıl", "2–3 yıl", "3–5 yıl", "5+ yıl"])
        bd = bant.value_counts(sort=False).rename_axis("Kıdem").reset_index(name="Kişi")
        c2.markdown(f"**Kıdem dağılımı** · ortalama {sayi(kd.mean(), 1)} yıl"
                    + (f" · {kd.isna().sum()} kişide giriş tarihi yok" if kd.isna().any() else ""))
        c2.altair_chart(
            alt.Chart(bd).mark_bar(color=TEK_RENK, cornerRadiusEnd=3).encode(
                y=alt.Y("Kıdem:N", sort=list(bd["Kıdem"]), title=None),
                x=alt.X("Kişi:Q", axis=EKSEN), tooltip=["Kıdem", "Kişi"])
            .properties(height=220), width="stretch")


# ---------------------------------------------------------------- Yıllık izin
with sekme[1]:
    if izin_v is None or izin_v[0].empty:
        yok_mesaji("YILLIK İZİN MEVCUT")
    else:
        izin, ad_, degisme, mod = izin_v
        kaynak_notu(ad_, degisme, mod)
        hak_sut = sorted(c for c in izin.columns if c.startswith("hak_"))
        k = st.columns(4)
        k[0].metric("Kişi", sayi(len(izin)))
        k[1].metric("Toplam kalan izin", f"{sayi(izin['kalan'].sum())} gün")
        k[2].metric("Kullanılan", f"{sayi(izin['kullanilan'].sum())} gün")
        eksi = izin[izin["kalan"] < 0]
        k[3].metric("Eksi bakiyeli", sayi(len(eksi)),
                    help="Hakkından fazla izin kullanmış (avans izin) kişiler")

        st.subheader("Kişi başı kalan izin (gün)")
        s = izin.sort_values("kalan", ascending=False)
        s = s.assign(durum=s["kalan"].map(lambda v: "Eksi" if v < 0 else
                                          ("Yüksek (≥ 14)" if v >= 14 else "Normal")))
        st.altair_chart(
            alt.Chart(s).mark_bar(cornerRadiusEnd=3).encode(
                y=alt.Y("ad:N", sort=list(s["ad"]), title=None),
                x=alt.X("kalan:Q", title="Kalan gün", axis=EKSEN),
                color=alt.Color("durum:N", title=None, legend=alt.Legend(orient="top"),
                                scale=alt.Scale(domain=["Normal", "Yüksek (≥ 14)", "Eksi"],
                                                range=[TEK_RENK, PALET[3], PALET[1]])),
                tooltip=[alt.Tooltip("ad:N", title="Ad"), alt.Tooltip("kalan:Q", title="Kalan"),
                         alt.Tooltip("kullanilan:Q", title="Kullanılan")])
            .properties(height=max(220, 24 * len(s))), width="stretch")
        st.caption("Yüksek bakiye (≥ 14 gün) yıl sonu / yaz planlamasında öne alınmalı; eksi "
                   "bakiye avans izindir.")

        tablo = izin.rename(columns={"sicil": "Sicil", "ad": "Ad Soyad", "bolum": "Bölüm",
                                     "giris": "Topluluk giriş", "hakedis": "Hak ediş",
                                     "kullanilan": "Kullanılan", "kalan": "Kalan",
                                     **{c: f"{c[4:]} hakkı" for c in hak_sut}})
        st.dataframe(tablo, hide_index=True, width="stretch", column_config={
            "Topluluk giriş": st.column_config.DateColumn(format="DD.MM.YYYY"),
            "Hak ediş": st.column_config.DateColumn(format="DD.MM.YYYY"),
            "Sicil": st.column_config.NumberColumn(format="%d")})


# ---------------------------------------------------------------- Yoklama
def is_gunu(ay, bugun):
    """Ayın Pazar hariç gün sayısı (bu ay için bugüne kadar)."""
    son = min(ay + pd.offsets.MonthEnd(0), bugun)
    if son < ay:
        return 0
    gunler = pd.date_range(ay, son)
    return int((gunler.dayofweek != 6).sum())


@st.cache_data(show_spinner=False)
def aylik_yoklama(yok, bugun):
    kisi = yok[yok["tip"] == "kisi"]
    gun = yok[yok["tip"] == "gun"]
    a = kisi.groupby("ay").size().rename("kisi").to_frame()
    a["saat"] = gun.groupby("ay")["saat"].sum()
    a["saat"] = a["saat"].fillna(0)
    a = a.reset_index()
    a["is_gunu"] = a["ay"].map(lambda t: is_gunu(t, bugun))
    a["kapasite"] = a["kisi"] * a["is_gunu"] * GUN_SAAT
    a["oran"] = (a["saat"] / a["kapasite"]).where(a["kapasite"] > 0)
    a["gun"] = a["saat"] / GUN_SAAT
    a["kisi_basi_gun"] = a["gun"] / a["kisi"]
    a["veri_var"] = a["saat"] > 0
    return a


with sekme[2]:
    if yok_v is None or yok_v[0].empty:
        yok_mesaji("PROFİL YOKLAMA")
        st.stop()
    yok, ad_, degisme, mod = yok_v
    kaynak_notu(ad_, degisme, mod)
    bugun = pd.Timestamp.today().normalize()
    a_hepsi = aylik_yoklama(yok, bugun)
    bos = a_hepsi[~a_hepsi["veri_var"] & (a_hepsi["ay"] <= bugun)]
    a_hepsi = a_hepsi[a_hepsi["veri_var"]].reset_index(drop=True)
    if a_hepsi.empty:
        st.info("Yoklama sayfalarında henüz devamsızlık girilmemiş.")
        st.stop()
    aylar = list(a_hepsi["ay"])
    if len(aylar) > 1:
        varsayilan = aylar[-12] if len(aylar) > 12 else aylar[0]
        bas, bit = st.select_slider("Ay aralığı", options=aylar, value=(varsayilan, aylar[-1]),
                                    format_func=ay_etiketi, key="ik_ay")
    else:
        bas = bit = aylar[0]
    a = a_hepsi[a_hepsi["ay"].between(bas, bit)]
    son = a_hepsi[a_hepsi["ay"] == bit].iloc[0]
    onceki = a_hepsi[a_hepsi["ay"] < bit].tail(1)

    oran = a["saat"].sum() / a["kapasite"].sum() if a["kapasite"].sum() else None
    k = st.columns(4)
    k[0].metric("Devamsızlık oranı", f"%{sayi(oran * 100, 1)}" if oran is not None else "–",
                help="Devamsızlık saati ÷ (kişi × Pazar hariç iş günü × 8)")
    k[1].metric("Devamsızlık", f"{sayi(a['gun'].sum(), 1)} gün",
                help=f"{sayi(a['saat'].sum(), 1)} saat")
    k[2].metric("Kişi başı / ay", f"{sayi(a['gun'].sum() / a['kisi'].sum(), 2)} gün")
    fark = (None if onceki.empty or pd.isna(onceki.iloc[0]["oran"]) or pd.isna(son["oran"])
            else f"{sayi((son['oran'] - onceki.iloc[0]['oran']) * 100, 1)} puan")
    k[3].metric(f"{ay_etiketi(bit)} oranı",
                f"%{sayi(son['oran'] * 100, 1)}" if pd.notna(son["oran"]) else "–",
                delta=fark, delta_color="inverse")
    if not bos.empty:
        st.caption("⚠️ Devamsızlık girilmemiş ay(lar) hesaba katılmadı: "
                   + ", ".join(ay_etiketi(t) for t in bos["ay"]))

    st.subheader("Aylık devamsızlık oranı")
    ac = a.assign(etiket=a["ay"].map(ay_etiketi), yuzde=a["oran"] * 100)
    ortalama = alt.Chart(pd.DataFrame({"y": [oran * 100 if oran else 0]})).mark_rule(
        strokeDash=[5, 4], color=SONUK).encode(y="y:Q")
    st.altair_chart(
        (alt.Chart(ac).mark_bar(color=TEK_RENK, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
         .encode(x=alt.X("etiket:N", sort=list(ac["etiket"]), title=None,
                         axis=alt.Axis(labelAngle=0)),
                 y=alt.Y("yuzde:Q", title="Devamsızlık %", axis=EKSEN),
                 tooltip=[alt.Tooltip("etiket:N", title="Ay"),
                          alt.Tooltip("yuzde:Q", title="Oran %", format=".1f"),
                          alt.Tooltip("gun:Q", title="Gün", format=".1f"),
                          alt.Tooltip("kisi:Q", title="Kişi"),
                          alt.Tooltip("is_gunu:Q", title="İş günü")])
         + ortalama).properties(height=280), width="stretch")
    st.caption("Kesikli çizgi: seçili dönem ortalaması. Resmi tatiller iş gününden düşülmez; "
               "bu ay bugüne kadarki günlerle hesaplanır.")

    gunler = yok[(yok["tip"] == "gun") & yok["ay"].between(bas, bit)]
    kisiler = yok[(yok["tip"] == "kisi") & yok["ay"].between(bas, bit)]
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("En çok devamsızlık (kişi)")
        kb = (gunler.groupby("ad").agg(saat=("saat", "sum"), kez=("gun", "nunique"))
              .reset_index())
        kb["gün"] = kb["saat"] / GUN_SAAT
        kb = kb.sort_values("saat", ascending=False).head(15)
        st.altair_chart(
            alt.Chart(kb).mark_bar(color=PALET[1], cornerRadiusEnd=3).encode(
                y=alt.Y("ad:N", sort=list(kb["ad"]), title=None),
                x=alt.X("gün:Q", title="Gün", axis=EKSEN),
                tooltip=[alt.Tooltip("ad:N", title="Ad"),
                         alt.Tooltip("gün:Q", title="Gün", format=".1f"),
                         alt.Tooltip("kez:Q", title="Farklı gün sayısı")])
            .properties(height=max(220, 24 * len(kb))), width="stretch")
    with c2:
        st.subheader("Haftanın günlerine göre")
        hg = gunler.assign(g=gunler["gun"].dt.dayofweek)
        hg = hg.groupby("g")["saat"].sum().reindex(range(7), fill_value=0).reset_index()
        hg["Gün"] = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
        hg["gün"] = hg["saat"] / GUN_SAAT
        st.altair_chart(
            alt.Chart(hg).mark_bar(color=TEK_RENK, cornerRadiusTopLeft=3,
                                   cornerRadiusTopRight=3).encode(
                x=alt.X("Gün:N", sort=list(hg["Gün"]), title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("gün:Q", title="Gün", axis=EKSEN),
                tooltip=["Gün", alt.Tooltip("gün:Q", title="Gün", format=".1f")])
            .properties(height=240), width="stretch")
        st.caption("Cumartesi / Pazartesi yığılması plansız devamsızlık işaretidir.")

        st.subheader("Açıklamalara göre izin türü")
        turler = [t for ac_ in kisiler["aciklama"].dropna() for t in izin_turleri(ac_)]
        if turler:
            tt = pd.Series(turler).value_counts().rename_axis("Tür").reset_index(name="Kayıt")
            st.altair_chart(
                alt.Chart(tt).mark_bar(color=PALET[2], cornerRadiusEnd=3).encode(
                    y=alt.Y("Tür:N", sort=list(tt["Tür"]), title=None),
                    x=alt.X("Kayıt:Q", axis=EKSEN), tooltip=["Tür", "Kayıt"])
                .properties(height=200), width="stretch")
            st.caption("Kişi-ay açıklamalarında geçen türler (kelime araması); açıklama "
                       "yazılmayan devamsızlıklar burada görünmez.")
        else:
            st.caption("Seçili dönemde açıklama yok.")

    st.subheader(f"{ay_etiketi(bit)} · kişi × gün (saat)")
    ay_g = yok[(yok["ay"] == bit) & (yok["tip"] == "gun")]
    ay_k = yok[(yok["ay"] == bit) & (yok["tip"] == "kisi")]
    tablo = (ay_g.assign(g=ay_g["gun"].dt.day)
             .pivot_table(index="ad", columns="g", values="saat", aggfunc="sum"))
    tablo = tablo.reindex(columns=range(1, (bit + pd.offsets.MonthEnd(0)).day + 1))
    tablo.columns = [str(c) for c in tablo.columns]
    tablo.insert(0, "Toplam saat", tablo.sum(axis=1))
    tablo = (ay_k.set_index("ad")[["aciklama"]].join(tablo, how="left")
             .sort_values("Toplam saat", ascending=False, na_position="last"))
    tablo = tablo[["Toplam saat"] + [c for c in tablo.columns if c not in ("Toplam saat", "aciklama")]
                  + ["aciklama"]].rename(columns={"aciklama": "Açıklama"})
    st.dataframe(tablo.reset_index().rename(columns={"ad": "Ad Soyad"}), hide_index=True,
                 width="stretch")
    st.download_button("⬇️ CSV indir",
                       tablo.to_csv(sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=f"yoklama_{bit:%Y_%m}.csv", mime="text/csv")
