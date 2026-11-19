"""2026 Pres Üretim Raporu sayfası.

Aylık görünüm 'ÖZET 6"' ve 'ÖZET 8"' sayfalarından (yılın bütün ayları),
günlük görünüm ay sayfalarındaki günlük satırlardan gelir.
"""
import altair as alt
import pandas as pd
import streamlit as st

from ortak import (PALET, PRES_RENK, TEK_RENK, ay_etiketi, kaynak_notu,
                   rapor_verisi, sayi)

DURUS_ADI = {"ariza": "Arıza", "isletme": "İşletme", "elektrik": "Elektrik Kesintisi",
             "planli": "Planlı Duruş", "diger": "Diğer Duruş", "iftar": "İftar Duruşu"}

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
# Filtreler
# ---------------------------------------------------------------------
aylar = sorted(ozet["ay"].unique())
f1, f2 = st.columns([1, 3])
presler = f1.multiselect("Pres", ['6"', '8"'], default=['6"', '8"'])
secili_aylar = f2.multiselect("Aylar", aylar, default=aylar, format_func=ay_etiketi)
o = ozet[ozet["pres"].isin(presler) & ozet["ay"].isin(secili_aylar)].copy()
if o.empty:
    st.warning("Seçilen pres ve aylarda kayıt yok.")
    st.stop()


def toplam_gostergeler(t):
    ham, tes = t["hammadde"].sum(), t["testere"].sum()
    net_saat = t["net_saat"].sum()
    return {
        "hammadde": ham, "testere": tes, "fire": (ham - tes) / ham if ham else None,
        "net_saat": net_saat, "brut_saat": t["brut_saat"].sum(),
        "kg_saat": tes / net_saat if net_saat else None,
        "durus_saat": t["durus_dk"].sum() / 60, "setup": t["setup"].sum(),
        "biyet": t["biyet_adet"].sum(), "deneme": t["deneme"].sum(),
    }


g = toplam_gostergeler(o)
k = st.columns(4)
k[0].metric("Hammadde", f"{sayi(g['hammadde'] / 1000, 1)} ton")
k[1].metric("Testere (net)", f"{sayi(g['testere'] / 1000, 1)} ton")
k[2].metric("Fire", f"%{sayi(g['fire'] * 100, 1)}")
k[3].metric("Saatlik Üretim", f"{sayi(g['kg_saat'])} kg/saat",
            help="Testere kg ÷ net çalışma saati")
k = st.columns(4)
k[0].metric("Net Çalışma", f"{sayi(g['net_saat'])} saat",
            help=f"Brüt {sayi(g['brut_saat'])} saat")
k[1].metric("Duruş", f"{sayi(g['durus_saat'], 1)} saat")
k[2].metric("Kalıp Değişimi (setup)", sayi(g["setup"]))
k[3].metric("Biyet", sayi(g["biyet"]))

sekme = st.tabs(["📅 Aylık", "📆 Günlük", "⏸ Duruşlar", "📋 Özet Tablo"])

# ---------------------------------------------------------------------
# Aylık
# ---------------------------------------------------------------------
o["etiket"] = o["ay"].map(ay_etiketi)
o["testere_ton"] = o["testere"] / 1000
o["hammadde_ton"] = o["hammadde"] / 1000
o["fire_yuzde"] = o["fire"] * 100
sira = [ay_etiketi(a) for a in sorted(o["ay"].unique())]
x = alt.X("etiket:O", title=None, sort=sira, axis=alt.Axis(labelAngle=0))
renk = alt.Color("pres:N", scale=PRES_RENK, title="Pres", legend=alt.Legend(orient="top"))
ipucu = [alt.Tooltip("etiket:N", title="Ay"), alt.Tooltip("pres:N", title="Pres"),
         alt.Tooltip("hammadde_ton:Q", title="Hammadde ton", format=",.1f"),
         alt.Tooltip("testere_ton:Q", title="Testere ton", format=",.1f"),
         alt.Tooltip("fire_yuzde:Q", title="Fire %", format=".1f"),
         alt.Tooltip("kg_saat:Q", title="kg/saat", format=",.0f"),
         alt.Tooltip("net_saat:Q", title="Net saat", format=",.0f")]

