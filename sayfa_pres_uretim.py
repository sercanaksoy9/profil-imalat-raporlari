"""2026 Pres Üretim Raporu sayfası (tarih aralıklı).

Seçilen tarih aralığına göre detaylı rapor verir. Günlük kayıtlar ay
sayfalarından gelir; günlük kaydı olmayan aylar (Ocak–Mayıs) 'ÖZET 6"' ve
'ÖZET 8"' sayfalarındaki ay toplamlarıyla tamamlanır. Böyle bir ay aralığa
kısmen de girse tam ay olarak eklenir (gün gün bölünemez), ekranda not düşülür.
"""
import datetime as dt

import altair as alt
import pandas as pd
import streamlit as st

from ortak import PALET, PRES_RENK, TEK_RENK, ay_etiketi, kaynak_notu, rapor_verisi, sayi

DURUS_ADI = {"ariza": "Arıza", "isletme": "İşletme", "elektrik": "Elektrik Kesintisi",
             "planli": "Planlı Duruş", "diger": "Diğer Duruş", "iftar": "İftar Duruşu"}
TOPLANAN = ["hammadde", "testere", "brut_dk", "net_dk", "durus_dk", "setup", "deneme",
            "calismayan_kalip", "biyet_adet", *DURUS_ADI]
GUN_ADI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

st.title("🏭 2026 Pres Üretim Raporu")

ozet_veri = rapor_verisi("pres_rapor_ozet")
if ozet_veri is None or ozet_veri[0].empty:
    st.error("Veri klasöründe '2026 PRES ÜRETİM RAPORU' dosyası bulunamadı.")
    st.stop()
ozet, kaynak_adi, degisme, mod = ozet_veri
gunluk_veri = rapor_verisi("pres_rapor_gunluk")
gunluk = gunluk_veri[0] if gunluk_veri else pd.DataFrame()
kaynak_notu(kaynak_adi, degisme, mod)


# ---------------------------------------------------------------------
# Günlük + aylık kayıtları tek tabloda birleştir
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def kayitlari_birlestir(ozet, gunluk):
    parcalar = []
    gunlu_aylar = set()
    if not gunluk.empty:
        g = gunluk.copy()
        g["brut_dk"] = g["calisma_dk"]
        g["net_dk"] = (g["calisma_dk"] - g["durus_dk"]).clip(lower=0)
        g["iftar"] = 0.0
        g["bitis"] = g["tarih"]
        g["tur"] = "gün"
        gunlu_aylar = set(g["ay"])
        parcalar.append(g)
    a = ozet[~ozet["ay"].isin(gunlu_aylar)].copy()
    if not a.empty:
        a["tarih"] = a["ay"]
        a["bitis"] = a["ay"] + pd.offsets.MonthEnd(0)
        a["tur"] = "ay"
        parcalar.append(a)
    k = pd.concat(parcalar, ignore_index=True)
    k[TOPLANAN] = k[TOPLANAN].fillna(0)
    k["ay"] = k["tarih"].dt.to_period("M").dt.to_timestamp()
    return k[["tarih", "bitis", "ay", "pres", "tur", "biyet_boyu", "hiz", *TOPLANAN]]


kayit = kayitlari_birlestir(ozet, gunluk)
ilk_gun = kayit["tarih"].min().date()
# Son gün: en son günlük kayıt (yoksa son ayın sonu)
son_gun = (kayit.loc[kayit["tur"] == "gün", "tarih"].max() if (kayit["tur"] == "gün").any()
           else kayit["bitis"].max()).date()


def ozetle(t):
    """Bir kayıt kümesinin toplam göstergeleri."""
    s = t[TOPLANAN].sum()
    biyet_a = t["biyet_adet"].where(t["biyet_boyu"].notna() & t["hiz"].notna(), 0)
    s["biyet_boyu"] = (t["biyet_boyu"] * biyet_a).sum() / biyet_a.sum() if biyet_a.sum() else None
    s["hiz"] = (t["hiz"] * biyet_a).sum() / biyet_a.sum() if biyet_a.sum() else None
    s["fire"] = (s["hammadde"] - s["testere"]) / s["hammadde"] if s["hammadde"] else None
    s["net_saat"], s["brut_saat"], s["durus_saat"] = s["net_dk"] / 60, s["brut_dk"] / 60, s["durus_dk"] / 60
    s["kg_saat"] = s["testere"] / s["net_saat"] if s["net_saat"] else None
    s["verim"] = s["net_dk"] / s["brut_dk"] if s["brut_dk"] else None
    s["uretim_gunu"] = int(t.loc[t["tur"] == "gün", "tarih"].nunique())
    return s


