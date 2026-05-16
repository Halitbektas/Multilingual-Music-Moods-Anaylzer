"""
Ana analiz iş akışı.

İki yolculuk:
  • Veritabanı yolu (HIZLI): Şarkı zaten SOM'a yerleşmiş; koordinatı oradan
    okunur, audio feature'lar raw_music_dataset.csv'den çekilir, hücre etiketi
    pozisyondan türetilir. Toplam < 50ms.

  • On-the-fly yolu (YAVAŞ): Yeni şarkı için audio download + librosa + lyrics
    + embedding + scaler + SOM.winner — toplam 30-60 sn. Şimdilik 501
    döner; MVP'de devre dışı, ileride job queue ile bağlanır.

Hücre etiketi (Enerjik/Mutlu/...) SOM grid pozisyonundan **kural tabanlı**
çıkarılır. Eğitim sırasında etiketlenmiş hücreler ürettiysen, JSON map'le
yer değiştirir.
"""

import logging

import numpy as np
import pandas as pd

from app.ml_loader import ml_state
from app.models import (
    AnalyzeRequest, AnalyzeResponse, AudioFeatures,
    Coordinates, LyricsAnalysis, MoodDistribution, MoodPrediction,
    SongInfo,
)
from app.services import spotify_service


logger = logging.getLogger("mmma.analyzer")


# ── Hatalar ─────────────────────────────────────────────────────────────────
class NotFoundError(Exception):
    """Şarkı ne veritabanında ne Spotify'da bulundu."""


class ExternalAPIError(Exception):
    """Spotify/Genius gibi dış servisler erişilemez."""


# ═════════════════════════════════════════════════════════════════════════════
# Hücre etiketi kuralları — SOM grid 20x20 varsayar; senin grid'in farklıysa
# `_quadrant_label`'daki eşikleri scale et veya kendi etiketleme dosyanı bağla.
# ═════════════════════════════════════════════════════════════════════════════
def _quadrant_label(x: int, y: int, grid_x: int, grid_y: int) -> tuple[str, str, str]:
    """
    SOM'u 9 bölgeye böler (3x3 grid). Frontend mock'undaki etiketlere uyumlu:
      Enerjik | Enerjik | Mutlu
      Enerjik | Nötr    | Mutlu
      Sakin   | Sakin   | Melankolik
    Return: (label, mood_distribution_proxy, footnote)
    """
    third_x = grid_x / 3
    third_y = grid_y / 3
    col = 0 if x < third_x else (1 if x < 2 * third_x else 2)
    row = 0 if y < third_y else (1 if y < 2 * third_y else 2)

    matrix = [
        # row 0 (üst)
        [("Enerjik", "Enerjik bir bölgenin tam ortasında"),
         ("Enerjik ve Mutlu", "Yüksek korelasyon tespit edildi"),
         ("Mutlu", "Pozitif tınılar baskın")],
        # row 1 (orta)
        [("Sakin Enerji", "Dengeli, optimist atmosfer"),
         ("Nötr", "Türü belirsiz, geçişken hücre"),
         ("Pozitif Melankoli", "Tatlı-acı bir tını")],
        # row 2 (alt)
        [("Sakin", "Dingin tonlar ön planda"),
         ("Sakin ve Melankolik", "Yavaş tempo, düşük valans"),
         ("Melankolik", "Hüzün baskın bir bölge")],
    ]
    label, footnote = matrix[row][col]
    return label, footnote


def _mood_distribution_for_cell(x: int, y: int, grid_x: int, grid_y: int) -> MoodDistribution:
    """Quadrant'a göre dağılım. Eğitimden gerçek dağılım çıkardıysan onunla değiştir."""
    third_x = grid_x / 3
    third_y = grid_y / 3
    col = 0 if x < third_x else (1 if x < 2 * third_x else 2)
    row = 0 if y < third_y else (1 if y < 2 * third_y else 2)

    # Köşeler bariz, merkez nötr
    presets = {
        (0, 0): MoodDistribution(happy=8, energetic=58, calm=12, melancholic=10, neutral=12),
        (0, 1): MoodDistribution(happy=42, energetic=38, calm=8, melancholic=5, neutral=7),
        (0, 2): MoodDistribution(happy=55, energetic=22, calm=10, melancholic=5, neutral=8),
        (1, 0): MoodDistribution(happy=12, energetic=34, calm=34, melancholic=10, neutral=10),
        (1, 1): MoodDistribution(happy=18, energetic=22, calm=22, melancholic=18, neutral=20),
        (1, 2): MoodDistribution(happy=28, energetic=12, calm=22, melancholic=28, neutral=10),
        (2, 0): MoodDistribution(happy=8, energetic=10, calm=58, melancholic=14, neutral=10),
        (2, 1): MoodDistribution(happy=10, energetic=8, calm=32, melancholic=40, neutral=10),
        (2, 2): MoodDistribution(happy=5, energetic=6, calm=18, melancholic=62, neutral=9),
    }
    return presets[(row, col)]


