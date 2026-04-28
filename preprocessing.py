"""
preprocessing.py  –  MMMA Music Dataset Preprocessing Pipeline

Veri boru hattına (pipeline) girmeden önce ham Spotify verilerini temizler:
  1. Şarkı başlıklarından versiyon/remix/feat. meta verilerini siler (regex)
  2. Sanatçı isimlerini düzeltir (search_tag içindeki artist:"..." formatı)
  3. (temiz_başlık + sanatçı) anahtarına göre tekrarlı kayıtları tekilleştirir
  4. [song_id, title, artist] formatında temiz bir CSV üretir

Kullanım:
    python preprocessing.py                              # varsayılan dosya
    python preprocessing.py --input ham.csv
    python preprocessing.py --input ham.csv --output temiz.csv  #ile son durum görülebilir
    python preprocessing.py --preview                    # sadece önizleme
"""

import re
import argparse
import pandas as pd
from pathlib import Path


_VERSION_KEYWORDS = (
    r"radio[\s_-]?edit"
    r"|extended[\s_-](?:mix|version)"
    r"|club[\s_-]mix"
    r"|original[\s_-]mix"
    r"|piano[\s_-]version"
    r"|lp[\s_-]mastered"
    r"|re[\s_-]?recorded|rerecorded"
    r"|film[\s_-]m[üu]zi[gğ]i"
    r"|original[\s_-]soundtrack"
    r"|uzun[\s_-]hava"
    r"|remaster(?:ed)?(?:[\s_-]\d{4})?"
    r"|\bremix\b"
    r"|\bedit\b"
    r"|\bmix\b"
    r"|\bmashup\b"
    r"|\bmedley\b"
    r"|\bacoustic\b|akustik"
    r"|\blive\b"
    r"|\binstrumental\b"
    r"|enstr[üu]man(?:tal)?"
    r"|\bslowed\b"
    r"|\bnightcore\b"
    r"|\bcover\b"
    r"|\bdemo\b"
    r"|\bbonus\b"
    r"|\bdeluxe\b"
    r"|\bstripped\b"
    r"|\bunplugged\b"
    r"|canl[ıi]"
    r"|\bversiyon\b"
    r"|\bgazel\b"
    r"|u\.h\."                   
    r"|\b(?:arr|transc|orch|rek)\.?"
    r"|\bversion\b"
    r"|\bfrom\b"
    r"|\brework\b"
    r"|\bbootleg\b"
    r"|\breprise\b"
    r"|\bacapella\b|a\s+cappella"
    r"|\bvip\b"
    r"|\bdub\b"
    r"|\brebuild\b"
    r"|\bpt\.?\s*\d+"
    r"|\bpart\s+\d+"
    r"|\btake\s+\d+"
)


_VKW_RE = re.compile(
    r"\b(?:" + _VERSION_KEYWORDS + r")\b",
    re.IGNORECASE,
)


_FEAT_PAREN_RE = re.compile(
    r"\s*\(\s*(?:feat\.?|ft\.?|featuring|with|con|met|avec|x)\s+[^)]+\)",
    re.IGNORECASE,
)
_FEAT_BRACKET_RE = re.compile(
    r"\s*\[\s*(?:feat\.?|ft\.?|featuring|with)\s+[^\]]+\]",
    re.IGNORECASE,
)

_PAREN_VER_RE = re.compile(
    r"\s*\([^)]*\b(?:" + _VERSION_KEYWORDS + r")\b[^)]*\)",
    re.IGNORECASE,
)
_BRACKET_VER_RE = re.compile(
    r"\s*\[[^\]]*\b(?:" + _VERSION_KEYWORDS + r")\b[^\]]*\]",
    re.IGNORECASE,
)


_TRAIL_PUNCT_RE = re.compile(r"\s*[-–,;:]+\s*$")
_LEAD_PUNCT_RE  = re.compile(r"^\s*[-–,;:]+\s*")



def clean_title(title: str) -> str:
    """
    Şarkı başlığındaki versiyon/remix/feat. meta verilerini temizler.

    Uygulanan adımlar (sırasıyla):
      1. (feat. X) / [feat. X] gibi performans notasyonlarını sil.
      2. ' - ' ile ayrılmış parçaları kontrol et; versiyon anahtar
         kelimesi içeren ilk parçadan itibaren her şeyi kes.
      3. Kalan parantez / köşeli ayraç içi versiyon etiketlerini sil.
      4. Artık noktalama işaretlerini ve boşlukları temizle.

    Örnekler:
        "Yanmışım - Kivanch K. Remix"   → "Yanmışım"
        "Feel (feat. Sena Sener) - Edit" → "Feel"
        "Sabah İle - Lp Mastered"        → "Sabah İle"
        "Gece Mavisi"                    → "Gece Mavisi"  (değişmez)
    """
    if not isinstance(title, str):
        return ""

    s = title.strip()

    s = _FEAT_PAREN_RE.sub("", s)
    s = _FEAT_BRACKET_RE.sub("", s)

    parts = re.split(r"\s+[-–]\s+", s)
    if len(parts) > 1:
        for i in range(1, len(parts)):
            candidate = " - ".join(parts[i:])
            if _VKW_RE.search(candidate):
                s = " - ".join(parts[:i]).strip()
                break

    s = _PAREN_VER_RE.sub("", s)
    s = _BRACKET_VER_RE.sub("", s)

    s = _TRAIL_PUNCT_RE.sub("", s)
    s = _LEAD_PUNCT_RE.sub("", s)
    s = re.sub(r"\s{2,}", " ", s) 

    return s.strip()


