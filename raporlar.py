"""Pres dışındaki raporlar: aylık üretim, fire, enerji, kalıp ve bakım.

Her rapor, veri klasöründeki adı belli kelimeleri içeren en yeni Excel
dosyasından okunur ('Eski' klasörleri atlanır). Bulutta Excel yoktur;
senkron.py'nin yazdığı veri/<anahtar>.parquet okunur.
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd

import veri

AYLAR = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ",
         "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"]


def _sade(metin):
    """Karşılaştırma için: Türkçe karakterler sadeleşir, küçük harf, NFC."""
    metin = unicodedata.normalize("NFKD", str(metin))
    metin = "".join(c for c in metin if not unicodedata.combining(c))
    return (metin.replace("ı", "i").replace("İ", "I").replace("ş", "s").replace("Ş", "S")
            .replace("ğ", "g").replace("Ğ", "G").lower().strip())


def _ay_no(metin):
    s = _sade(metin)
    for i, ay in enumerate(AYLAR, 1):
        if s.startswith(_sade(ay)[:3]) and (s == _sade(ay) or len(s) <= len(_sade(ay)) + 1):
            return i
    return None


# anahtar: (dosya adında olması gereken kelimeler, olmaması gerekenler, okuyucu)
RAPORLAR = {}
# Ekranda olan ve buluta gönderilen raporlar (yeni başlık eklenince buraya)
AKTIF_RAPORLAR = ["pres_rapor_ozet", "pres_rapor_gunluk", "fire", "uretim_aylik", "enerji", "tozboya_aylik",
                  "kalip_kayitlari"]


def rapor(anahtar, kelimeler, haric=()):
    def kaydet(fonk):
        RAPORLAR[anahtar] = (kelimeler, haric, fonk)
        return fonk
    return kaydet


def kaynak_dosyasi(anahtar, kok=None):
    """Bu bilgisayarda raporun en yeni Excel dosyası (yoksa None)."""
    kok = Path(kok or veri.veri_klasoru())
    if not kok.exists():
        return None
    kelimeler, haric, _ = RAPORLAR[anahtar]
    adaylar = []
    for y in kok.rglob("*.xls*"):
        ad = _sade(y.name)
        if y.name.startswith("~$") or veri._eski_mi(y, kok):
            continue
        if all(k in ad for k in kelimeler) and not any(h in ad for h in haric):
            adaylar.append(y)
    return max(adaylar, key=lambda y: y.stat().st_mtime) if adaylar else None


def bulut_dosyasi(anahtar):
    return veri.UYGULAMA_KLASORU / "veri" / f"{anahtar}.parquet"


def oku(anahtar, yol):
    """Excel'den raporu okur (okuyucu fonksiyonla)."""
    return RAPORLAR[anahtar][2](yol)


# ---------------------------------------------------------------------
# 2026 Pres Üretim Raporu: ay sayfalarında 6" ve 8" pres blokları,
# blokta günlük satırlar (TOPLAM satırına kadar)
# ---------------------------------------------------------------------
PRES_RAPOR_SUTUN = ["tarih", "hammadde", "testere", "setup", "biyet_boyu",
                    "biyet_adet", "hiz", "calismayan_kalip", "deneme", "ariza",
                    "isletme", "elektrik", "diger", "planli", "calisma_dk",
                    "vardiya"]
DURUS_SUTUN = ["ariza", "isletme", "elektrik", "diger", "planli"]


OZET_SUTUN = {1: "hammadde", 2: "testere", 3: "brut_dk", 4: "net_dk", 5: "ariza",
              6: "isletme", 7: "elektrik", 8: "planli", 9: "diger", 10: "iftar",
              12: "setup", 13: "deneme", 14: "calismayan_kalip", 15: "durus_dk",
              16: "biyet_adet", 17: "hiz", 18: "kg_saat", 19: "biyet_boyu"}