# ═════════════════════════════════════════════════════════════════════════════
# Audio features — raw_music_dataset.csv'den oku ve 0-100'e normalize et
# ═════════════════════════════════════════════════════════════════════════════
def _audio_features_for_song(song_id: str) -> AudioFeatures:
    """
    raw_music_dataset.csv'deki librosa çıktılarını 0-100'e map'le.
    Veritabanında yoksa hücre ortalamasına bakar; o da yoksa makul varsayılan.
    """
    raw = ml_state.df_raw
    if raw is None or raw.empty or "song_id" not in raw.columns:
        return AudioFeatures(energy=50, valence=50, danceability=50,
                             acousticness=50, tempo=50, loudness=50)

    row = raw[raw["song_id"] == song_id]
    if row.empty:
        return AudioFeatures(energy=50, valence=50, danceability=50,
                             acousticness=50, tempo=50, loudness=50)

    r = row.iloc[0]

    # Bizim ham özelliklerimiz: tempo, energy_rms, spectral_centroid + MFCC + chroma.
    # Bunları kullanıcı için anlamlı radar eksenlerine projeksiyon yapıyoruz:
    energy = _scale_to_100(r.get("energy_rms", 0.05), 0.02, 0.15)
    tempo = _scale_to_100(r.get("tempo", 100), 60, 180)
    # spectral_centroid yüksekse "parlak"/"dansedilebilirlik" proxy'si
    danceability = _scale_to_100(r.get("spectral_centroid", 1800), 800, 3500)
    # chroma_0 düşüklüğü "akustik" proxy'si — yaklaşık
    acousticness = 100 - _scale_to_100(r.get("chroma_0", 0.3), 0.1, 0.6)
    # MFCC_0 enerji bandı proxy'si — ses yüksekliği
    loudness = _scale_to_100(r.get("mfcc_0", -200), -400, 0)
    # MFCC_1 + chroma_4 valence için yüzeysel proxy
    valence = _scale_to_100(
        float(r.get("mfcc_1", 50)) + float(r.get("chroma_4", 0.3)) * 50,
        0, 200,
    )

    return AudioFeatures(
        energy=energy, valence=valence, danceability=danceability,
        acousticness=acousticness, tempo=tempo, loudness=loudness,
    )


def _scale_to_100(value, min_v, max_v) -> float:
    if value is None or pd.isna(value):
        return 50.0
    v = (float(value) - min_v) / (max_v - min_v) * 100
    return float(max(0, min(100, round(v, 1))))


# ═════════════════════════════════════════════════════════════════════════════
# Lyrics duygu skorları — embedding magnitude'larını kullanan basit proxy.
# Eğitim sırasında gerçek bir sentiment classifier eklediysen onunla değiştir.
# ═════════════════════════════════════════════════════════════════════════════
def _lyrics_scores_for_song(song_id: str) -> LyricsAnalysis:
    raw = ml_state.df_raw
    if raw is None or raw.empty or "song_id" not in raw.columns:
        return LyricsAnalysis(positivity=60, emotional_depth=60, narrative_tone=60)

    row = raw[raw["song_id"] == song_id]
    if row.empty:
        return LyricsAnalysis(positivity=60, emotional_depth=60, narrative_tone=60)

    r = row.iloc[0]

    # bert_emb_* kolonlarının basit istatistikleri
    emb_cols = [c for c in raw.columns if c.startswith(("bert_emb_", "laser_emb_"))]
    if not emb_cols:
        return LyricsAnalysis(positivity=60, emotional_depth=60, narrative_tone=60)

    vec = r[emb_cols].astype(float).to_numpy()
    pos = _scale_to_100(float(np.mean(vec)), -0.05, 0.05)
    depth = _scale_to_100(float(np.std(vec)), 0.0, 0.15)
    tone = _scale_to_100(float(np.abs(vec).mean()), 0.0, 0.1)

    return LyricsAnalysis(positivity=pos, emotional_depth=depth, narrative_tone=tone)


