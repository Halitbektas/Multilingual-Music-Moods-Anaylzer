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
import math
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
KMEANS_CLUSTERS = [
    {"label": "Enerjik Türkçe Pop-Rock", "x": 2, "y": 9},
    {"label": "Global Akustik & Slow", "x": 12, "y": 19},
    {"label": "Hareketli Türkçe Pop", "x": 20, "y": 4},
    {"label": "Modern Türkçe Alternatif", "x": 3, "y": 18},
    {"label": "Duygusal Türkçe Klasikler", "x": 19, "y": 16},
    {"label": "Türkçe Rap & Hip-Hop", "x": 13, "y": 2},
    {"label": "Yüksek Voltaj Global Hits", "x": 4, "y": 2},
    {"label": "Uluslararası Radyo Pop", "x": 11, "y": 10}
]

def generate_dynamic_footnote(audio_features: dict, primary_label: str) -> str:
    if not audio_features:
        return f"{primary_label} tınılarının öne çıktığı dengeli bir yapı."

    tempo = audio_features.get("tempo", 120)
    energy_rms = audio_features.get("energy_rms", 0.5)

    if tempo < 90 and energy_rms < 0.3:
        return "Düşük tempo ve sakin frekansların yarattığı dingin, organik bir yapı."
    elif tempo > 130 and energy_rms > 0.6:
        return "Yüksek BPM ve coşkulu frekanslarla kalp ritmini hızlandıran enerji patlaması."
    elif energy_rms > 0.7:
        return "Modern beat'lerin ve yoğun prodüksiyonun öne çıktığı güçlü bir atmosfer."
    elif tempo < 100:
        return "Yavaş ve derinden ilerleyen, duygusal ağırlığı yüksek bir müzikal iklim."
    else:
        return f"Karmaşık ses katmanlarının {primary_label} ile harmanlandığı hibrit bir deneyim."


def calculate_mood_metrics(song_x: int, song_y: int, audio_features: dict) -> dict:
    """Şarkının SOM üzerindeki konumuna göre Hibrit Duygu yüzdelerini hesaplar."""
    distances = []

    for cluster in KMEANS_CLUSTERS:
        dist = math.sqrt((cluster["x"] - song_x) ** 2 + (cluster["y"] - song_y) ** 2)
        # Sözlük yerine doğrudan Tuple (mesafe, etiket) ekliyoruz. KeyError imkansız hale geliyor.
        distances.append((dist, cluster["label"]))

    # 0. index olan 'dist' (mesafe) değerine göre küçükten büyüğe sırala
    distances.sort(key=lambda item: item[0])

    # En yakın ilk 2 kıtayı al
    dist_1, label_1 = distances[0]
    dist_2, label_2 = distances[1]

    # Yüzdelik Oranları Hesapla (Inverse Distance Weighting)
    if dist_1 == 0:
        pct_1, pct_2 = 100, 0
    else:
        w1 = 1 / dist_1
        w2 = 1 / dist_2
        total_w = w1 + w2
        pct_1 = round((w1 / total_w) * 100)
        pct_2 = round((w2 / total_w) * 100)

    # Yoğunluk (Intensity) Hesaplaması: Merkezden (11,11) ne kadar uzaksa o kadar yoğun
    dist_from_center = math.sqrt((11 - song_x) ** 2 + (11 - song_y) ** 2)
    max_dist = 15.5
    intensity = min(100, round((dist_from_center / max_dist) * 100))

    # Energy_rms değeri varsa yoğunluğa etki etsin
    if audio_features and "energy_rms" in audio_features:
        energy_pct = min(100, audio_features["energy_rms"] * 100)
        intensity = round((intensity * 0.4) + (energy_pct * 0.6))

    return {
        "label": label_1,
        "primary_pct": pct_1,
        "secondary_label": label_2,
        "secondary_pct": pct_2,
        "intensity": intensity,
        "confidence": pct_1,
        "footnote": generate_dynamic_footnote(audio_features, label_1)
    }
