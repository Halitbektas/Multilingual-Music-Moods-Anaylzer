"""
Bir hücredeki tüm şarkıların temizlenmiş şarkı sözlerinden kelime bulutu üretir.

raw_music_dataset.csv'de doğrudan `clean_lyrics` kolonu olmayabilir (bizim
mevcut pipeline embedding'leri tutuyor). Bu durumda Genius'tan tekrar çekmek
çok pahalı — bu yüzden ya:
  (a) Önişleme adımında clean_lyrics kolonu eklenir (önerilen)
  (b) Endpoint, yoksa boş döner — frontend zarif degrade olur

Burada (a) varsayımı altında çalışır; clean_lyrics kolonu yoksa boş döner.
"""

import logging
import re
from collections import Counter

from app.ml_loader import ml_state
from app.models import Coordinates, WordCloudResponse, WordFrequency


logger = logging.getLogger("mmma.wordcloud")


# ── Türkçe + İngilizce stopwords (genişletilmiş) ────────────────────────────
TR_STOP = {
    "acaba", "altı", "altmış", "ama", "ancak", "arada", "artık", "asla",
    "az", "bana", "bazen", "bazı", "bazıları", "belki", "ben", "benden",
    "beni", "benim", "beş", "bile", "bin", "bir", "birçok", "biri",
    "birkaç", "birşey", "biz", "bizden", "bize", "bizi", "bizim", "böyle",
    "böylece", "bu", "buna", "bunda", "bundan", "bunu", "bunun", "burada",
    "bütün", "çoğu", "çok", "çünkü", "da", "daha", "de", "değil", "demek",
    "diğer", "diğeri", "diye", "doksan", "dokuz", "dolayı", "dolayısıyla",
    "dört", "edecek", "eden", "ederek", "edilen", "ediliyor", "edip",
    "ediyor", "eğer", "elli", "en", "etmek", "etti", "ettiği", "ettiğini",
    "eylül", "fakat", "falan", "filan", "gene", "gibi", "göre", "gün",
    "halen", "hangi", "hatta", "hem", "henüz", "hep", "hepsi", "her",
    "herhangi", "herkes", "hiç", "hiçbir", "için", "iki", "ile", "ilgili",
    "ise", "işte", "itibaren", "kadar", "katrilyon", "kendi", "kendine",
    "kez", "ki", "kim", "kimi", "kimse", "kırk", "milyar", "milyon",
    "mu", "mı", "mi", "nasıl", "ne", "neden", "nedenle", "nerde", "nerede",
    "nereye", "niçin", "niye", "o", "olan", "olarak", "oldu", "olduğu",
    "olduğunu", "olduklarını", "olmadı", "olmadığı", "olmak", "olması",
    "olmayan", "olmaz", "olsa", "olsun", "olup", "olur", "olursa",
    "oluyor", "on", "ona", "ondan", "onlar", "onlardan", "onları", "onların",
    "onu", "onun", "otuz", "oysa", "öyle", "pek", "rağmen", "sana", "sanki",
    "sekiz", "seksen", "sen", "senden", "seni", "senin", "siz", "sizden",
    "sizi", "sizin", "şey", "şeyden", "şeyi", "şeyler", "şimdi", "şöyle",
    "şu", "şuna", "şunda", "şundan", "şunu", "tarafından", "trilyon", "tüm",
    "üç", "üzere", "var", "vardı", "ve", "veya", "ya", "yani", "yapacak",
    "yapılan", "yapılması", "yapıyor", "yapmak", "yaptı", "yaptığı",
    "yaptığını", "yedi", "yerine", "yetmiş", "yine", "yirmi", "yoksa", "yüz",
    "zaten", "i̇şte", "yok", "var",
}

EN_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if",
    "in", "into", "is", "it", "no", "not", "of", "on", "or", "such", "that",
    "the", "their", "then", "there", "these", "they", "this", "to", "was",
    "will", "with", "i", "you", "me", "my", "your", "we", "he", "she", "him",
    "her", "his", "hers", "all", "so", "do", "did", "does", "have", "has",
    "had", "been", "being", "am", "were", "what", "when", "where", "who",
    "why", "how", "from", "up", "down", "out", "about", "ll", "ve", "re", "s",
    "t", "d", "m", "o", "y", "just", "now", "can", "could", "would", "should",
    "yeah", "oh", "ah", "la", "na", "mmm", "uh", "got", "get", "go", "going",
    "gonna", "wanna", "ya",
}

STOP = TR_STOP | EN_STOP


# Kelime ayırıcı — Türkçe karakter güvenli
_WORD_RE = re.compile(r"[a-zA-ZçÇğĞıİöÖşŞüÜ]+", re.UNICODE)


def compute_from_text(text: str, top_n: int = 60) -> list[WordFrequency]:
    """Tek bir şarkı sözü metninden kelime frekansı listesi döner."""
    counter: Counter[str] = Counter()
    for tok in _WORD_RE.findall(text.lower()):
        if len(tok) <= 2:
            continue
        if tok in STOP:
            continue
        counter[tok] += 1
    return [WordFrequency(word=w, weight=c) for w, c in counter.most_common(top_n)]


def compute(x: int, y: int, top_n: int = 60) -> WordCloudResponse:
    db = ml_state.df_db
    raw = ml_state.df_raw

    cell = db[(db["som_x"] == x) & (db["som_y"] == y)]

    if (raw is None or raw.empty
            or "clean_lyrics" not in raw.columns
            or "song_id" not in raw.columns):
        logger.warning(
            "clean_lyrics kolonu yok. WordCloud için raw_music_dataset.csv'ye "
            "lyrics'leri eklemen lazım (lyrics_pipeline.clean_lyrics çıktısı)."
        )
        return WordCloudResponse(
            cell=Coordinates(x=x, y=y, text=f"({x}, {y})"),
            songs_aggregated=0,
            words=[],
        )

    song_ids = set(cell["song_id"].astype(str))
    cell_lyrics = raw[raw["song_id"].astype(str).isin(song_ids)]["clean_lyrics"]

    if cell_lyrics.empty:
        return WordCloudResponse(
            cell=Coordinates(x=x, y=y, text=f"({x}, {y})"),
            songs_aggregated=0,
            words=[],
        )

    counter: Counter[str] = Counter()
    for text in cell_lyrics.dropna().astype(str):
        for tok in _WORD_RE.findall(text.lower()):
            if len(tok) <= 2:
                continue
            if tok in STOP:
                continue
            counter[tok] += 1

    most = counter.most_common(top_n)
    words = [WordFrequency(word=w, weight=c) for w, c in most]

    return WordCloudResponse(
        cell=Coordinates(x=x, y=y, text=f"({x}, {y})"),
        songs_aggregated=len(cell_lyrics),
        words=words,
    )
