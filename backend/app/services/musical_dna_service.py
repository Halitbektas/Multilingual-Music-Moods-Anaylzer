"""
Müzikal DNA — şarkının ham audio özelliklerini, BULUNDUĞU hücredeki diğer
şarkıların ortalamasıyla yan yana koyar. Frontend bunu çift-eksenli bir
radar grafiği olarak çizer.

"Şarkın hücreye %X uyuyor" hissini birebir verir.
"""

import numpy as np
import pandas as pd

from app.ml_loader import ml_state
from app.models import Coordinates, DNAEntry, MusicalDNAResponse, SongInfo
from app.services import spotify_service


class NotFoundError(Exception):
    pass


# ── Hangi feature'lar radar üzerinde gösterilecek ───────────────────────────
RADAR_FEATURES = [
    # (display_name, raw_csv_column, scale_min, scale_max)
    ("Enerji",            "energy_rms",        0.02, 0.15),
    ("Tempo",             "tempo",             60,   180),
    ("Spektral Parlaklık","spectral_centroid", 800,  3500),
    ("MFCC Profili",      "mfcc_0",            -400, 0),
    ("Tını (MFCC-1)",     "mfcc_1",             0,   200),
    ("Renk (Chroma-4)",   "chroma_4",           0.05, 0.6),
]


def _scale(v, lo, hi) -> float:
    if v is None or pd.isna(v):
        return 50.0
    scaled = (float(v) - lo) / (hi - lo) * 100
    return float(max(0, min(100, round(scaled, 1))))


def compute(song_id: str) -> MusicalDNAResponse:
    db = ml_state.df_db
    raw = ml_state.df_raw

    x, y = None, None
    song_info_data = None
    song_audio_data = None
    is_on_the_fly = False

    # 1. Önce Runtime Cache'e (Anlık analiz edilen şarkılar) bak
    if hasattr(ml_state, 'runtime_songs') and song_id in ml_state.runtime_songs:
        cached_song = ml_state.runtime_songs[song_id]
        x, y = cached_song["som_x"], cached_song["som_y"]
        song_info_data = cached_song
        song_audio_data = cached_song["audio_features"]
        is_on_the_fly = True

    # 2. Eğer cache'te yoksa Veritabanı (df_db) içinde ara
    elif db is not None and not db.empty:
        hit = db[db["song_id"] == song_id]
        if not hit.empty:
            row = hit.iloc[0]
            x, y = int(row["som_x"]), int(row["som_y"])
            
            # DB'den spotify servisi ile zenginleştirilmiş data al
            meta = spotify_service.enrich_song_row(row)
            song_info_data = {
                "song_id": str(row["song_id"]),
                "title": str(row["title"]),
                "artist": str(row["artist"]),
                "language": str(row.get("language") or ""),
                "spotify_preview_url": meta.get("spotify_preview_url"),
                "album_art_url": meta.get("album_art_url"),
                "spotify_url": meta.get("spotify_url"),
            }
            
            if raw is not None and not raw.empty:
                song_raw = raw[raw["song_id"] == song_id]
                if not song_raw.empty:
                    song_audio_data = song_raw.iloc[0].to_dict()

    if song_info_data is None:
        raise NotFoundError(f"Şarkı veritabanında veya aktif bellekte bulunamadı: {song_id}")

    # Hücredeki DB şarkılarını bul (Hücre ortalaması için)
    cell_song_ids = []
    if db is not None and not db.empty:
        cell_song_ids = db[(db["som_x"] == x) & (db["som_y"] == y)]["song_id"].tolist()
    
    cell_raw = pd.DataFrame()
    if raw is not None and not raw.empty:
        cell_raw = raw[raw["song_id"].isin(cell_song_ids)]

    # 3. DNA Özelliklerini Hesapla
    dna: list[DNAEntry] = []
    for name, col, lo, hi in RADAR_FEATURES:
        
        # Şarkı değeri (Hem runtime dict'ten hem raw_df dict'ten gelebilir)
        song_val = song_audio_data.get(col) if song_audio_data else None
        
        # Hücre ortalaması (Sadece DB'deki şarkılardan hesaplanır)
        cell_val = cell_raw[col].mean() if not cell_raw.empty and col in cell_raw.columns else None

        dna.append(DNAEntry(
            feature=name,
            song_value=_scale(song_val, lo, hi),
            cell_average=_scale(cell_val, lo, hi),
        ))

    # 4. Response modelini oluştur
    song_info_model = SongInfo(
        song_id=song_info_data["song_id"],
        title=song_info_data["title"],
        artist=song_info_data["artist"],
        language=song_info_data.get("language", ""),
        source="on_the_fly" if is_on_the_fly else "database",
        spotify_preview_url=song_info_data.get("spotify_preview_url"),
        album_art_url=song_info_data.get("album_art_url"),
        spotify_url=song_info_data.get("spotify_url"),
    )

    return MusicalDNAResponse(
        song=song_info_model,
        cell=Coordinates(x=x, y=y, text=f"({x}, {y})"),
        cell_size=len(cell_song_ids),
        dna=dna,
    )