def aralik_sec(bas, bit, presler):
    m = kayit["pres"].isin(presler)
    gun = (kayit["tur"] == "gün") & (kayit["tarih"].dt.date >= bas) & (kayit["tarih"].dt.date <= bit)
    ay = ((kayit["tur"] == "ay") & (kayit["tarih"].dt.date <= bit)
          & (kayit["bitis"].dt.date >= bas))
    return kayit[m & (gun | ay)].copy()


# ---------------------------------------------------------------------
# Filtreler: pres + tarih aralığı
# ---------------------------------------------------------------------
bugun = son_gun
HAZIR = {
    "Bu ay": (bugun.replace(day=1), bugun),
    "Geçen ay": ((bugun.replace(day=1) - dt.timedelta(days=1)).replace(day=1),
                 bugun.replace(day=1) - dt.timedelta(days=1)),
    "Son 7 gün": (bugun - dt.timedelta(days=6), bugun),
    "Son 30 gün": (bugun - dt.timedelta(days=29), bugun),
    "Son 3 ay": ((pd.Timestamp(bugun) - pd.DateOffset(months=3)).date() + dt.timedelta(days=1), bugun),
    "Yılbaşından beri": (ilk_gun, bugun),
    "Özel aralık": None,
}
f1, f2, f3 = st.columns([1, 1.3, 1.7])
presler = f1.multiselect("Pres", ['6"', '8"'], default=['6"', '8"'])
hazir = f2.selectbox("Dönem", list(HAZIR), index=list(HAZIR).index("Yılbaşından beri"))
if HAZIR[hazir] is None:
    secim = f3.date_input("Tarih aralığı", value=(bugun.replace(day=1), bugun),
                          min_value=ilk_gun, max_value=bugun, format="DD.MM.YYYY")
    if not isinstance(secim, (tuple, list)) or len(secim) < 2:
        st.info("Bitiş tarihini de seçin.")
        st.stop()
    bas, bit = secim[0], secim[1]
else:
    bas, bit = HAZIR[hazir]
    bas = max(bas, ilk_gun)
    f3.text_input("Tarih aralığı", f"{bas:%d.%m.%Y} – {bit:%d.%m.%Y}", disabled=True)

o = aralik_sec(bas, bit, presler)
if o.empty:
    st.warning("Seçilen pres ve tarih aralığında kayıt yok.")
    st.stop()

aylik_kisim = o[o["tur"] == "ay"]
if not aylik_kisim.empty:
    aylar = ", ".join(ay_etiketi(a) for a in sorted(aylik_kisim["ay"].unique()))
    st.info(f"ℹ️ {aylar} için günlük kayıt yok (ay sayfaları boş). Bu aylar ÖZET "
            "sayfasındaki **ay toplamıyla** rapora eklendi; aralık bu aylara kısmen "
            "girse de tam ay sayılır.")

# Önceki eşit uzunluktaki dönemle kıyas (yalnız ikisi de günlük kayıttan geliyorsa)
gun_sayisi = (bit - bas).days + 1
onceki = aralik_sec(bas - dt.timedelta(days=gun_sayisi), bas - dt.timedelta(days=1), presler)
kiyas = (not onceki.empty and (onceki["tur"] == "gün").all() and (o["tur"] == "gün").all())
g = ozetle(o)
p = ozetle(onceki) if kiyas else None


def fark(anahtar, carpan=1.0, ondalik=0, birim=""):
    if p is None or p[anahtar] is None or g[anahtar] is None:
        return None
    return f"{sayi((g[anahtar] - p[anahtar]) * carpan, ondalik)}{birim}"


st.markdown(f"#### {bas:%d.%m.%Y} – {bit:%d.%m.%Y}  ·  {gun_sayisi} gün"
            + (f"  ·  {sayi(g['uretim_gunu'])} üretim günü" if g["uretim_gunu"] else ""))
if kiyas:
    st.caption(f"Oklar bir önceki {gun_sayisi} günle "
               f"({bas - dt.timedelta(days=gun_sayisi):%d.%m} – {bas - dt.timedelta(days=1):%d.%m}) kıyastır.")

