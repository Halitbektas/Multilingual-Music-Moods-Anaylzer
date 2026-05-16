"""
Yolculuk listesi — başlangıç hücresinden bitiş hücresine **kademeli geçiş**.

linspace ile hücreler arası düz çizgi çizip her hücrede 1 şarkı seçer.
Boş hücrelere denk gelirsek en yakın dolu hücreye snap eder.

Narrative metni: başlangıç ve bitiş hücrelerinin etiketlerinden türetilir.
"""

import logging

import numpy as np

from app.ml_loader import ml_state
from app.models import Coordinates, JourneyResponse, JourneyStop, NeighborSong
from app.services import spotify_service
from app.services.analyzer_service import _quadrant_label  # tekrar tekrar yazmamak için


logger = logging.getLogger("mmma.journey")


def _nearest_non_empty_cell(x: int, y: int, max_radius: int = 6):
    """Boş hücre denk gelirse en yakın dolu hücreyi bul (BFS)."""
    db = ml_state.df_db
    for r in range(max_radius + 1):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if abs(dx) != r and abs(dy) != r:
                    continue  # sadece halka üzerindekiler
                nx, ny = x + dx, y + dy
                if not (0 <= nx < ml_state.som_x and 0 <= ny < ml_state.som_y):
                    continue
                if not db[(db["som_x"] == nx) & (db["som_y"] == ny)].empty:
                    return nx, ny
    return None


def generate(start_x: int, start_y: int,
             end_x: int, end_y: int, steps: int) -> JourneyResponse:
    grid_x, grid_y = ml_state.som_x, ml_state.som_y

    # Sınır kontrolü
    for coord in [(start_x, start_y), (end_x, end_y)]:
        cx, cy = coord
        if not (0 <= cx < grid_x and 0 <= cy < grid_y):
            raise ValueError(f"Koordinat sınır dışı: {coord}")

    xs = np.linspace(start_x, end_x, steps).astype(int)
    ys = np.linspace(start_y, end_y, steps).astype(int)

    db = ml_state.df_db
    seen_cells: set[tuple[int, int]] = set()
    stops: list[JourneyStop] = []
    step_no = 0

    for px, py in zip(xs, ys):
        cell_key = (int(px), int(py))
        cell = db[(db["som_x"] == cell_key[0]) & (db["som_y"] == cell_key[1])]

        # Boşsa en yakın dolu hücreye atla
        if cell.empty:
            snap = _nearest_non_empty_cell(cell_key[0], cell_key[1])
            if snap is None:
                continue
            cell_key = snap
            cell = db[(db["som_x"] == cell_key[0]) & (db["som_y"] == cell_key[1])]

        # Aynı hücreyi tekrar koyma
        if cell_key in seen_cells:
            continue
        seen_cells.add(cell_key)

        chosen = cell.sample(1).iloc[0]
        meta = spotify_service.enrich_song_row(chosen)
        step_no += 1
        stops.append(JourneyStop(
            step=step_no,
            cell=Coordinates(x=cell_key[0], y=cell_key[1],
                             text=f"({cell_key[0]}, {cell_key[1]})"),
            song=NeighborSong(**meta),
        ))

    # ── Narrative ───────────────────────────────────────────────────────
    start_label, _ = _quadrant_label(start_x, start_y, grid_x, grid_y)
    end_label, _ = _quadrant_label(end_x, end_y, grid_x, grid_y)
    narrative = (
        f"{start_label} hücresinden başlayıp seni adım adım {end_label} "
        f"bölgesine taşıyan, ses özellikleri yumuşak geçişlerle değişen "
        f"{len(stops)} duraklı bir yolculuk listesi hazırladım."
    )

    return JourneyResponse(
        narrative=narrative,
        total_stops=len(stops),
        stops=stops,
    )
