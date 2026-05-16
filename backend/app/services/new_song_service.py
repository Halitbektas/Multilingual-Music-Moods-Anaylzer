# app/services/new_song_service.py

import logging
import numpy as np
from fastapi import HTTPException
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# app/services/new_song_service.py üst kısmı

from app.ml_loader import ml_state
from app.config import settings
from app.models import AnalyzeResponse, Coordinates, SongInfo, AudioFeatures, LyricsAnalysis, MoodPrediction
from app.services import spotify_service
from app.services.analyzer_service import _quadrant_label, _confidence_for_cell
from app.services.wordcloud_service import compute_from_text

# Bu importları projenin ana dizinindeki modüllerinden kendine göre uyarla
from lyrics_pipeline import fetch_single_lyrics
from nlp_pipeline import get_embeddings
from audio_fetcher import process_song_automatically

logger = logging.getLogger("mmma.new_song")

# EĞİTİMDE KULLANILAN KOLON SIRASI (BİREBİR AYNI OLMALI)
EXPECTED_AUDIO_COLUMNS = [
    "tempo", "energy_rms", "spectral_centroid", 
    "mfcc_0", "mfcc_1", "mfcc_2", "mfcc_3", "mfcc_4", "mfcc_5", 
    "mfcc_6", "mfcc_7", "mfcc_8", "mfcc_9", "mfcc_10", "mfcc_11", "mfcc_12",
    "chroma_0", "chroma_1", "chroma_2", "chroma_3", "chroma_4", "chroma_5", 
    "chroma_6", "chroma_7", "chroma_8", "chroma_9", "chroma_10", "chroma_11"
]

def analyze_new_song_on_the_fly(song_id: str, title: str, artist: str, spotify_url: str) -> AnalyzeResponse:
    try:
        # 1. Spotify Meta Zenginleştirme
        spotify_meta = {}
        actual_id = song_id
        
        if spotify_url:
            # URL varsa içinden ID'yi çıkar ve verileri çek
            extracted_id = spotify_service.extract_track_id(spotify_url)
            if extracted_id:
                actual_id = extracted_id
                spotify_meta = spotify_service.get_track_meta(actual_id) or {}
        elif title and artist:
            # URL yoksa (manuel form girişi) şarkı ve sanatçı adından arat
            spotify_meta = spotify_service.search_track(artist, title) or {}
            if spotify_meta and "song_id" in spotify_meta:
                actual_id = spotify_meta["song_id"]

        actual_title = spotify_meta.get("title", title)
        actual_artist = spotify_meta.get("artist", artist)
        
        # Eğer Spotify'da bile bulunamazsa geçici bir ID üret
        if not actual_id:
            actual_id = f"temp_{actual_title}_{actual_artist}".replace(" ", "_")

        actual_title = spotify_meta.get("title", title)
        actual_artist = spotify_meta.get("artist", artist)
        actual_id = spotify_meta.get("song_id", song_id or f"temp_{actual_title}_{actual_artist}".replace(" ", "_"))

        # 2. Lyrics Çekme
        logger.info("Genius'tan şarkı sözleri çekiliyor...")
        lyrics_res = fetch_single_lyrics(actual_title, actual_artist, settings.genius_token)
        if not lyrics_res:
            raise HTTPException(status_code=400, detail="Şarkı sözleri bulunamadı, analiz yapılamıyor.")
        
        clean_lyrics = lyrics_res['clean_lyrics']
        detected_language = lyrics_res['detected_language']

        # 3. NLP Embedding Üretme (512 boyutlu)
        logger.info("Şarkı sözleri vektöre çevriliyor...")
        lyrics_embedding = get_embeddings(clean_lyrics)

        # 4. Audio Feature Çıkarma
        logger.info("Ses analiz ediliyor...")
        # process_song_automatically sana dict dönmeli (CSV yazmamalı)
        audio_features_dict = process_song_automatically(actual_title, actual_artist)
        if not audio_features_dict:
            raise HTTPException(status_code=400, detail="Ses dosyası indirilemedi veya işlenemedi.")

        # 5. Modele Hazırlık (Vektörleri Sıralama ve Birleştirme)
        logger.info("SOM için vektörler hazırlanıyor...")
        
        # Lyrics için Scaler ve PCA uygula
        lyrics_scaled = ml_state.laser_scaler.transform([lyrics_embedding])
        lyrics_pca = ml_state.laser_pca.transform(lyrics_scaled) # Shape: (1, pca_dim)

        # Audio özelliklerini beklenen sıraya göre numpy dizisine çevir
        audio_vector = np.array([[audio_features_dict.get(col, 0.0) for col in EXPECTED_AUDIO_COLUMNS]]) # Shape: (1, 28)

        # Vektörleri birleştir (Önce audio mu lyrics mi birleştirildiğine eğitim kodundan emin ol)
        # Genelde sıralama: [audio_features, lyrics_pca_features] şeklindedir.
        combined_vector = np.concatenate((audio_vector, lyrics_pca), axis=1)

        # Final Scaler uygula
        final_input = ml_state.final_scaler.transform(combined_vector)

        # 6. SOM Tahmini (Winner)
        logger.info("SOM haritasındaki koordinat tahmin ediliyor...")
        x, y = ml_state.som.winner(final_input[0])
        x, y = int(x), int(y)

        for k, v in audio_features_dict.items():
            if isinstance(v, np.floating):
                audio_features_dict[k] = float(v)

        # 7. Runtime Cache'e Kaydet
        ml_state.runtime_songs[actual_id] = {
            "song_id": actual_id,
            "title": actual_title,
            "artist": actual_artist,
            "som_x": x,
            "som_y": y,
            "language": detected_language,
            "clean_lyrics": clean_lyrics,
            "audio_features": audio_features_dict,
            "spotify_preview_url": spotify_meta.get("preview_url"),
            "album_art_url": spotify_meta.get("album_art_url"),
            "spotify_url": spotify_meta.get("external_url") or spotify_url,
        }

        # 8. Response Oluştur (Sadece gerçek verilerle)
        mood_label, footnote = _quadrant_label(x, y, ml_state.som_x, ml_state.som_y)
        conf, intensity = _confidence_for_cell(x, y)

        return AnalyzeResponse(
            song=SongInfo(
                song_id=actual_id,
                title=actual_title,
                artist=actual_artist,
                language=detected_language,
                source="on_the_fly",
                spotify_preview_url=spotify_meta.get("preview_url"),
                album_art_url=spotify_meta.get("album_art_url"),
                spotify_url=spotify_meta.get("external_url") or spotify_url,
            ),
            coordinates=Coordinates(x=x, y=y, text=f"({x}, {y})"),
            mood=MoodPrediction(
                label=mood_label,
                confidence=conf,
                intensity=intensity,
                footnote=footnote
            ),
            audio_features=AudioFeatures(**audio_features_dict),
            lyrics=LyricsAnalysis(
                language=detected_language,
                word_count=len(clean_lyrics.split())
            ),
            lyrics_wordcloud=compute_from_text(clean_lyrics, top_n=60),
        )
    
    except Exception as e:
        logger.error(f"On-the-fly analiz hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Şarkı analiz edilirken bir hata oluştu: {str(e)}")