# Birimler başlıkta: dar ekranda sayı kesilmesin
k = st.columns(4)
k[0].metric("Hammadde (ton)", sayi(g["hammadde"] / 1000, 1), fark("hammadde", 1 / 1000, 1))
k[1].metric("Testere net (ton)", sayi(g["testere"] / 1000, 1), fark("testere", 1 / 1000, 1))
k[2].metric("Fire (%)", sayi(g["fire"] * 100, 1) if g["fire"] is not None else "–",
            fark("fire", 100, 1, " puan"), delta_color="inverse")
k[3].metric("Saatlik Üretim (kg/saat)", sayi(g["kg_saat"]), fark("kg_saat"),
            help="Testere kg ÷ net çalışma saati")
k = st.columns(4)
k[0].metric("Net Çalışma (saat)", sayi(g["net_saat"]), fark("net_saat"),
            help=f"Brüt {sayi(g['brut_saat'])} saat · verim %{sayi((g['verim'] or 0) * 100, 1)}")
k[1].metric("Duruş (saat)", sayi(g["durus_saat"], 1), fark("durus_saat", 1, 1),
            delta_color="inverse")
k[2].metric("Kalıp Değişimi (setup)", sayi(g["setup"]), fark("setup"))
k[3].metric("Biyet", sayi(g["biyet_adet"]), fark("biyet_adet"))

sekme = st.tabs(["📈 Trend", "🏭 Pres Karşılaştırma", "⏸ Duruşlar", "🔎 Gün Analizi",
                 "📋 Detay Tablo"])

# ---------------------------------------------------------------------
# Trend: gün / hafta / ay kırılımı
# ---------------------------------------------------------------------
with sekme[0]:
    varsayilan = "Gün" if gun_sayisi <= 45 else ("Hafta" if gun_sayisi <= 120 else "Ay")
    kirilim = st.radio("Kırılım", ["Gün", "Hafta", "Ay"], horizontal=True,
                       index=["Gün", "Hafta", "Ay"].index(varsayilan))
    t = o if kirilim == "Ay" else o[o["tur"] == "gün"]
    if kirilim != "Ay" and not aylik_kisim.empty:
        st.caption("Günlük kaydı olmayan aylar gün/hafta kırılımında görünmez; "
                   "onlar için **Ay** kırılımını seçin.")
    if t.empty:
        st.info("Bu kırılımda gösterilecek günlük kayıt yok.")
    else:
        t = t.copy()
        if kirilim == "Gün":
            t["donem"] = t["tarih"]
            t["etiket"] = t["donem"].dt.strftime("%d.%m")
        elif kirilim == "Hafta":
            t["donem"] = t["tarih"] - pd.to_timedelta(t["tarih"].dt.weekday, unit="D")
            t["etiket"] = t["donem"].dt.strftime("%d.%m") + " haftası"
        else:
            t["donem"] = t["ay"]
            t["etiket"] = t["donem"].map(ay_etiketi)
        d = (t.groupby(["donem", "etiket", "pres"]).apply(ozetle, include_groups=False)
             .reset_index())
        d["testere_ton"], d["hammadde_ton"] = d["testere"] / 1000, d["hammadde"] / 1000
        d["fire_yuzde"] = d["fire"].astype(float) * 100
        sira = list(d.sort_values("donem")["etiket"].unique())
        x = alt.X("etiket:O", title=None, sort=sira,
                  axis=alt.Axis(labelAngle=0 if len(sira) <= 14 else -45))
        renk = alt.Color("pres:N", scale=PRES_RENK, title="Pres", legend=alt.Legend(orient="top"))
        ipucu = [alt.Tooltip("etiket:N", title="Dönem"), alt.Tooltip("pres:N", title="Pres"),
                 alt.Tooltip("hammadde_ton:Q", title="Hammadde ton", format=",.1f"),
                 alt.Tooltip("testere_ton:Q", title="Testere ton", format=",.1f"),
                 alt.Tooltip("fire_yuzde:Q", title="Fire %", format=".1f"),
                 alt.Tooltip("kg_saat:Q", title="kg/saat", format=",.0f"),
                 alt.Tooltip("net_saat:Q", title="Net saat", format=",.1f"),
                 alt.Tooltip("setup:Q", title="Setup")]
        st.subheader(f"Testere (net) üretim, ton · {kirilim.lower()} bazında")
        st.altair_chart(
            alt.Chart(d).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                  stroke="white", strokeWidth=2)
            .encode(x=x, y=alt.Y("testere_ton:Q", title="Ton", stack=True), color=renk,
                    tooltip=ipucu).properties(height=280), use_container_width=True)
        sol, sag = st.columns(2)
        cizgi = alt.Chart(d).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60))
        with sol:
            st.subheader("Fire %")
            st.altair_chart(cizgi.encode(x=x, y=alt.Y("fire_yuzde:Q", title="Fire %"),
                                         color=renk, tooltip=ipucu).properties(height=250),
                            use_container_width=True)
        with sag:
            st.subheader("Saatlik üretim (kg/saat)")
            st.altair_chart(cizgi.encode(x=x, y=alt.Y("kg_saat:Q", title="kg/saat"),
                                         color=renk, tooltip=ipucu).properties(height=250),
                            use_container_width=True)

