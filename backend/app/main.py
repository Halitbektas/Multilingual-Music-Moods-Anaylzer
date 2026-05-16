"""
═══════════════════════════════════════════════════════════════════════════════
  MMMA Backend — FastAPI Entry Point
═══════════════════════════════════════════════════════════════════════════════

Çok Dilli Müzik Duygu Analiz Sistemi'nin HTTP API katmanı.

Açılışta:
  • SOM model + scaler + PCA dosyalarını disk'ten yükler (singleton).
  • som_music_database.csv + raw_music_data.csv DataFrame olarak belleğe alır.
  • Spotipy istemcisini Client Credentials akışıyla hazırlar.

Uçtaki endpoint'ler servislere delege eder; controller-service ayrımı korunur.
═══════════════════════════════════════════════════════════════════════════════
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.ml_loader import ml_state
from app.models import (
    AnalyzeRequest, AnalyzeResponse,
    JourneyRequest, JourneyResponse,
    WordCloudResponse, MusicalDNAResponse,
    NeighborsResponse,
)
from app.services import (
    analyzer_service,
    journey_service,
    musical_dna_service,
    som_service,
    wordcloud_service,
)


# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("mmma.main")


# ── Lifespan: startup'ta ağırlıkları yükle, shutdown'da temizle ─────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 MMMA backend başlatılıyor...")
    ml_state.load_all()
    logger.info(
        "✅ Modeller bellekte. SOM grid: %sx%s, veritabanı: %s şarkı",
        ml_state.som_x, ml_state.som_y, len(ml_state.df_db),
    )
    yield
    logger.info("🛑 Kapatılıyor.")


app = FastAPI(
    title="MMMA — Çok Dilli Müzik Duygu Analiz API",
    description=(
        "Spotify linki veya sanatçı+şarkı adı verildiğinde, şarkıyı SOM "
        "haritasında konumlar; ses özellikleri, lyrics duygusu, komşular ve "
        "yolculuk listesi döner."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ── CORS: lokal geliştirme + production için izin verilen origin'ler ────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═════════════════════════════════════════════════════════════════════════════
# Sağlık kontrolü
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "som_grid": f"{ml_state.som_x}x{ml_state.som_y}",
        "songs_in_db": len(ml_state.df_db),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Ana analiz endpoint'i — Spotify URL veya sanatçı+şarkı
# ═════════════════════════════════════════════════════════════════════════════
@app.post("/api/analyze", response_model=AnalyzeResponse, tags=["analyze"])
def analyze(req: AnalyzeRequest):
    """
    İki mod destekler:
      • spotify_url verilirse → track id alınır, veritabanında ARANIR.
        Varsa anında dönülür; yoksa on-the-fly tahmin (audio + lyrics + SOM).
      • artist + song verilirse → veritabanı araması (case-insensitive).
    """
    try:
        return analyzer_service.analyze(req)
    except analyzer_service.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except analyzer_service.ExternalAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ═════════════════════════════════════════════════════════════════════════════
# SOM hücresindeki komşular (+ Spotify preview_url + albüm kapağı)
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/api/cell/neighbors", response_model=NeighborsResponse, tags=["som"])
def cell_neighbors(
    x: int, y: int,
    limit: int = 10,
    exclude_song_id: str | None = None,
    enrich: bool = True,
):
    """
    (x, y) hücresindeki şarkıları döner. enrich=True ise her şarkı için
    Spotify'dan preview_url ve albüm kapağı eklenir (cache'li).
    """
    if not (0 <= x < ml_state.som_x and 0 <= y < ml_state.som_y):
        raise HTTPException(400, f"Koordinat sınır dışı: ({x},{y})")
    return som_service.get_neighbors(x, y, limit, exclude_song_id, enrich)


# ═════════════════════════════════════════════════════════════════════════════
# Müzikal DNA — şarkı vs hücre ortalaması (Radar grafiği için)
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/api/musical-dna/{song_id}", response_model=MusicalDNAResponse, tags=["som"])
def musical_dna(song_id: str):
    """
    Şarkının ham audio feature'larını (tempo, energy_rms, spectral_centroid,
    valence proxy'leri) **aynı hücredeki diğer şarkıların ortalamasıyla**
    karşılaştıran çift-eksenli veri döner. Frontend radar olarak çizer.
    """
    try:
        return musical_dna_service.compute(song_id)
    except musical_dna_service.NotFoundError as e:
        raise HTTPException(404, str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Word cloud — bir hücredeki şarkı sözlerinden Türkçe stopword'siz kelime bulutu
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/api/cell/wordcloud", response_model=WordCloudResponse, tags=["som"])
def cell_wordcloud(x: int, y: int, top_n: int = 60):
    """
    Hücredeki tüm şarkıların temizlenmiş lyrics'lerini birleştirir, TR/EN
    stopword'leri çıkarır, en sık geçen `top_n` kelimeyi frekansla döner.
    Frontend dilediği gibi çizer (d3-cloud, react-wordcloud, vs.).
    """
    if not (0 <= x < ml_state.som_x and 0 <= y < ml_state.som_y):
        raise HTTPException(400, f"Koordinat sınır dışı: ({x},{y})")
    return wordcloud_service.compute(x, y, top_n)


# ═════════════════════════════════════════════════════════════════════════════
# Yolculuk listesi — başlangıç hücresinden bitiş hücresine geçiş playlist'i
# ═════════════════════════════════════════════════════════════════════════════
@app.post("/api/journey", response_model=JourneyResponse, tags=["journey"])
def journey(req: JourneyRequest):
    """
    (start_x, start_y) → (end_x, end_y) arasında, SOM ızgarasında **adım adım**
    ses özellikleri kademeli değişen bir çalma listesi üretir.

    Geri dönüşte her şarkı için Spotify preview_url ve albüm kapağı da gelir.
    """
    if req.steps < 2 or req.steps > 30:
        raise HTTPException(400, "steps 2-30 aralığında olmalı.")
    return journey_service.generate(
        req.start_x, req.start_y, req.end_x, req.end_y, req.steps
    )