with sekme[0]:
    st.subheader("Aylık testere (net) üretim, ton")
    st.altair_chart(
        alt.Chart(o).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                              stroke="white", strokeWidth=2)
        .encode(x=x, y=alt.Y("testere_ton:Q", title="Ton", stack=True), color=renk,
                tooltip=ipucu).properties(height=280), use_container_width=True)
    sol, sag = st.columns(2)
    with sol:
        st.subheader("Fire %")
        st.altair_chart(
            alt.Chart(o).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=70))
            .encode(x=x, y=alt.Y("fire_yuzde:Q", title="Fire %"), color=renk, tooltip=ipucu)
            .properties(height=250), use_container_width=True)
    with sag:
        st.subheader("Saatlik üretim (kg/saat)")
        st.altair_chart(
            alt.Chart(o).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=70))
            .encode(x=x, y=alt.Y("kg_saat:Q", title="kg/saat"), color=renk, tooltip=ipucu)
            .properties(height=250), use_container_width=True)

# ---------------------------------------------------------------------
# Günlük (ay sayfalarındaki günlük satırlar)
# ---------------------------------------------------------------------
with sekme[1]:
    if gunluk.empty:
        st.info("Günlük kayıt bulunamadı.")
    else:
        gun_aylari = sorted(gunluk["ay"].unique())
        st.caption("Günlük kayıtlar ay sayfalarından gelir; Ocak–Mayıs sayfaları "
                   "boş olduğu için o aylar yalnız aylık görünümde vardır.")
        secili = st.selectbox("Ay", gun_aylari, index=len(gun_aylari) - 1,
                              format_func=ay_etiketi)
        gd = gunluk[(gunluk["ay"] == secili) & gunluk["pres"].isin(presler)].copy()
        if gd.empty:
            st.info("Bu ay için seçili preste kayıt yok.")
        else:
            gd["gun"] = gd["tarih"].dt.strftime("%d.%m")
            gd["testere_kg"] = gd["testere"]
            gd["fire_yuzde"] = (gd["hammadde"] - gd["testere"]) / gd["hammadde"] * 100
            gun_sira = sorted(gd["gun"].unique(), key=lambda s: (s[3:], s[:2]))
            st.subheader(f"{ay_etiketi(secili)} günlük testere (kg)")
            st.altair_chart(
                alt.Chart(gd).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                       stroke="white", strokeWidth=2)
                .encode(x=alt.X("gun:O", title=None, sort=gun_sira),
                        y=alt.Y("testere_kg:Q", title="kg", stack=True), color=renk,
                        tooltip=[alt.Tooltip("gun:N", title="Gün"),
                                 alt.Tooltip("pres:N", title="Pres"),
                                 alt.Tooltip("hammadde:Q", title="Hammadde kg", format=",.0f"),
                                 alt.Tooltip("testere_kg:Q", title="Testere kg", format=",.0f"),
                                 alt.Tooltip("fire_yuzde:Q", title="Fire %", format=".1f"),
                                 alt.Tooltip("biyet_adet:Q", title="Biyet")])
                .properties(height=280), use_container_width=True)
            st.dataframe(pd.DataFrame({
                "Tarih": gd["tarih"], "Pres": gd["pres"],
                "Hammadde (kg)": gd["hammadde"], "Testere (kg)": gd["testere"],
                "Fire %": gd["fire_yuzde"].round(1), "Setup": gd["setup"],
                "Biyet": gd["biyet_adet"], "Ort. Biyet Boyu": gd["biyet_boyu"].round(0),
                "Ort. Hız (mm/sn)": gd["hiz"].round(2),
                "Çalışmayan Kalıp": gd["calismayan_kalip"], "Deneme": gd["deneme"],
                "Duruş (dk)": gd["durus_dk"], "Çalışma (dk)": gd["calisma_dk"],
                "Vardiya": gd["vardiya"],
            }), hide_index=True, use_container_width=True,
                column_config={"Tarih": st.column_config.DateColumn(format="DD.MM.YYYY")})

