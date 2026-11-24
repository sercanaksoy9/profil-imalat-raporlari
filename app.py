"""Profil İmalat Üretim Raporları (ALBOND).

Veri klasörüne (ALBOND RAPORLAR) giren rapor dosyalarını okur ve pano olarak
gösterir. Her rapor üstteki menüde bir başlıktır. Klasördeki dosyalar
değişince pano kendini yeniler (1 dakikada bir bakar).
"""
import streamlit as st

import ortak
import parola
import veri

st.set_page_config(page_title="Profil İmalat Üretim Raporları", page_icon="📊",
                   layout="wide")


@st.fragment(run_every="60s")
def klasor_izle():
    """Veri klasörü değişince sayfayı yeniden çalıştırır."""
    imza = veri.klasor_imzasi()
    onceki = st.session_state.get("klasor_imzasi")
    st.session_state["klasor_imzasi"] = imza
    if onceki is not None and imza != onceki:
        st.rerun(scope="app")


ortak.tema_uygula()
parola.parola_kontrol("Profil İmalat Üretim Raporları")
klasor_izle()

# Raporlar (başlıklar): yenisi eklendikçe bu listeye bir satır gelir
SAYFALAR = [
    st.Page("sayfa_pres_uretim.py", title="Pres Üretim Raporu", icon="🏭",
            url_path="pres-uretim-2026", default=True),
    st.Page("sayfa_fire.py", title="Toplam Fire 2026", icon="♻️", url_path="toplam-fire-2026"),
    st.Page("sayfa_pres_aylik.py", title="Pres Üretimler Aylık 2023-2026", icon="📅",
            url_path="pres-uretimler-aylik"),
    st.Page("sayfa_enerji.py", title="Enerji Sarfiyatlar 2026", icon="⚡",
            url_path="enerji-sarfiyatlar-2026"),
    st.Page("sayfa_tozboya.py", title="Toz Boya Aylık 2025-2026", icon="🎨",
            url_path="toz-boya-aylik"),
    st.Page("sayfa_kalip.py", title="Kalıp Bazlı Arama", icon="🔩", url_path="kalip-arama"),
]
st.navigation(SAYFALAR, position="top").run()
