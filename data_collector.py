import os
import pandas as pd
from dotenv import load_dotenv
from spotipy_executer import get_track_info
from audio_fetcher import process_song_automatically
from lyrics_pipeline import fetch_single_lyrics
from nlp_pipeline import get_bert_embeddings

load_dotenv()
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")


def run_collector(track_urls, output_csv="raw_music_dataset.csv"):
    for url in track_urls:
        try:
            print(f"Processing URL: {url}")
            song_name, artist_name = get_track_info(url)
            if not song_name or not artist_name:
                print(f"Skipping URL due to missing info: {url}")
                continue

            audio_data = process_song_automatically(song_name, artist_name)
            if not audio_data:
                print(f"Skipping URL due to audio processing failure: {url}")
                continue

            lyrics_res = fetch_single_lyrics(song_name, artist_name, GENIUS_TOKEN)
            if not lyrics_res:
                print(f"Skipping URL due to lyrics fetching failure: {url}")
                continue

            embedding = get_bert_embeddings(lyrics_res['clean_lyrics'])
            nlp_features = {f"bert_emb_{i}": val for i, val in enumerate(embedding)}

            final_row = {
                "title": song_name,
                "artist": artist_name,
                "language": lyrics_res['detected_language'],
                **audio_data,
                **nlp_features
            }

            df_new = pd.DataFrame([final_row])
            file_exists = os.path.isfile(output_csv)
            df_new.to_csv(output_csv, mode='a', index=False, header=not file_exists)

            print(f"Successfully processed: {song_name} by {artist_name}")

        except Exception as e:
            print(f"Error processing URL {url}: {e}")


if __name__ == "__main__":

    test_links = [
        "https://open.spotify.com/intl-tr/track/1mgoLJV5W6JSWanT5bgf3o?si=bfdbeb86b14b4da8",
    ]
    run_collector(test_links)