def resolve_artist(artist: str, search_tag: str = "") -> str:
    """
    Sanatçı adını çözümler.

    search_tag içinde artist:"İsim" formatı varsa bu öncelik taşır
    (spotipy_executer.py'daki artist-arama sorgularından gelir).
    Yoksa artist sütununu olduğu gibi kullanır.
    """
    if isinstance(search_tag, str):
        match = re.search(r'artist:\s*"([^"]+)"', search_tag)
        if match:
            return match.group(1).strip()

    return artist.strip() if isinstance(artist, str) else ""


# ANA BORU HATTI (PIPELINE)


def preprocess(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Ham veri setini işleyen tam ön-işleme boru hattı.

    Beklenen sütunlar : song_id, title, artist  (+isteğe bağlı: popularity, search_tag)
    Döndürülen sütunlar: song_id, title, artist  (temizlenmiş ve tekilleştirilmiş)

    Args:
        df      : Ham pandas DataFrame
        verbose : İşlem istatistiklerini konsola yaz

    Returns:
        Temiz DataFrame
    """
    out = df.copy()

   
    for col in ("title", "artist", "search_tag"):
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip().replace("nan", "")

    if "search_tag" in out.columns:
        out["artist"] = out.apply(
            lambda r: resolve_artist(r["artist"], r.get("search_tag", "")),
            axis=1,
        )

    out["title"] = out["title"].map(clean_title)

    before_empty_drop = len(out)
    out = out[(out["title"].str.len() > 0) & (out["artist"].str.len() > 0)]
    empty_dropped = before_empty_drop - len(out)

    dedup_key = (
        out["title"].str.lower().str.strip().str.replace(r"\s+", " ", regex=True)
        + "|||"
        + out["artist"].str.lower().str.strip().str.replace(r"\s+", " ", regex=True)
    )
    before_dedup = len(out)
    out = out[~dedup_key.duplicated(keep="first")]
    dedup_removed = before_dedup - len(out)

    keep_cols = [c for c in ("song_id", "title", "artist") if c in out.columns]
    out = out[keep_cols].reset_index(drop=True)

    if verbose:
        print(f"  Boş/geçersiz satır kaldırıldı  : {empty_dropped}")
        print(f"  Tekilleştirme öncesi            : {before_dedup}")
        print(f"  Tekilleştirme sonrası           : {len(out)}  "
              f"({dedup_removed} tekrar kaldırıldı)")

    return out


def show_preview(df: pd.DataFrame, n: int = 40) -> None:
    """
    Ham başlıklar ile temizlenmiş başlıkları yan yana gösterir.
    Yalnızca değişen satırları listeler.
    """
    if "title" not in df.columns:
        print("[preview] 'title' sütunu bulunamadı.")
        return

    raw_titles   = df["title"].astype(str)
    clean_titles = raw_titles.map(clean_title)
    mask         = raw_titles != clean_titles

    changed = pd.DataFrame({"Ham Başlık": raw_titles[mask], "Temiz Başlık": clean_titles[mask]})
    total   = mask.sum()

    sep = "-" * 95
    print(f"\n{sep}")
    print(f"  {'HAM BASLIK':<58}  {'TEMIZ BASLIK':<33}")
    print(sep)
    for _, row in changed.head(n).iterrows():
        orig  = str(row["Ham Başlık"])[:57]
        clean = str(row["Temiz Başlık"])[:32]
        print(f"  {orig:<58}  {clean:<33}")
    print(sep)
    print(f"  Gosterilen: {min(n, total)} / {total} degistirilmis baslik\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MMMA Müzik Veri Seti Ön-İşleme Aracı",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input", "-i",
        default="MMMA_Massive_Dataset_AutoSave.csv",
        help="Girdi CSV dosya yolu (varsayılan: MMMA_Massive_Dataset_AutoSave.csv)",
    )
    parser.add_argument(
        "--output", "-o",
        default="MMMA_Cleaned.csv",
        help="Çıktı CSV dosya yolu (varsayılan: MMMA_Cleaned.csv)",
    )
    parser.add_argument(
        "--preview", "-p",
        action="store_true",
        help="Yalnızca önizleme yap, dosya kaydetme",
    )
    parser.add_argument(
        "--preview-n",
        type=int,
        default=40,
        help="Önizlemede gösterilecek satır sayısı (varsayılan: 40)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[HATA] Girdi dosyası bulunamadı: {input_path}")
        return

    # Yükleme
    print(f"\n[1/4] Yükleniyor  : {input_path}")
    df_raw = pd.read_csv(input_path, encoding="utf-8")
    print(f"      Boyut        : {df_raw.shape}  sütunlar={df_raw.columns.tolist()}")

    # Önizleme
    print(f"\n[2/4] Başlık önizlemesi (değişen kayıtlar):")
    show_preview(df_raw, n=args.preview_n)

    if args.preview:
        print("[--preview modu] Dosya kaydedilmedi.")
        return

    # Isleme
    print("[3/4] On-isleme basliyor...")
    df_clean = preprocess(df_raw, verbose=True)

    # Kaydetme
    output_path = Path(args.output)
    print(f"\n[4/4] Kaydediliyor : {output_path}")
    df_clean.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"      Toplam kayit  : {len(df_clean)}")

    # Kisa ornek cikti
    sep = "-" * 60
    print(f"\n{sep}")
    print("  Ilk 10 temiz kayit:")
    print(sep)
    print(df_clean.head(10).to_string(index=False))
    print(f"{sep}\n")


if __name__ == "__main__":
    main()
