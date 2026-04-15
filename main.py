from dotenv import load_dotenv
from lyrics_pipeline import fetch_single_lyrics
import os
from audio_fetcher import process_song_automatically
from spotipy_executer import get_track_info
import pandas as pd

load_dotenv()

GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")
test_song_url = "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC"

song_name, artist_name = get_track_info(test_song_url)

if song_name and artist_name:
    print(f"Şarkı Adı: {song_name}")
    print(f"Sanatçı Adı: {artist_name}")
    audio_data = process_song_automatically(song_name, artist_name)
    lyrics_data = fetch_single_lyrics(song_name, artist_name, GENIUS_TOKEN)


### BU DOSYA SUAN KULLANILMAYACAK !!!