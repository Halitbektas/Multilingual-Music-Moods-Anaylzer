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

    if db is None or db.empty:
        raise NotFoundError("Veritabanı boş.")

    hit = db[db["song_id"] == song_id]
    if hit.empty:
        raise NotFoundError(f"Şarkı bulunamadı: {song_id}")

    row = hit.iloc[0]
    x, y = int(row["som_x"]), int(row["som_y"])

    # Hücredeki tüm şarkı id'leri
    cell_song_ids = db[(db["som_x"] == x) & (db["som_y"] == y)]["song_id"].tolist()

    # Şarkının ve hücre ortalamasının ham özelliklerini topla
    if raw is None or raw.empty or "song_id" not in raw.columns:
        # raw_music_dataset.csv yoksa nötr fallback
        dna = [DNAEntry(feature=name, song_value=50, cell_average=50)
               for name, *_ in RADAR_FEATURES]
        return MusicalDNAResponse(
            song=_song_info(row),
            cell=Coordinates(x=x, y=y, text=f"({x}, {y})"),
            cell_size=len(cell_song_ids),
            dna=dna,
        )

    song_raw = raw[raw["song_id"] == song_id]
    cell_raw = raw[raw["song_id"].isin(cell_song_ids)]

    dna: list[DNAEntry] = []
    for name, col, lo, hi in RADAR_FEATURES:
        if col not in raw.columns:
            dna.append(DNAEntry(feature=name, song_value=50, cell_average=50))
            continue

        song_val = song_raw[col].iloc[0] if not song_raw.empty else None
        cell_val = cell_raw[col].mean() if not cell_raw.empty else None

        dna.append(DNAEntry(
            feature=name,
            song_value=_scale(song_val, lo, hi),
            cell_average=_scale(cell_val, lo, hi),
        ))

    return MusicalDNAResponse(
        song=_song_info(row),
        cell=Coordinates(x=x, y=y, text=f"({x}, {y})"),
        cell_size=len(cell_song_ids),
        dna=dna,
    )


def _song_info(row) -> SongInfo:
    """Spotify zenginleştirmesi ile birlikte SongInfo üret."""
    meta = spotify_service.enrich_song_row(row)
    return SongInfo(
        song_id=str(row["song_id"]),
        title=str(row["title"]),
        artist=str(row["artist"]),
        language=str(row.get("language") or ""),
        source="Spotify",
        spotify_preview_url=meta.get("spotify_preview_url"),
        album_art_url=meta.get("album_art_url"),
        spotify_url=meta.get("spotify_url"),
    )
