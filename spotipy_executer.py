import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth
import os
import time
import pandas as pd

load_dotenv()
if os.path.exists(".cache"):
    os.remove(".cache")
    print("🗑️ Eski bozuk önbellek (cache) başarıyla silindi!")

auth_manager = SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("REDIRECT_URI"),
    scope="playlist-read-private"

)
CSV_FILENAME = 'MMMA_Massive_Dataset_AutoSave.csv'
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


def save_checkpoint(tracks_list):
    if not tracks_list: return

    df = pd.DataFrame(tracks_list)
    file_exists = os.path.isfile(CSV_FILENAME)
    df.to_csv(CSV_FILENAME, mode='a', index=False, header=not file_exists)


def get_tracks_by_search_terms(total_goal=20000):
    all_tracks = []
    seen_ids = set()
    total_saved = 0

    search_queries = [
        'artist:"Müslüm Gürses"',
        'artist:"Sezen Aksu"',

    ]

    for query in search_queries:
        if total_saved >= total_goal: break

        print(f"\n🔍 '{query}' etiketine sahip şarkılar toplanıyor...")

        for offset in range(0, 1000, 10):
            try:
                search_res = sp.search(q=query, type='track', limit=10, offset=offset, market='TR')
                tracks = search_res['tracks']['items']

                if not tracks: break

                batch_tracks = []
                for track in tracks:
                    if track and track.get('id') and track['id'] not in seen_ids:
                        batch_tracks.append({
                            'song_id': track['id'],
                            'title': track['name'],
                            'artist': track['artists'][0]['name'] if track.get('artists') else 'Unknown',
                            'popularity': track.get('popularity', 0),
                            'search_tag': query
                        })
                        seen_ids.add(track['id'])

                if batch_tracks:
                    save_checkpoint(batch_tracks)
                    total_saved += len(batch_tracks)
                    print(f"💾 Otomatik Kayıt! Toplam güvende olan şarkı: {total_saved}")

                if total_saved >= total_goal: break
                time.sleep(1)

            except spotipy.exceptions.SpotifyException as e:
                print(f"⚠️ API Hatası (Ban yemiş olabiliriz): {e}")
                return
            except Exception as e:
                print(f"⚠️ Beklenmeyen Hata: {e}")
                break


get_tracks_by_search_terms(total_goal=20000)
print(f"\n🏁 İşlem tamam! Verilerin {CSV_FILENAME} dosyasında güvende.")