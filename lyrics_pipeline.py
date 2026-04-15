# lyrics_pipeline.py
import lyricsgenius
from langdetect import detect, LangDetectException
import re
import pandas as pd

def clean_lyrics(raw_lyrics):
    text = re.sub(r'\[.*?\]', '', raw_lyrics)
    text = re.sub(r'\d*Embed$', '', text)    
    text = text.replace('\n', ' ')          
    text = re.sub(r'\s+', ' ', text).strip()  
    return text.lower()                     

def fetch_single_lyrics(title, artist, api_token):
    genius = lyricsgenius.Genius(api_token)
    genius.verbose = False
    genius.remove_playlists = True 
    genius.timeout = 15
    genius.retries = 3

    try:
        song = genius.search_song(title, artist)

        if song is None:
            print("[HATA: Bulunamadı]")
            return None

        lyrics_text = song.lyrics

        try:
            detected_lang = detect(lyrics_text)
        except LangDetectException:
            detected_lang = "unknown"

        if detected_lang in ['en', 'tr']:
            cleaned_text = clean_lyrics(lyrics_text)
            return {
                "title": song.title,
                "artist": song.artist,
                "detected_language": detected_lang,
                "clean_lyrics": cleaned_text
            }
        else:
            print(f"[ATLANDI: Hedef dil değil ({detected_lang})]")
            return None

    except Exception as e:
        print(f"[HATA: {str(e)}]")
        return None