@rapor("pres_rapor_ozet", ("pres uretim raporu",))
def pres_rapor_ozet_oku(yol):
    """ÖZET 6" ve ÖZET 8" sayfaları: her pres için ay ay toplamlar."""
    parcalar = []
    for sayfa in pd.ExcelFile(yol).sheet_names:
        s = _sade(sayfa)
        if not s.startswith("ozet"):
            continue
        pres = '8"' if "8" in s else '6"'
        d = pd.read_excel(yol, sheet_name=sayfa, header=None)
        yil = 2026
        tarihli = pd.to_numeric(re.findall(r"20\d\d", Path(yol).name)[:1] or [yil])[0]
        for i in range(len(d)):
            ay = _ay_no(d.iat[i, 0]) if isinstance(d.iat[i, 0], str) else None
            if not ay:
                continue
            satir = {"pres": pres, "ay": pd.Timestamp(int(tarihli), ay, 1)}
            for j, ad in OZET_SUTUN.items():
                satir[ad] = pd.to_numeric(d.iat[i, j], errors="coerce") if j < d.shape[1] else None
            parcalar.append(satir)
            if ay == 12:
                break  # alttaki duruş oranı tablosu da aylarla başlıyor
    o = pd.DataFrame(parcalar)
    if o.empty:
        return o
    o = o[o["hammadde"].fillna(0) > 0].reset_index(drop=True)
    o["fire"] = (o["hammadde"] - o["testere"]) / o["hammadde"]
    o["brut_saat"] = o["brut_dk"] / 60
    o["net_saat"] = o["net_dk"] / 60
    return o


@rapor("pres_rapor_gunluk", ("pres uretim raporu",))
def pres_uretim_raporu(yol):
    parcalar = []
    for sayfa in pd.ExcelFile(yol).sheet_names:
        if not _ay_no(sayfa) or _sade(sayfa).startswith("ozet"):
            continue
        d = pd.read_excel(yol, sheet_name=sayfa, header=None)
        basliklar = [i for i, v in d[0].items()
                     if isinstance(v, str) and _sade(v).startswith("uretim")]
        for b in basliklar:
            ad = _sade(d.iat[b, 0])
            pres = '8"' if "8" in ad else '6"'
            satirlar = []
            for k in range(b + 2, len(d)):
                ilk = d.iat[k, 0]
                if isinstance(ilk, str) and "toplam" in _sade(ilk):
                    break
                satirlar.append(d.iloc[k, :16].tolist())
            blok = pd.DataFrame(satirlar, columns=PRES_RAPOR_SUTUN)
            blok["tarih"] = pd.to_datetime(blok["tarih"], errors="coerce")
            for c in PRES_RAPOR_SUTUN[1:]:
                blok[c] = pd.to_numeric(blok[c], errors="coerce")
            blok = blok[blok["tarih"].notna() & (blok["hammadde"].fillna(0) > 0)]
            blok["pres"] = pres
            parcalar.append(blok)
    if not parcalar:
        return pd.DataFrame(columns=PRES_RAPOR_SUTUN + ["pres"])
    d = pd.concat(parcalar, ignore_index=True)
    sayi_sutun = [c for c in PRES_RAPOR_SUTUN if c not in ("tarih", "biyet_boyu", "hiz")]
    d[sayi_sutun] = d[sayi_sutun].fillna(0)
    d["durus_dk"] = d[DURUS_SUTUN].sum(axis=1)
    d["ay"] = d["tarih"].dt.to_period("M").dt.to_timestamp()
    return (d.drop_duplicates(["tarih", "pres"], keep="last")
            .sort_values(["tarih", "pres"]).reset_index(drop=True))