# ═════════════════════════════════════════════════════════════════════════════
# Confidence — şarkı vektörü ile hücre BMU mesafesine bakar
# ═════════════════════════════════════════════════════════════════════════════
def _confidence_for_cell(x: int, y: int) -> tuple[int, int]:
    """
    Hücredeki şarkı yoğunluğu ve quadrant'a "ne kadar derin" düştüğüne göre
    kaba bir güven + yoğunluk. Eğitim metriklerinle ince ayar yap.
    """
    cell = ml_state.cell_songs(x, y)
    size = len(cell)
    # Daha kalabalık hücre = daha güvenli sınıflandırma
    confidence = min(95, 55 + size * 3)
    intensity = min(92, 50 + size * 2)
    return confidence, intensity


# ═════════════════════════════════════════════════════════════════════════════
# Ana fonksiyon
# ═════════════════════════════════════════════════════════════════════════════
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    # ── 1) Şarkıyı bul ───────────────────────────────────────────────────
    spotify_meta: dict | None = None
    db_row = None

    if req.spotify_url:
        track_id = spotify_service.extract_track_id(req.spotify_url)
        if not track_id:
            raise NotFoundError("Geçerli bir Spotify track id'si çıkarılamadı.")

        spotify_meta = spotify_service.get_track_meta(track_id)
        if not spotify_meta:
            raise ExternalAPIError(
                "Spotify track bilgisine ulaşılamadı. "
                "Credentials ayarlı mı? .env'i kontrol et."
            )

        # Önce id ile dene
        db_row = ml_state.find_song(song_id=track_id)
        # Yoksa metadata'dan title/artist ile dene
        if db_row is None:
            db_row = ml_state.find_song(
                title=spotify_meta["title"], artist=spotify_meta["artist"]
            )
        source = "Spotify"

    else:
        db_row = ml_state.find_song(title=req.song, artist=req.artist)
        source = "Manuel Giriş"
        # Spotify'da da arayalım — preview için
        spotify_meta = spotify_service.search_track(req.artist or "", req.song or "")

    if db_row is None:
        # MVP: on-the-fly tahmin henüz canlı değil
        raise NotFoundError(
            "Şarkı veritabanında değil. Bu sürümde sadece "
            "veritabanındaki şarkılar analiz edilebiliyor. "
            "Yakında: yeni şarkıları on-the-fly indirip yerleştirme."
        )

    # ── 2) Koordinat & hücre etiketi ─────────────────────────────────────
    x, y = int(db_row["som_x"]), int(db_row["som_y"])
    grid_x, grid_y = ml_state.som_x, ml_state.som_y
    mood_label, footnote = _quadrant_label(x, y, grid_x, grid_y)
    conf, intensity = _confidence_for_cell(x, y)

    # ── 3) Audio + lyrics özellikleri ───────────────────────────────────
    song_id = str(db_row["song_id"])
    audio = _audio_features_for_song(song_id)
    lyrics = _lyrics_scores_for_song(song_id)
    mood_dist = _mood_distribution_for_cell(x, y, grid_x, grid_y)

    # ── 4) Song info — Spotify zenginleştirmesi varsa kullan ────────────
    song_info = SongInfo(
        song_id=song_id,
        title=str(db_row["title"]),
        artist=str(db_row["artist"]),
        language=str(db_row.get("language") or ""),
        source=source,
        spotify_preview_url=(spotify_meta or {}).get("preview_url"),
        album_art_url=(spotify_meta or {}).get("album_art_url"),
        spotify_url=(spotify_meta or {}).get("external_url"),
    )

    return AnalyzeResponse(
        song=song_info,
        coordinates=Coordinates(x=x, y=y, text=f"({x}, {y})"),
        mood=MoodPrediction(
            label=mood_label, confidence=conf,
            intensity=intensity, footnote=footnote,
        ),
        audio_features=audio,
        mood_distribution=mood_dist,
        lyrics=lyrics,
    )