# ═════════════════════════════════════════════════════════════════════════════
# Audio features — raw_music_dataset.csv'den oku ve 0-100'e normalize et
# ═════════════════════════════════════════════════════════════════════════════
def _audio_features_for_song(song_id: str) -> AudioFeatures:
    """
    raw_music_data_v2.csv'deki gerçek Librosa çıktılarını (V2) doğrudan Pydantic modeline yollar.
    """
    raw = ml_state.df_raw

    # 1. Hata durumunda (Şarkı bulunamazsa) sistemi çökertmeyecek Varsayılan V2 Değerleri
    default_features = {
        "tempo": 120.0,
        "energy_rms": 0.1,
        "spectral_centroid": 2000.0,
        "mfcc_0": -150.0,
        "mfcc_1": 80.0,
        "mfcc_2": 10.0
    }

    if raw is None or raw.empty or "song_id" not in raw.columns:
        return AudioFeatures(**default_features)

    row = raw[raw["song_id"] == song_id]
    if row.empty:
        return AudioFeatures(**default_features)

    r = row.iloc[0]

    # 2. Proxy (dönüştürme) kullanmadan, Pydantic'in tam olarak beklediği V2 sütunlarını döndürüyoruz
    return AudioFeatures(
        tempo=float(r.get("tempo", default_features["tempo"])),
        energy_rms=float(r.get("energy_rms", default_features["energy_rms"])),
        spectral_centroid=float(r.get("spectral_centroid", default_features["spectral_centroid"])),
        mfcc_0=float(r.get("mfcc_0", default_features["mfcc_0"])),
        mfcc_1=float(r.get("mfcc_1", default_features["mfcc_1"])),
        mfcc_2=float(r.get("mfcc_2", default_features["mfcc_2"]))
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
    """
    Şarkının söz analizlerini döndürür. Pydantic'in istediği language ve word_count eklendi.
    """
    raw = ml_state.df_raw

    # Varsayılan değerler (Sistem çökmesin diye)
    lang = "tr"
    wc = 200

    if raw is not None and not raw.empty and "song_id" in raw.columns:
        row = raw[raw["song_id"] == song_id]
        if not row.empty:
            r = row.iloc[0]
            # Gerçek veri setinde language kolonu varsa al, yoksa "tr" yap
            lang = str(r.get("language", "tr"))
            # word_count kolonu varsa al, yoksa 200 varsay
            wc = int(r.get("word_count", 200))

    return LyricsAnalysis(
        positivity=60,
        emotional_depth=60,
        narrative_tone=60,
        language=lang,  # 🎯 Pydantic'in istediği 1. yeni alan
        word_count=wc  # 🎯 Pydantic'in istediği 2. yeni alan
    )


# ═════════════════════════════════════════════════════════════════════════════
# Confidence — şarkı vektörü ile hücre BMU mesafesine bakar
# ═════════════════════════════════════════════════════════════════════════════


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

        try:
            spotify_meta = spotify_service.get_track_meta(track_id)
        except Exception as e:
            logger.warning(f"Spotify API Kotası Dolu veya Hata (Albüm kapağı yok): {e}")
            spotify_meta = None

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

        try:
            spotify_meta = spotify_service.search_track(req.artist or "", req.song or "")
        except Exception as e:
            logger.warning(f"Spotify API Kotası Dolu veya Hata: {e}")
            spotify_meta = None

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

    # ── 4) Audio + lyrics özellikleri ───────────────────────────────────
    song_id_db = str(db_row["song_id"])
    audio = _audio_features_for_song(song_id_db)
    lyrics = _lyrics_scores_for_song(song_id_db)

    features_dict = audio.dict() if hasattr(audio, "dict") else {}
    mood_data = calculate_mood_metrics(x, y, features_dict)

    # ── 5) Song info — Spotify zenginleştirmesi varsa kullan ────────────
    song_info = SongInfo(
        song_id=song_id_db,
        title=str(db_row["title"]),
        artist=str(db_row["artist"]),
        language=lyrics.language,
        source=source,
        spotify_preview_url=(spotify_meta or {}).get("preview_url"),
        album_art_url=(spotify_meta or {}).get("album_art_url"),
        spotify_url=(spotify_meta or {}).get("external_url"),
    )

    return AnalyzeResponse(
        song=song_info,
        coordinates=Coordinates(x=x, y=y, text=f"({x}, {y})"),
        mood=MoodPrediction(**mood_data),
        audio_features=audio,
        lyrics=lyrics,
    )