def pres_rapor_ozet(d, anahtar):
    """Gruplara göre toplamlar ve oranlar (ÖZET sayfasındaki gibi)."""
    g = d.groupby(anahtar).agg(
        hammadde=("hammadde", "sum"), testere=("testere", "sum"),
        setup=("setup", "sum"), biyet_adet=("biyet_adet", "sum"),
        calismayan_kalip=("calismayan_kalip", "sum"), deneme=("deneme", "sum"),
        calisma_dk=("calisma_dk", "sum"), durus_dk=("durus_dk", "sum"),
        **{c: (c, "sum") for c in DURUS_SUTUN}).reset_index()
    # Biyet boyu ve hız: biyet adediyle ağırlıklı ortalama
    agirlik = d.assign(_b=d["biyet_boyu"] * d["biyet_adet"], _h=d["hiz"] * d["biyet_adet"],
                       _a=d["biyet_adet"].where(d["biyet_boyu"].notna() & d["hiz"].notna(), 0))
    ort = agirlik.groupby(anahtar)[["_b", "_h", "_a"]].sum().reset_index()
    g = g.merge(ort, on=anahtar)
    g["biyet_boyu"] = (g["_b"] / g["_a"]).where(g["_a"] > 0)
    g["hiz"] = (g["_h"] / g["_a"]).where(g["_a"] > 0)
    g = g.drop(columns=["_b", "_h", "_a"])
    g["fire"] = ((g["hammadde"] - g["testere"]) / g["hammadde"]).where(g["hammadde"] > 0)
    g["brut_saat"] = g["calisma_dk"] / 60
    g["net_saat"] = (g["calisma_dk"] - g["durus_dk"]) / 60
    g["kg_saat"] = (g["testere"] / g["net_saat"]).where(g["net_saat"] > 0)
    g["durus_oran"] = (g["durus_dk"] / g["calisma_dk"]).where(g["calisma_dk"] > 0)
    return g


# ---------------------------------------------------------------------
# Aylık üretim (pres ve toz boya): bloklar 'kg/ay', 'kg/gün', 'kg/saat';
# başlığın altındaki satırda yıllar, sonraki satırlarda aylar
# ---------------------------------------------------------------------
def _yil_ay_bloklari(yol, kaynak_adi):
    satirlar = []
    for sayfa in pd.ExcelFile(yol).sheet_names:
        d = pd.read_excel(yol, sheet_name=sayfa, header=None)
        for i in range(len(d) - 2):
            baslik = next((v for v in d.iloc[i, :3] if isinstance(v, str) and "/" in v), None)
            if not baslik:
                continue
            olcu = re.search(r"\((kg\s*/\s*\w+)", baslik, re.I)
            olcu = olcu.group(1).lower().replace(" ", "") if olcu else baslik
            olcu = {"kg/ay": "kg/ay", "kg/gün": "kg/gün", "kg/saat": "kg/saat"}.get(olcu, olcu)
            yil_satiri = d.iloc[i + 1]
            yillar = {j: int(v) for j, v in yil_satiri.items()
                      if isinstance(v, (int, float)) and 2000 < v < 2100}
            for k in range(i + 2, min(i + 16, len(d))):
                etiket = next((v for v in d.iloc[k, :3] if isinstance(v, str)), None)
                ay = _ay_no(etiket) if etiket else None
                if not ay:
                    continue
                for j, yil in yillar.items():
                    deger = pd.to_numeric(d.iat[k, j], errors="coerce")
                    if pd.notna(deger) and deger != 0:
                        satirlar.append({"kaynak": kaynak_adi(sayfa), "olcu": olcu,
                                         "tarih": pd.Timestamp(yil, ay, 1), "deger": float(deger)})
    return pd.DataFrame(satirlar)


def _pres_sayfa_adi(sayfa):
    s = _sade(sayfa)
    return '6"' if s.startswith("6") else '8"' if s.startswith("8") else "Toplam"


@rapor("uretim_aylik", ("pres", "aylik"))
def pres_aylik(yol):
    return _yil_ay_bloklari(yol, _pres_sayfa_adi)


@rapor("tozboya_aylik", ("toz boya", "aylik"))
def tozboya_aylik(yol):
    return _yil_ay_bloklari(yol, lambda s: "Toz Boya Toplam" if "toplam" in _sade(s) else "Toz Boya")


