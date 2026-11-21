"""Müşteri adlarının birleştirilmesi.

Excel'de aynı müşteri farklı yazılabiliyor (BG / BG PLAST / BG PLSAT,
ANATOLIA / ANATOLİA, BG 142 ...). Önce otomatik sadeleştirilir:
  - büyük harf, Türkçe harfler sadeleşir (İ→I, Ş→S ...), boşluk ve noktalama atılır
  - sondaki numara ve '-TEST' eki atılır (BG 142 → BG, AKMANLAR-TEST → AKMANLAR)
Sonra aşağıdaki tabloyla birleştirilir. Yeni bir yazılış görürseniz ilgili
satırın listesine ekleyin (yazıldığı gibi yazmanız yeterli).
"""
import re

import pandas as pd

# Gösterilecek ad: [aynı müşterinin diğer yazılışları]
GRUPLAR = {
    "BG PLAST": ["BG", "BG PLASTİK", "BG PLSAT", "BG M08"],
    "AD MEDİA": ["AD MADIA", "AD MEDYA"],
    "AKMANLAR": ["AKMANŞLAR"],
    "ALUAKS": ["AKUAKS"],
    "ALUGLASS": ["ALUGLAS"],
    "ALUPROGRES": ["ALUPGRES", "ALUGRES", "ALUPRES", "ALURES", "ALUPROGES"],
    "ANATOLIA": ["ANATOKIA"],
    "ARCHIGIA": ["ARCHCIA", "ARCHGIA", "ARCHIA", "ARCHICA"],
    "AVG OTO": ["AVG"],
    "BF BUILDING": ["BF", "BF FACEDE", "BF FACEDES"],
    "COŞKUNLAR": ["COŞKUN", "ÇOŞKUN ALM"],
    "EGEMEN": ["EGEMEN ALM"],
    "E-SYSTEM": ["E SYSYTEM", "ESYSTEM"],
    "GOLMAT": ["GOLLMAT"],
    "KAVİN": ["KANİN"],
    "KAYRA METAL": ["KAYRA"],
    "KRUG": ["KRUG D.O.O"],
    "MEISSL": ["MEIS", "MEISSI", "MEİSSİ", "MEISSL GMBH"],
    "METALLICA": ["METALICA"],
    "MHR TURİZM": ["MHR TURUZM"],
    "NUOVA": ["NOUVA", "NVOVA", "WUOVA", "NUOVA NEON"],
    "PROSES": ["PROSESS"],
    "RE GRUP": ["REG GRUP"],
    "RM İSTANBUL": ["RM", "RM İST"],
    "SENDA": ["SENDA INT."],
    "SİSTEM REKLAM": ["S.REKLAM", "SİSTEM"],
    "TAL ENGINEERING": ["TAL", "TAL ENG.", "TAL ENGIINERING", "TAL FAÇADE", "TAL FAAÇADE",
                        "TAL FAAÇEDE", "TAL FAÇAADE"],
    "TOORS": ["TORS"],
    "UAB HELIOPOLIS": ["UAB", "HELIOPOLIS", "HELİOPLİS", "UAB PLANTAS"],
    "ÇUKUROVA": ["ÇUJKUROVA"],
}

_TR = str.maketrans("İIŞĞÜÖÇ", "IISGUOC")


def _sade(ad):
    """Sondaki numara ve '-TEST' eki atılmış yazılış (BG 142 → BG)."""
    s = str(ad).upper().strip()
    s = re.sub(r"[\s\-]+TEST$", "", s)
    return re.sub(r"[\s\-]*\d+$", "", s) or s


def _anahtar(ad):
    return re.sub(r"[^0-9A-Z]", "", _sade(ad).translate(_TR))


_GRUP = {_anahtar(v): ad for ad, liste in GRUPLAR.items() for v in [ad, *liste]}


def birlestir(seri):
    """Müşteri sütununu birleşik adlarla döndürür. Tabloda olmayanlar en sık
    yazılışlarıyla (sondaki numara atılmış) gösterilir."""
    seri = seri.astype("string")
    anahtar = seri.map(lambda v: _anahtar(v) if pd.notna(v) else pd.NA).astype("string")
    sade = seri.map(lambda v: _sade(v) if pd.notna(v) else pd.NA)
    en_sik = (pd.DataFrame({"a": anahtar, "m": sade}).dropna()
              .groupby("a")["m"].agg(lambda s: s.value_counts().index[0]))
    ad = anahtar.map(lambda a: _GRUP.get(a, en_sik.get(a)) if pd.notna(a) else pd.NA)
    return ad.astype("string").where(anahtar.str.len() > 0)
