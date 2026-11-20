"""Basit şifre ekranı.

Şifre koda yazılmaz; Streamlit'in Secrets bölümünden okunur:
    parola = "..."            (Streamlit Cloud: App settings → Secrets)
Bu bilgisayarda .streamlit/secrets.toml dosyasından (git'e girmez).
Secrets'ta 'parola' tanımlı değilse şifre sorulmaz (ör. kendi bilgisayarında).
Doğru girilen şifre tarayıcı oturumu boyunca hatırlanır.
"""
import hmac

import streamlit as st


def _tanimli_parola():
    try:
        deger = st.secrets.get("parola")
    except Exception:              # secrets dosyası hiç yoksa
        return None
    return str(deger) if deger else None


def parola_kontrol(uygulama_adi):
    """Şifre doğruysa True döner; değilse giriş kutusunu gösterip sayfayı durdurur."""
    parola = _tanimli_parola()
    if parola is None or st.session_state.get("_parola_ok"):
        return True
    sol, orta, sag = st.columns([1, 1.4, 1])
    with orta:
        st.markdown(f"### 🔒 {uygulama_adi}")
        st.caption("Devam etmek için şifreyi girin.")
        with st.form("parola_formu", clear_on_submit=True):
            girilen = st.text_input("Şifre", type="password")
            gonder = st.form_submit_button("Giriş", use_container_width=True)
        if gonder:
            if hmac.compare_digest(girilen.encode(), parola.encode()):
                st.session_state["_parola_ok"] = True
                st.rerun()
            st.error("Şifre hatalı.")
    st.stop()