# ---------------------------------------------------------------------
# Toplam Fire Listesi 2026: ay sayfalarında günlük satırlar. Sayfada bir
# sonraki ayın ilk günü de olabildiği için (DASBORD'daki SUMIFS gibi) her
# sayfadan yalnız kendi ayının günleri alınır.
# ---------------------------------------------------------------------
FIRE_SUTUN = {
    "disari giden arais": "arais", "teorik kullanilan hammadde": "teorik",
    "net kullanilan hammadde": "net", "sepete giren (testere)": "sepete",
    "pres sonrasi atilan hurda (teorik)": "ps_teorik",
    "pres sonrasi atilan hurda (tartim)": "ps_tartim",
    "iade hurda kg (tartim)": "iade", "stok hurda kg (tartim)": "stok",
    "numune hurda kg (tartim)": "numune", "talas kg (tartim)": "talas",
    "hassas kesim": "hassas", "hammadde sayim": "sayim", "gelen hammadde": "gelen",
    "boyahane/eloksal kantar fisi": "boya_kantar", "sevkiyat kantar fisi": "sevk_kantar",
    "hammadde tartim kantar (kg)": "ham_kantar", "rampa (kg)": "rampa",
    "net kullanilan hammadde (kantara gore)": "net_kantar",
    "arais tartim (kantara gore)": "arais_kantar",
}
FIRE_DEGER = [c for c in FIRE_SUTUN.values() if c != "sayim"]
# Fire listesi bu tarihten itibaren bizim; önceki ay sayfaları (Ocak–Mayıs
# 2026, Excel'de gizli) eski rapora ait, rapora alınmaz.
FIRE_BASLANGIC = pd.Timestamp(2026, 6, 1)


@rapor("fire", ("fire listesi",))
def fire_gunluk(yol):
    parcalar = []
    for sayfa in pd.ExcelFile(yol).sheet_names:
        s = re.sub(r"\s+", " ", _sade(sayfa))
        m = re.fullmatch(r"([a-z]+) (20\d\d)", s)
        if not m or not _ay_no(m.group(1)):
            continue
        d = pd.read_excel(yol, sheet_name=sayfa)
        d.columns = [re.sub(r"\s+", " ", _sade(c)) for c in d.columns]
        d = d.rename(columns={"tarih": "tarih", **FIRE_SUTUN})
        d = d[["tarih"] + [c for c in FIRE_SUTUN.values() if c in d.columns]].copy()
        d["tarih"] = pd.to_datetime(d["tarih"], errors="coerce")
        ay, yil = _ay_no(m.group(1)), int(m.group(2))
        d = d[(d["tarih"].dt.month == ay) & (d["tarih"].dt.year == yil)]
        for c in d.columns[1:]:
            d[c] = pd.to_numeric(d[c], errors="coerce")
        parcalar.append(d)
    if not parcalar:
        return pd.DataFrame(columns=["tarih"] + list(FIRE_SUTUN.values()))
    d = pd.concat(parcalar, ignore_index=True)
    d = d[d["tarih"] >= FIRE_BASLANGIC]
    for c in FIRE_SUTUN.values():
        if c not in d.columns:
            d[c] = float("nan")
    # Kayıt girilmiş günler: hammadde ya da testere değeri olanlar
    d["kayitli"] = d[["teorik", "net", "sepete"]].notna().any(axis=1)
    d[FIRE_DEGER] = d[FIRE_DEGER].fillna(0)
    return (d.drop_duplicates("tarih", keep="last").sort_values("tarih")
            .reset_index(drop=True))


def fire_ozet(t):
    """Bir dönemin toplamları ve Excel'deki fire oranları (net kullanılan
    hammaddeye göre). Toplam kantar hurdasında Excel'deki 'LK/IM' sütun
    hatası düzeltilmiş olarak talaş da sayılır."""
    s = t[FIRE_DEGER].sum()
    net = s["net"] if s["net"] else None
    s["pres_hurda"] = s["net"] - s["sepete"]
    s["ps_hurda"] = s["ps_tartim"] + s["iade"] + s["stok"]
    s["toplam_hurda"] = (s["pres_hurda"] + s["ps_tartim"] + s["iade"] + s["stok"]
                         + s["numune"] + s["talas"] + s["hassas"])
    oran = lambda v: v / net if net else None
    s["pres_fire"] = oran(s["pres_hurda"])
    s["ps_fire"] = oran(s["ps_hurda"])
    s["toplam_fire"] = (s["pres_fire"] + s["ps_fire"]) if net else None
    s["fabrika_fire"] = oran(s["arais"])
    s["teorik_fire"] = (s["teorik"] - s["sepete"]) / s["teorik"] if s["teorik"] else None
    s["fark"] = s["toplam_hurda"] - s["arais"]
    s["gun"] = int(t.loc[t["kayitli"], "tarih"].nunique()) if "kayitli" in t else 0
    return s