# ---------------------------------------------------------------------
# Pres karşılaştırma
# ---------------------------------------------------------------------
with sekme[1]:
    satirlar = {pr: ozetle(o[o["pres"] == pr]) for pr in presler if (o["pres"] == pr).any()}
    if len(satirlar) > 1:
        satirlar["Toplam"] = g
    satir_adi = [
        ("Hammadde (ton)", lambda s: sayi(s["hammadde"] / 1000, 1)),
        ("Testere (ton)", lambda s: sayi(s["testere"] / 1000, 1)),
        ("Fire %", lambda s: sayi(s["fire"] * 100, 1) if s["fire"] is not None else "–"),
        ("Saatlik üretim (kg/saat)", lambda s: sayi(s["kg_saat"])),
        ("Brüt çalışma (saat)", lambda s: sayi(s["brut_saat"], 1)),
        ("Net çalışma (saat)", lambda s: sayi(s["net_saat"], 1)),
        ("Çalışma verimi % (net/brüt)", lambda s: sayi((s["verim"] or 0) * 100, 1)),
        ("Duruş (saat)", lambda s: sayi(s["durus_saat"], 1)),
        ("Üretim günü", lambda s: sayi(s["uretim_gunu"]) if s["uretim_gunu"] else "–"),
        ("Günlük ort. testere (kg)",
         lambda s: sayi(s["testere"] / s["uretim_gunu"]) if s["uretim_gunu"] and not (o["tur"] == "ay").any() else "–"),
        ("Kalıp değişimi (setup)", lambda s: sayi(s["setup"])),
        ("Deneme", lambda s: sayi(s["deneme"])),
        ("Çalışmayan kalıp", lambda s: sayi(s["calismayan_kalip"])),
        ("Biyet (adet)", lambda s: sayi(s["biyet_adet"])),
        ("Biyet başına testere (kg)",
         lambda s: sayi(s["testere"] / s["biyet_adet"], 1) if s["biyet_adet"] else "–"),
        ("Ort. biyet boyu (mm)", lambda s: sayi(s["biyet_boyu"])),
        ("Ort. hız (mm/sn)", lambda s: sayi(s["hiz"], 2)),
    ]
    st.dataframe(pd.DataFrame({ad: [f(s) for f in [fn for _, fn in satir_adi]]
                               for ad, s in satirlar.items()},
                              index=[a for a, _ in satir_adi]),
                 use_container_width=True, height=36 * len(satir_adi) + 40)
    if len(satirlar) > 1:
        pay = pd.DataFrame({"pres": [p_ for p_ in satirlar if p_ != "Toplam"],
                            "ton": [satirlar[p_]["testere"] / 1000 for p_ in satirlar if p_ != "Toplam"]})
        pay["oran"] = pay["ton"] / pay["ton"].sum() * 100
        st.subheader("Testere üretimindeki pay")
        st.altair_chart(
            alt.Chart(pay).mark_bar(stroke="white", strokeWidth=2, height=28)
            .encode(x=alt.X("ton:Q", stack="normalize", title=None, axis=alt.Axis(format="%")),
                    color=alt.Color("pres:N", scale=PRES_RENK, title="Pres",
                                    legend=alt.Legend(orient="top")),
                    tooltip=[alt.Tooltip("pres:N", title="Pres"),
                             alt.Tooltip("ton:Q", title="Ton", format=",.1f"),
                             alt.Tooltip("oran:Q", title="Pay %", format=".1f")])
            .properties(height=70), use_container_width=True)

