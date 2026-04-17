import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import os

load_dotenv()

auth_manager = SpotifyClientCredentials(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET")
)
sp = spotipy.Spotify(auth_manager=auth_manager)
def get_track_info(track_url):
    try:
        track_info = sp.track(track_url)
        song_name = track_info['name']
        artist_name = track_info['artists'][0]['name']
        return song_name, artist_name
    except Exception as e:
        print(f"Error fetching track info: {e}")
        return None, None