# ---------------------------------------------------------------------
# Enerji Sarfiyatlar 2026: sayfalarda '2026 | OCAK ... ARALIK' başlıklı
# bloklar (bazı sayfalarda iki blok yan yana). Her kalem blok başlığı ve
# satır etiketiyle bulunur; türetilen göstergeler enerji_ozet'te Excel'deki
# formüllerle hesaplanır.
# ---------------------------------------------------------------------
def _ay_bloklari(d):
    """(blok başlığı, etiket, {ay: değer}) listesi."""
    cikti = []
    for i in range(len(d)):
        aylar = {j: _ay_no(v) for j, v in d.iloc[i].items() if isinstance(v, str) and _ay_no(v)}
        if len(aylar) < 6:
            continue
        sutunlar = sorted(aylar)
        parcalar, parca = [], [sutunlar[0]]
        for j in sutunlar[1:]:
            if j == parca[-1] + 1:
                parca.append(j)
            else:
                parcalar.append(parca)
                parca = [j]
        parcalar.append(parca)
        for parca in parcalar:
            etiket_sut = parca[0] - 1
            if etiket_sut < 0:
                continue
            baslik = ""
            for geri in (1, 2):
                if i - geri >= 0 and isinstance(d.iat[i - geri, etiket_sut], str):
                    baslik = d.iat[i - geri, etiket_sut]
                    break
            for k in range(i + 1, min(i + 25, len(d))):
                etiket = d.iat[k, etiket_sut]
                if not isinstance(etiket, str):
                    break
                degerler = {aylar[j]: pd.to_numeric(d.iat[k, j], errors="coerce") for j in parca}
                cikti.append((baslik, etiket, degerler))
    return cikti


# (sayfa başı, blok başlığında geçen, etikette geçen, sütun adı): ilk eşleşen alınır
ENERJI_KALEM = [
    ('6" pres', "elektrik tuketimi kompresor", "tuketim miktari", "p6_komp_kwh"),
    ('6" pres', "elektrik tuketimi kompresor", "calisma saati", "p6_komp_saat"),
    ('6" pres', "elektrik tuketimi", "tuketim miktari", "p6_kwh"),
    ('6" pres', "elektrik tuketimi", "kullanilan hammadde", "p6_hammadde"),
    ('6" pres', "dogalgaz", "tuketim miktari", "p6_gaz"),
    ('8" pres', "elektrik tuketimi kompresor", "tuketim miktari", "p8_komp_kwh"),
    ('8" pres', "elektrik tuketimi kompresor", "calisma saati", "p8_komp_saat"),
    ('8" pres', "elektrik tuketimi", "tuketim miktari", "p8_kwh"),
    ('8" pres', "elektrik tuketimi", "kullanilan hammadde", "p8_hammadde"),
    ('8" pres', "dogalgaz", "tuketim miktari", "p8_gaz"),
    ("termikler", "termik", "dogalgaz tuketimi m3", "termik_gaz"),
    ("termikler", "termik", "uretim kg", "termik_uretim"),
    ("boyahane", "dogalgaz", "dogalgaz tuketimi m3", "boya_gaz"),
    ("boyahane", "dogalgaz", "boyahane uretim", "boya_uretim"),
    ("boyahane", "elektrik", "tuketim miktari", "boya_kwh"),
    ("toplam", "profil imalat elektrik", "fabrika tuketim miktari", "fab_kwh"),
    ("toplam", "profil imalat elektrik", "ana pano", "ana_pano_kwh"),
    ("toplam", "profil imalat elektrik", "kompresor ana hat", "komp_ana_hat_kwh"),
    ("toplam", "profil imalat elektrik", "kompresor tuketim", "komp_kwh"),
    ("toplam", "profil imalat elektrik", "fatura bedeli", "fab_elk_tl"),
    ("toplam", "profil imalat elektrik", "presler aylik uretim", "pres_uretim"),
    ("toplam", "boyahane dogalgaz", "fabrika tuketim miktari", "fab_gaz_m3"),
    ("toplam", "boyahane dogalgaz", "odenen dogalgaz", "fab_gaz_tl"),
    ("toplam", "profil+termik", "dolar kuru", "dolar"),
]


