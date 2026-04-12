import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()



def get_track_info(track_url):
    auth_manager = SpotifyClientCredentials()
    sp = spotipy.Spotify(auth_manager=auth_manager)

    try:
        track_info = sp.track(track_url)
        song_name = track_info['name']
        artist_name = track_info['artists'][0]['name']
        return song_name, artist_name
    except Exception as e:
        print(f"Error fetching track info: {e}")
        return None, None

print(get_track_info("https://open.spotify.com/intl-tr/track/1mgoLJV5W6JSWanT5bgf3o?si=3d5a056bfdb84262"))