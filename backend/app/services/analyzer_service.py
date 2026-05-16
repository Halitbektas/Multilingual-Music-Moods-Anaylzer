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
    Coordinates, LyricsAnalysis, MoodPrediction,
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
    track_id = None # track_id'yi scope dışında da kullanabilmek için başta tanımlıyoruz

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
        source = "database" # Önceden "Spotify" idi, DB'den geldiğini netleştirmek daha iyi olabilir

    else:
        db_row = ml_state.find_song(title=req.song, artist=req.artist)
        source = "database"
        # Spotify'da da arayalım — preview için
        spotify_meta = spotify_service.search_track(req.artist or "", req.song or "")

    # ── 2) VERİTABANINDA YOKSA: ON-THE-FLY ANALİZ BAŞLAT ─────────────────
    if db_row is None:
        logger.info(f"Şarkı veritabanında bulunamadı. Anlık analiz başlatılıyor...")
        
        # DÖNGÜSEL İÇE AKTARMAYI ENGELLEMEK İÇİN İMPORTU BURADA YAPIYORUZ
        from app.services import new_song_service 
        
        # Meta verilerini toparla (Spotify URL'den gelmemişse req içinden al)
        actual_title = spotify_meta["title"] if spotify_meta else req.song
        actual_artist = spotify_meta["artist"] if spotify_meta else req.artist
        
        # Hata fırlatmak yerine doğrudan yeni servise yönlendirip dönen sonucu API'ye iletiyoruz
        return new_song_service.analyze_new_song_on_the_fly(
            song_id=track_id,
            title=actual_title,
            artist=actual_artist,
            spotify_url=req.spotify_url
        )
        # Hata fırlatmak yerine doğrudan yeni servise yönlendirip dönen sonucu API'ye iletiyoruz
        

    # ── 3) VERİTABANINDA VARSA: MEVCUT HIZLI AKIŞTAN DEVAM ET ────────────
    x, y = int(db_row["som_x"]), int(db_row["som_y"])
    grid_x, grid_y = ml_state.som_x, ml_state.som_y
    mood_label, footnote = _quadrant_label(x, y, grid_x, grid_y)
    conf, intensity = _confidence_for_cell(x, y)

    # ── 4) Audio + lyrics özellikleri ───────────────────────────────────
    song_id_db = str(db_row["song_id"])
    audio = _audio_features_for_song(song_id_db)
    lyrics = _lyrics_scores_for_song(song_id_db)

    # ── 5) Song info — Spotify zenginleştirmesi varsa kullan ────────────
    song_info = SongInfo(
        song_id=song_id_db,
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
        lyrics=lyrics,
    )