@rapor("enerji", ("sarfiyat",))
def enerji(yol):
    """Aylık enerji tablosu: her satır bir ay, sütunlar ENERJI_KALEM adları."""
    yil = int((re.findall(r"20\d\d", Path(yol).name) or [2026])[0])
    veri_ = {}
    for sayfa in pd.ExcelFile(yol).sheet_names:
        s = _sade(sayfa)
        if any(k in s for k in ("dashboard", "veriler", "kcal", "eloksal")):
            continue
        bloklar = _ay_bloklari(pd.read_excel(yol, sheet_name=sayfa, header=None))
        for sayfa_k, blok_k, etiket_k, ad in ENERJI_KALEM:
            if ad in veri_ or not s.startswith(sayfa_k):
                continue
            for baslik, etiket, degerler in bloklar:
                if blok_k in _sade(baslik) and etiket_k in _sade(etiket):
                    veri_[ad] = degerler
                    break
    if not veri_:
        return pd.DataFrame()
    d = pd.DataFrame(veri_).sort_index()
    d.index.name = "ay_no"
    d = d.reset_index()
    d.insert(0, "tarih", [pd.Timestamp(yil, int(a), 1) for a in d["ay_no"]])
    for _, _, _, ad in ENERJI_KALEM:
        if ad not in d:
            d[ad] = float("nan")
    # Girilmiş aylar: fabrika ya da pres elektrik tüketimi olanlar
    d = d[d[["fab_kwh", "p6_kwh", "p8_kwh"]].fillna(0).sum(axis=1) > 0]
    return d.drop(columns="ay_no").reset_index(drop=True)


def enerji_ozet(t):
    """Bir dönemin toplamları ve türetilmiş göstergeler. Oranlar dönem
    toplamlarından hesaplanır (aylık oranların ortalaması değil); TL→$
    çevrimi her ayın kendi kuruyla yapılır. Bölüm faturası = bölüm tüketimi ×
    fabrika ortalama birim fiyatı (Excel'deki dağılım oranı yöntemiyle aynı)."""
    t = t.copy()
    sifir = lambda c: t[c].fillna(0)
    t["pres_kwh"] = sifir("p6_kwh") + sifir("p8_kwh")
    t["prese_ait_kwh"] = sifir("ana_pano_kwh") - sifir("komp_ana_hat_kwh") + sifir("komp_kwh")
    t["elk_birim_ay"] = (t["fab_elk_tl"] / t["fab_kwh"]).where(t["fab_kwh"] > 0)
    t["gaz_birim_ay"] = (t["fab_gaz_tl"] / t["fab_gaz_m3"]).where(t["fab_gaz_m3"] > 0)
    t["pres_elk_tl"] = t["prese_ait_kwh"] * t["elk_birim_ay"]
    t["boya_elk_tl"] = sifir("boya_kwh") * t["elk_birim_ay"]
    t["pres_gaz"] = sifir("p6_gaz") + sifir("p8_gaz") + sifir("termik_gaz")
    t["pres_gaz_tl"] = t["pres_gaz"] * t["gaz_birim_ay"]
    t["boya_gaz_tl"] = sifir("boya_gaz") * t["gaz_birim_ay"]
    for c in ("pres_elk_tl", "boya_elk_tl", "pres_gaz_tl", "boya_gaz_tl", "fab_elk_tl", "fab_gaz_tl"):
        t[c.replace("_tl", "_usd")] = t[c] / t["dolar"]
    toplam = t.drop(columns=["elk_birim_ay", "gaz_birim_ay"]).sum(numeric_only=True, min_count=1)
    s = {k: (None if pd.isna(v) else float(v)) for k, v in toplam.items()}

    def oran(a, b, k=1000.0):
        return s[a] / s[b] * k if s.get(a) is not None and s.get(b) else None

    s.update({
        "ay": int(len(t)),
        "p6_kwh_ton": oran("p6_kwh", "p6_hammadde"), "p8_kwh_ton": oran("p8_kwh", "p8_hammadde"),
        "p6_gaz_ton": oran("p6_gaz", "p6_hammadde"), "p8_gaz_ton": oran("p8_gaz", "p8_hammadde"),
        "termik_gaz_ton": oran("termik_gaz", "termik_uretim"),
        "pres_kwh_ton": oran("pres_kwh", "pres_uretim"),
        "hat_kwh_ton": oran("prese_ait_kwh", "pres_uretim"),
        "pres_gaz_ton": oran("pres_gaz", "pres_uretim"),
        "boya_kwh_ton": oran("boya_kwh", "boya_uretim"), "boya_gaz_ton": oran("boya_gaz", "boya_uretim"),
        "pres_elk_usd_ton": oran("pres_elk_usd", "pres_uretim"),
        "pres_gaz_usd_ton": oran("pres_gaz_usd", "pres_uretim"),
        "boya_elk_usd_ton": oran("boya_elk_usd", "boya_uretim"),
        "boya_gaz_usd_ton": oran("boya_gaz_usd", "boya_uretim"),
        "elk_birim": oran("fab_elk_tl", "fab_kwh", 1), "gaz_birim": oran("fab_gaz_tl", "fab_gaz_m3", 1),
        "pres_elk_pay": oran("prese_ait_kwh", "fab_kwh", 1),
        "boya_elk_pay": oran("boya_kwh", "fab_kwh", 1),
        "pres_gaz_pay": oran("pres_gaz", "fab_gaz_m3", 1),
        "boya_gaz_pay": oran("boya_gaz", "fab_gaz_m3", 1),
    })
    for bolum in ("pres", "boya"):
        e, g = s[f"{bolum}_elk_usd_ton"], s[f"{bolum}_gaz_usd_ton"]
        s[f"{bolum}_enerji_usd_ton"] = None if e is None and g is None else (e or 0) + (g or 0)
    return s


