"""
Tüm büyük objeleri (SOM, scaler'lar, PCA, CSV'ler) bir kez yükleyip
process boyunca paylaşmak için singleton state.

Önemli: FastAPI'de "modulü import ettiğinde otomatik yükle" anti-pattern'i;
hata kontrolünü startup lifespan'da yapmak gerekir. Bu yüzden `load_all()`
elle çağrılır — main.py'nin lifespan'ı bunu yapıyor.
"""

import logging
import pickle
from typing import Any

import joblib
import pandas as pd

from app.config import settings


logger = logging.getLogger("mmma.ml_loader")


class MLState:
    """SOM model + scaler'lar + dataframe'ler için tek doğruluk kaynağı."""

    def __init__(self) -> None:
        self.som: Any = None
        self.som_x: int = 0   # MiniSom .x/.y vermez; weights.shape'den çıkarırız
        self.som_y: int = 0
        self.laser_scaler: Any = None
        self.laser_pca: Any = None
        self.final_scaler: Any = None
        self.df_db: pd.DataFrame | None = None
        self.df_raw: pd.DataFrame | None = None
        self._loaded = False
        self.runtime_songs: dict[str, dict] = {}

    # ── Yükleme ─────────────────────────────────────────────────────────────
    def load_all(self) -> None:
        if self._loaded:
            return

        logger.info("SOM modeli yükleniyor: %s", settings.som_model_path)
        with open(settings.som_model_path, "rb") as f:
            self.som = pickle.load(f)

        # MiniSom grid boyutunu weight tensor'undan al
        weights = self.som.get_weights()  # shape: (x, y, input_dim)
        self.som_x, self.som_y = int(weights.shape[0]), int(weights.shape[1])

        logger.info("LASER scaler: %s", settings.laser_scaler_path)
        self.laser_scaler = joblib.load(settings.laser_scaler_path)

        logger.info("LASER PCA: %s", settings.laser_pca_path)
        self.laser_pca = joblib.load(settings.laser_pca_path)

        logger.info("Final SOM scaler: %s", settings.final_scaler_path)
        self.final_scaler = joblib.load(settings.final_scaler_path)

        logger.info("SOM veritabanı CSV: %s", settings.som_db_csv)
        self.df_db = pd.read_csv(settings.som_db_csv)

        if settings.raw_data_csv.exists():
            logger.info("Ham veri CSV: %s", settings.raw_data_csv)
            self.df_raw = pd.read_csv(settings.raw_data_csv)
        else:
            logger.warning(
                "raw_music_dataset_v2.csv bulunamadı (%s). Musical-DNA özelliği "
                "şarkı bazlı tarafta cell-average ile sınırlı çalışacak.",
                settings.raw_data_csv,
            )
            self.df_raw = pd.DataFrame()

        # Sıkça aranılan kolonlar için lower-case indeks (kullanıcı yazımına dayanıklı)
        if {"title", "artist"} <= set(self.df_db.columns):
            self.df_db["_title_lc"] = self.df_db["title"].astype(str).str.lower().str.strip()
            self.df_db["_artist_lc"] = self.df_db["artist"].astype(str).str.lower().str.strip()

        self._loaded = True

    # ── Yardımcılar ─────────────────────────────────────────────────────────
    def find_song(self, song_id: str | None = None,
                  title: str | None = None,
                  artist: str | None = None) -> pd.Series | None:
        """song_id öncelikli; yoksa (title, artist) eşleşmesi."""
        if self.df_db is None or self.df_db.empty:
            return None

        if song_id:
            hit = self.df_db[self.df_db["song_id"] == song_id]
            if not hit.empty:
                return hit.iloc[0]

        if title and artist:
            t = title.lower().strip()
            a = artist.lower().strip()
            hit = self.df_db[
                (self.df_db["_title_lc"] == t) & (self.df_db["_artist_lc"] == a)
            ]
            if not hit.empty:
                return hit.iloc[0]

            # Fuzzy fallback: artist exact, title contains
            hit = self.df_db[
                (self.df_db["_artist_lc"] == a)
                & (self.df_db["_title_lc"].str.contains(t, regex=False, na=False))
            ]
            if not hit.empty:
                return hit.iloc[0]

        return None

    def cell_songs(self, x: int, y: int) -> pd.DataFrame:
        if self.df_db is None:
            return pd.DataFrame()
        return self.df_db[(self.df_db["som_x"] == x) & (self.df_db["som_y"] == y)]


# Global singleton
ml_state = MLState()