# ---------------------------------------------------------------------
# Duruşlar
# ---------------------------------------------------------------------
with sekme[2]:
    durus = (o.melt(id_vars=["ay", "etiket", "pres"], value_vars=list(DURUS_ADI),
                    var_name="tip", value_name="dk").fillna({"dk": 0}))
    durus = durus[durus["dk"] > 0]
    if durus.empty:
        st.info("Seçilen dönemde duruş yok.")
    else:
        durus["tip_adi"] = durus["tip"].map(DURUS_ADI)
        durus["saat"] = durus["dk"] / 60
        tipler = [DURUS_ADI[t] for t in DURUS_ADI if t in set(durus["tip"])]
        tip_renk = alt.Scale(domain=list(DURUS_ADI.values()), range=PALET[2:8])
        toplam = (durus.groupby("tip_adi")["saat"].sum().reset_index()
                  .sort_values("saat", ascending=False))
        sol, sag = st.columns([2, 3])
        with sol:
            st.subheader("Duruş tipine göre (saat)")
            st.altair_chart(
                alt.Chart(toplam).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                                           color=TEK_RENK)
                .encode(y=alt.Y("tip_adi:N", sort="-x", title=None,
                                axis=alt.Axis(labelLimit=200)),
                        x=alt.X("saat:Q", title="Saat"),
                        tooltip=[alt.Tooltip("tip_adi:N", title="Tip"),
                                 alt.Tooltip("saat:Q", title="Saat", format=",.1f")])
                .properties(height=40 * len(toplam) + 30), use_container_width=True)
        with sag:
            st.subheader("Aylık duruş (saat)")
            st.altair_chart(
                alt.Chart(durus).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                          stroke="white", strokeWidth=2)
                .encode(x=x, y=alt.Y("saat:Q", title="Saat", stack=True),
                        color=alt.Color("tip_adi:N", scale=tip_renk, title="Tip",
                                        legend=alt.Legend(orient="top")),
                        tooltip=[alt.Tooltip("etiket:N", title="Ay"),
                                 alt.Tooltip("pres:N", title="Pres"),
                                 alt.Tooltip("tip_adi:N", title="Tip"),
                                 alt.Tooltip("saat:Q", title="Saat", format=",.1f")])
                .properties(height=280), use_container_width=True)

# ---------------------------------------------------------------------
# Özet tablo (Excel'deki ÖZET sayfaları gibi)
# ---------------------------------------------------------------------
with sekme[3]:
    tablo = o.sort_values(["pres", "ay"])
    st.dataframe(pd.DataFrame({
        "Pres": tablo["pres"], "Ay": tablo["etiket"],
        "Hammadde (kg)": tablo["hammadde"], "Testere (kg)": tablo["testere"],
        "Fire %": (tablo["fire"] * 100).round(1),
        "Brüt Çalışma (saat)": tablo["brut_saat"].round(1),
        "Net Çalışma (saat)": tablo["net_saat"].round(1),
        "Saatlik Üretim (kg/saat)": tablo["kg_saat"].round(0),
        "Duruş (dk)": tablo["durus_dk"], "Kalıp Değişimi": tablo["setup"],
        "Deneme": tablo["deneme"], "Çalışmayan Kalıp": tablo["calismayan_kalip"],
        "Biyet": tablo["biyet_adet"], "Ort. Hız (mm/sn)": tablo["hiz"].round(2),
        "Ort. Biyet Boyu (mm)": tablo["biyet_boyu"].round(0),
    }), hide_index=True, use_container_width=True)
    st.download_button("⬇️ CSV indir", tablo.drop(columns=["etiket"]).to_csv(index=False)
                       .encode("utf-8-sig"), file_name="2026_pres_uretim_ozet.csv",
                       mime="text/csv")