# ---------------------------------------------------------------------
# Duruşlar
# ---------------------------------------------------------------------
with sekme[2]:
    durus = (o.melt(id_vars=["tarih", "ay", "pres"], value_vars=list(DURUS_ADI),
                    var_name="tip", value_name="dk"))
    durus = durus[durus["dk"] > 0]
    if durus.empty:
        st.success("Seçilen dönemde duruş kaydı yok.")
    else:
        durus["tip_adi"] = durus["tip"].map(DURUS_ADI)
        durus["saat"] = durus["dk"] / 60
        tip_renk = alt.Scale(domain=list(DURUS_ADI.values()), range=PALET[2:8])
        toplam = (durus.groupby(["tip_adi"])["saat"].sum().reset_index()
                  .sort_values("saat", ascending=False))
        toplam["oran"] = toplam["saat"] / toplam["saat"].sum() * 100
        sol, sag = st.columns([2, 3])
        with sol:
            st.subheader("Duruş tipine göre (saat)")
            st.altair_chart(
                alt.Chart(toplam).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                                           color=TEK_RENK)
                .encode(y=alt.Y("tip_adi:N", sort="-x", title=None, axis=alt.Axis(labelLimit=200)),
                        x=alt.X("saat:Q", title="Saat"),
                        tooltip=[alt.Tooltip("tip_adi:N", title="Tip"),
                                 alt.Tooltip("saat:Q", title="Saat", format=",.1f"),
                                 alt.Tooltip("oran:Q", title="Pay %", format=".1f")])
                .properties(height=40 * len(toplam) + 30), use_container_width=True)
            st.dataframe(pd.DataFrame({
                "Tip": toplam["tip_adi"], "Saat": toplam["saat"].round(1),
                "Pay %": toplam["oran"].round(1)}), hide_index=True, use_container_width=True)
        with sag:
            gunlu_durus = gun_sayisi <= 62 and (durus["tarih"].isin(o.loc[o["tur"] == "gün", "tarih"])).any()
            durus["etiket"] = (durus["tarih"].dt.strftime("%d.%m") if gunlu_durus and (o["tur"] == "gün").all()
                               else durus["ay"].map(ay_etiketi))
            durus["sira"] = durus["tarih"] if gunlu_durus and (o["tur"] == "gün").all() else durus["ay"]
            st.subheader("Döneme göre duruş (saat)")
            sira = list(durus.sort_values("sira")["etiket"].unique())
            st.altair_chart(
                alt.Chart(durus).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                          stroke="white", strokeWidth=2)
                .encode(x=alt.X("etiket:O", title=None, sort=sira, axis=alt.Axis(labelAngle=0 if len(sira) <= 14 else -45)),
                        y=alt.Y("sum(saat):Q", title="Saat", stack=True),
                        color=alt.Color("tip_adi:N", scale=tip_renk, title="Tip",
                                        legend=alt.Legend(orient="top")),
                        tooltip=[alt.Tooltip("etiket:N", title="Dönem"),
                                 alt.Tooltip("tip_adi:N", title="Tip"),
                                 alt.Tooltip("sum(saat):Q", title="Saat", format=",.1f")])
                .properties(height=300), use_container_width=True)
        pres_durus = durus.pivot_table(index="pres", columns="tip_adi", values="saat",
                                       aggfunc="sum", fill_value=0).round(1)
        st.subheader("Pres × duruş tipi (saat)")
        st.dataframe(pres_durus, use_container_width=True)

