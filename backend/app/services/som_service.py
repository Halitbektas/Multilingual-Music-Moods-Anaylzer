"""
SOM ızgarası üzerinde işlemler — komşu bulma, hücre içeriği, koordinatlar.
"""

import logging

from app.ml_loader import ml_state
from app.models import Coordinates, NeighborSong, NeighborsResponse
from app.services import spotify_service


logger = logging.getLogger("mmma.som")


def get_neighbors(
    x: int, y: int,
    limit: int = 10,
    exclude_song_id: str | None = None,
    enrich: bool = True,
) -> NeighborsResponse:
    cell = ml_state.cell_songs(x, y)
    total = len(cell)

    if exclude_song_id:
        cell = cell[cell["song_id"] != exclude_song_id]

    cell = cell.head(limit)

    neighbors: list[NeighborSong] = []
    for _, row in cell.iterrows():
        if enrich:
            data = spotify_service.enrich_song_row(row)
        else:
            data = {
                "song_id": str(row.get("song_id") or ""),
                "title": str(row.get("title") or ""),
                "artist": str(row.get("artist") or ""),
                "spotify_preview_url": None,
                "album_art_url": None,
                "spotify_url": None,
            }
        neighbors.append(NeighborSong(**data))

    return NeighborsResponse(
        cell=Coordinates(x=x, y=y, text=f"({x}, {y})"),
        total_in_cell=total,
        neighbors=neighbors,
    )

def get_u_matrix() -> list[list[float]]:
    if not hasattr(ml_state, 'som') or ml_state.som is None:
        raise ValueError("SOM modeli yüklenmemiş.")

    u_matrix = ml_state.som.distance_map()
    return u_matrix.tolist()