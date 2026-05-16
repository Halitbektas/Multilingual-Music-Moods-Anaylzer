"""
Tüm çalışma zamanı yapılandırması burada toplanır. .env dosyasından okunur,
yoksa makul varsayılanlar kullanılır.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# app/config.py dosyasından yola çıkarak:
# 1. parent -> app/
# 2. parent -> backend/
# 3. parent -> Ana Dizin (Multilingual-Music-Moods-Anaylzer/)
MAIN_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # .env dosyasını artık backend içinden değil, ana dizinden okuyor
        env_file=str(MAIN_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Spotify (Client Credentials akışı yeterli; oauth gerekmez) ──────────
    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    # ── Genius (yeni şarkıların lyrics'i için) ──────────────────────────────
    genius_token: str = ""

    # ── Model dosya yolları (artık ana dizin altındaki som_results varsayılır) ────
    som_model_path: Path = MAIN_PROJECT_ROOT / "som_results" / "mmma_som_model_v2_global.pkl"
    laser_scaler_path: Path = MAIN_PROJECT_ROOT / "som_results" / "laser_scaler_v2.pkl"
    laser_pca_path: Path = MAIN_PROJECT_ROOT / "som_results" / "laser_pca_model_v2.pkl"
    final_scaler_path: Path = MAIN_PROJECT_ROOT / "som_results" / "final_som_scaler_v2.pkl"

    som_db_csv: Path = MAIN_PROJECT_ROOT / "som_results" / "som_music_database_v2.csv"
    
    # Veriseti de ana dizinden okunuyor
    raw_data_csv: Path = MAIN_PROJECT_ROOT / "raw_music_dataset_v2.csv"

    # ── CORS ────────────────────────────────────────────────────────────────
    # Üretimde gerçek domain'inle değiştir.
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5500",   # VSCode Live Server
        "http://localhost:8080",
    ]

    # ── Cache ───────────────────────────────────────────────────────────────
    # Spotify track lookup'ları için bellek-içi LRU; canlıda Redis'e geçersin.
    spotify_cache_size: int = 2048


settings = Settings()