# ---------------------------------------------------------------------
# Gün analizi (yalnız günlük kayıtlar)
# ---------------------------------------------------------------------
with sekme[3]:
    gd = o[o["tur"] == "gün"].copy()
    if gd.empty:
        st.info("Seçilen aralıkta günlük kayıt yok (yalnız ay toplamları var).")
    else:
        gd["fire_yuzde"] = (gd["hammadde"] - gd["testere"]) / gd["hammadde"] * 100
        gd["net_saat"] = gd["net_dk"] / 60
        gd["kg_saat"] = (gd["testere"] / gd["net_saat"]).where(gd["net_saat"] > 0)
        gd["gun_adi"] = gd["tarih"].dt.weekday.map(lambda i: GUN_ADI[i])
        goster = lambda t: pd.DataFrame({
            "Tarih": t["tarih"].dt.strftime("%d.%m.%Y"), "Gün": t["gun_adi"], "Pres": t["pres"],
            "Testere (kg)": t["testere"].map(sayi), "Fire %": t["fire_yuzde"].map(lambda v: sayi(v, 1)),
            "kg/saat": t["kg_saat"].map(sayi), "Setup": t["setup"].map(sayi),
            "Duruş (dk)": t["durus_dk"].map(sayi)})
        sol, sag = st.columns(2)
        with sol:
            st.subheader("🏆 En yüksek üretim günleri")
            st.dataframe(goster(gd.nlargest(5, "testere")), hide_index=True, use_container_width=True)
            st.subheader("⚡ En yüksek saatlik üretim")
            st.dataframe(goster(gd[gd["net_saat"] >= 4].nlargest(5, "kg_saat")),
                         hide_index=True, use_container_width=True)
        with sag:
            st.subheader("⚠️ En yüksek fire günleri")
            st.dataframe(goster(gd[gd["hammadde"] >= 1000].nlargest(5, "fire_yuzde")),
                         hide_index=True, use_container_width=True)
            st.subheader("⏸ En çok duruş olan günler")
            dd = gd[gd["durus_dk"] > 0].nlargest(5, "durus_dk")
            if dd.empty:
                st.success("Duruş olan gün yok.")
            else:
                st.dataframe(goster(dd), hide_index=True, use_container_width=True)
        st.caption("Saatlik üretim sıralamasında en az 4 saat net çalışılan, fire "
                   "sıralamasında en az 1 ton hammadde girilen günler dikkate alınır.")
        st.subheader("Haftanın günlerine göre ortalama")
        hg = (gd.groupby(["gun_adi", "pres"]).agg(testere=("testere", "mean"), gun=("tarih", "nunique"))
              .reset_index())
        st.altair_chart(
            alt.Chart(hg).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(x=alt.X("gun_adi:N", sort=GUN_ADI, title=None, axis=alt.Axis(labelAngle=0)),
                    xOffset="pres:N",
                    y=alt.Y("testere:Q", title="Ort. testere (kg/gün)"),
                    color=alt.Color("pres:N", scale=PRES_RENK, title="Pres", legend=alt.Legend(orient="top")),
                    tooltip=[alt.Tooltip("gun_adi:N", title="Gün"), alt.Tooltip("pres:N", title="Pres"),
                             alt.Tooltip("testere:Q", title="Ort. testere kg", format=",.0f"),
                             alt.Tooltip("gun:Q", title="Gün sayısı")])
            .properties(height=260), use_container_width=True)

# ---------------------------------------------------------------------
# Detay tablo
# ---------------------------------------------------------------------
with sekme[4]:
    tablo = o.sort_values(["tarih", "pres"]).copy()
    tablo["fire_yuzde"] = ((tablo["hammadde"] - tablo["testere"]) / tablo["hammadde"] * 100).round(1)
    tablo["kg_saat"] = (tablo["testere"] / (tablo["net_dk"] / 60)).where(tablo["net_dk"] > 0).round(0)
    tablo["donem"] = tablo.apply(lambda r: r["tarih"].strftime("%d.%m.%Y") if r["tur"] == "gün"
                                 else f"{ay_etiketi(r['tarih'])} (ay toplamı)", axis=1)
    cikti = pd.DataFrame({
        "Tarih": tablo["donem"], "Pres": tablo["pres"],
        "Hammadde (kg)": tablo["hammadde"], "Testere (kg)": tablo["testere"],
        "Fire %": tablo["fire_yuzde"], "Saatlik Üretim (kg/saat)": tablo["kg_saat"],
        "Brüt Çalışma (dk)": tablo["brut_dk"], "Net Çalışma (dk)": tablo["net_dk"],
        "Duruş (dk)": tablo["durus_dk"], **{f"{DURUS_ADI[c]} (dk)": tablo[c] for c in DURUS_ADI},
        "Setup": tablo["setup"], "Deneme": tablo["deneme"],
        "Çalışmayan Kalıp": tablo["calismayan_kalip"], "Biyet": tablo["biyet_adet"],
        "Ort. Biyet Boyu (mm)": tablo["biyet_boyu"].round(0),
        "Ort. Hız (mm/sn)": tablo["hiz"].round(2),
    })
    bos = [c for c in cikti.columns if c.endswith("(dk)") and c != "Duruş (dk)" and (cikti[c] == 0).all()]
    cikti = cikti.drop(columns=bos)
    st.dataframe(cikti, hide_index=True, use_container_width=True)
    st.download_button("⬇️ CSV indir", cikti.to_csv(index=False, sep=";", decimal=",")
                       .encode("utf-8-sig"),
                       file_name=f"pres_uretim_{bas:%Y%m%d}_{bit:%Y%m%d}.csv", mime="text/csv")
