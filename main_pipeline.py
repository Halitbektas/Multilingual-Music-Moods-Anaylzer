import os
import pandas as pd
import time
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth


from audio_fetcher import process_song_automatically
from lyrics_pipeline import fetch_single_lyrics
from nlp_pipeline import get_embeddings
from preprocessing import clean_title

load_dotenv()


def run_artist_pipeline(artist_name, output_csv="raw_music_dataset.csv"):
    if os.path.exists(".cache"):
        os.remove(".cache")

    print(f"\n🚀 Madenci Başlatıldı: '{artist_name}' taranıyor...")

    auth_manager = SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("REDIRECT_URI"),
        scope="playlist-read-private",
        open_browser=True
    )
    sp = spotipy.Spotify(auth_manager=auth_manager)
    GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")

    all_tracks = []


    for current_offset in range(0, 200, 10):
        try:
            q_str = f'artist:"{artist_name}"'
            results = sp.search(q=q_str, type='track', limit=10, offset=current_offset)
            tracks = results['tracks']['items']

            if not tracks: break

            all_tracks.extend(tracks)
            print(f"📥 {artist_name} için {len(all_tracks)} şarkı listelendi...")
            time.sleep(0.2)

        except Exception as e:
            print(f"⚠️ Hata oluştu: {e}")
            break

    if not all_tracks:
        print(f"❌ {artist_name} için veri bulunamadı.")
        return

    # Mevcut şarkıları kontrol et (Duplicate önleme)
    existing_songs = set()
    if os.path.isfile(output_csv):
        try:
            df_existing = pd.read_csv(output_csv, usecols=['title', 'artist'])
            existing_songs = set(zip(df_existing['title'], df_existing['artist']))
        except:
            pass

    success_count = 0
    for track in all_tracks:
        try:
            song_name = clean_title(track['name'])
            actual_artist = track['artists'][0]['name']

            # Duplicate kontrolü
            if (song_name, actual_artist) in existing_songs:
                continue

            print(f"\n🎵 ({success_count + 1}) İşleniyor: {song_name} - {actual_artist}")

            # Audio, Lyrics ve NLP Süreçleri
            audio_data = process_song_automatically(song_name, actual_artist)
            if not audio_data: continue

            lyrics_res = fetch_single_lyrics(song_name, actual_artist, GENIUS_TOKEN)
            if not lyrics_res: continue

            embedding = get_embeddings(lyrics_res['clean_lyrics'])
            nlp_features = {f"bert_emb_{i}": val for i, val in enumerate(embedding)}

            final_row = {
                "song_id": track['id'],
                "title": song_name,
                "artist": actual_artist,
                "language": lyrics_res['detected_language'],
                **audio_data,
                **nlp_features
            }

            df_new = pd.DataFrame([final_row])
            df_new.to_csv(output_csv, mode='a', index=False, header=not os.path.isfile(output_csv))
            success_count += 1

        except Exception as e:
            print(f"❌ Şarkı hatası ({song_name}): {e}")

    print(f"\n✅ {artist_name} bitti. {success_count} yeni şarkı eklendi.")


if __name__ == "__main__":
    print("\n   MMMA MUSIC MINER V3.0 - ARTIST ONLY MODE")

    # İster buraya sanatçıları içeren bir .txt dosyası yolu ver,
    # ister listeyi doğrudan buraya yaz.
    artists_to_scan = ["Mabel Matiz"]  # Örnek liste

    # Eğer artists.txt diye bir dosyadan okumak istersen:
    if os.path.exists("artists.txt"):
        with open("artists.txt", "r", encoding="utf-8") as f:
            artists_to_scan = [line.strip() for line in f.readlines() if line.strip()]

    for artist in artists_to_scan:
        run_artist_pipeline(artist)

    print("\n🏁 Tüm liste başarıyla tarandı.")