# ---------------------------------------------------------------------
# Kalıp bazlı baskı kayıtları: pres DASHBOARD dosyasının 'Temiz veri'
# sayfası (her satır bir baskı: kalıp no, piston hızı, brüt/net kg, süre)
# ---------------------------------------------------------------------
@rapor("kalip_kayitlari", ("dashboard",), haric=("enerji", "sarfiyat"))
def kalip_kayitlari(yol):
    return veri.pres_kayitlari(yol).drop(columns=["hafta"], errors="ignore")


# ---------------------------------------------------------------------
# Kalıp raporu ve bakım talepleri: düz tablolar
# ---------------------------------------------------------------------
@rapor("kaliplar", ("kalip rapor",), haric=("ozet", "ydf"))
def kaliplar(yol):
    d = pd.read_excel(yol, sheet_name=0, header=0)
    d.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in d.columns]
    d = d[pd.to_numeric(d.iloc[:, 0], errors="coerce").notna()].copy()
    d = d.loc[:, ~d.columns.str.startswith("Unnamed")]
    kod = next((c for c in d.columns if "KOD" in c.upper()), None)
    if kod:  # numarası verilmiş ama boş satırlar
        d = d[d[kod].notna() & (d[kod].astype(str).str.strip() != "")]
    for c in d.columns:
        if "TARİH" in c.upper() or "TARIH" in _sade(c).upper():
            d[c] = pd.to_datetime(d[c], errors="coerce")
        elif d[c].dtype == object:
            d[c] = d[c].astype("string").str.strip()
    return d.reset_index(drop=True)


@rapor("bakim", ("talep",), haric=())
def bakim(yol):
    d = pd.read_excel(yol, sheet_name=0, header=None)
    satirlar, baslik = [], None
    for _, s in d.iterrows():
        degerler = [v for v in s.tolist()]
        if any(isinstance(v, str) and _sade(v) == "firma" for v in degerler):
            baslik = [re.sub(r"\s+", " ", str(v)).strip() if pd.notna(v) else None for v in degerler]
            continue
        if baslik and pd.notna(s.iloc[baslik.index("Firma")] if "Firma" in baslik else None):
            satirlar.append({b: v for b, v in zip(baslik, degerler) if b})
    t = pd.DataFrame(satirlar)
    if "Tarih" in t:
        t["Tarih"] = pd.to_datetime(t["Tarih"], errors="coerce")
    for c in ("Alac.Tut.", "Euro"):
        if c in t:
            t[c] = pd.to_numeric(t[c], errors="coerce")
    for c in t.columns:
        if t[c].dtype == object:
            t[c] = t[c].astype("string")
    return t
