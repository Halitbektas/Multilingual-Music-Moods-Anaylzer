"""
Pydantic modelleri — endpoint sözleşmeleri burada.
FastAPI bunları kullanarak otomatik /docs üretir + tip kontrolü yapar.
"""

from typing import Literal
from pydantic import BaseModel, Field, model_validator


# ═════════════════════════════════════════════════════════════════════════════
# /api/analyze
# ═════════════════════════════════════════════════════════════════════════════
class AnalyzeRequest(BaseModel):
    """İki moddan biri zorunlu: ya spotify_url, ya artist+song."""
    spotify_url: str | None = Field(None, description="Spotify track URL'si")
    artist: str | None = Field(None, description="Sanatçı adı")
    song: str | None = Field(None, description="Şarkı adı")

    @model_validator(mode="after")
    def _at_least_one(self):
        has_url = bool(self.spotify_url and self.spotify_url.strip())
        has_manual = bool(self.artist and self.song)
        if not (has_url or has_manual):
            raise ValueError(
                "Ya spotify_url, ya da (artist + song) verilmeli."
            )
        return self


class Coordinates(BaseModel):
    x: int
    y: int
    text: str  # "(3, 5)" gibi gösterim için


class SongInfo(BaseModel):
    song_id: str
    title: str
    artist: str
    language: str | None = None
    source: Literal["Spotify", "Manuel Giriş", "Yeni Analiz"]
    spotify_preview_url: str | None = None
    album_art_url: str | None = None
    spotify_url: str | None = None


class MoodPrediction(BaseModel):
    """SOM hücresinin etiketi + güven puanı."""
    label: str          # "Enerjik ve Mutlu" vb.
    confidence: int     # 0-100
    intensity: int      # 0-100
    footnote: str


class AudioFeatures(BaseModel):
    """Radar grafiğindeki eksenler. 0-100 arası normalize."""
    energy: float
    valence: float
    danceability: float
    acousticness: float
    tempo: float
    loudness: float


class MoodDistribution(BaseModel):
    """Hücredeki/şarkıdaki ruh hali dağılımı (yüzde)."""
    happy: float
    energetic: float
    calm: float
    melancholic: float
    neutral: float


class LyricsAnalysis(BaseModel):
    """Şarkı sözü duygu skorları (0-100)."""
    positivity: float       # şarkı sözü pozitifliği
    emotional_depth: float  # duygusal derinlik
    narrative_tone: float   # anlatım tonu


class AnalyzeResponse(BaseModel):
    song: SongInfo
    coordinates: Coordinates
    mood: MoodPrediction
    audio_features: AudioFeatures
    mood_distribution: MoodDistribution
    lyrics: LyricsAnalysis


# ═════════════════════════════════════════════════════════════════════════════
# /api/cell/neighbors
# ═════════════════════════════════════════════════════════════════════════════
class NeighborSong(BaseModel):
    song_id: str
    title: str
    artist: str
    spotify_preview_url: str | None = None
    album_art_url: str | None = None
    spotify_url: str | None = None


class NeighborsResponse(BaseModel):
    cell: Coordinates
    total_in_cell: int
    neighbors: list[NeighborSong]


# ═════════════════════════════════════════════════════════════════════════════
# /api/musical-dna/{song_id}
# ═════════════════════════════════════════════════════════════════════════════
class DNAEntry(BaseModel):
    feature: str   # "energy", "tempo", vb.
    song_value: float
    cell_average: float


class MusicalDNAResponse(BaseModel):
    song: SongInfo
    cell: Coordinates
    cell_size: int
    dna: list[DNAEntry]


# ═════════════════════════════════════════════════════════════════════════════
# /api/cell/wordcloud
# ═════════════════════════════════════════════════════════════════════════════
class WordFrequency(BaseModel):
    word: str
    weight: int


class WordCloudResponse(BaseModel):
    cell: Coordinates
    songs_aggregated: int
    words: list[WordFrequency]


# ═════════════════════════════════════════════════════════════════════════════
# /api/journey
# ═════════════════════════════════════════════════════════════════════════════
class JourneyRequest(BaseModel):
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    steps: int = 10


class JourneyStop(BaseModel):
    step: int           # 1..N
    cell: Coordinates
    song: NeighborSong


class JourneyResponse(BaseModel):
    narrative: str      # "Yüksek enerjiden melankoliye geçiş..." gibi
    total_stops: int
    stops: list[JourneyStop]
