import yt_dlp
import os
import librosa
import numpy as np
import pandas as pd


def download_mp3(song_title, artist_name, output_folder="audio_files"):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    search_term = f"{artist_name} {song_title}".strip()
    search_query = f"ytsearch1:{search_term} official audio"

    safe_name = "".join([c for c in search_term if c.isalpha() or c.isdigit() or c == ' ']).rstrip()
    file_name = safe_name.replace(' ', '_')
    output_path = os.path.join(output_folder, f"{file_name}.%(ext)s")
    final_mp3_path = os.path.join(output_folder, f"{file_name}.mp3")

    if os.path.exists(final_mp3_path):
        return final_mp3_path


    ydl_opts = {
        'format': 'bestaudio/best',  # Sadece sesi indirme
        'outtmpl': output_path,  # Çıktı adı ve konumu
        'noplaylist': True,  # Oynatma listesi indirme
        'quiet': True,  # Terminali gereksiz yazılarla doldurma
        'no_warnings': True,  # Uyarıları gizle
        'postprocessors': [{  # Sesi MP3 formatına dönüştür
            'key': 'FFmpegExtractAudio',  # FFmpeg kullanarak sesi çıkar
            'preferredcodec': 'mp3',  # MP3 formatında kaydet
            'preferredquality': '192',  # 192kbps
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_query])
        return final_mp3_path

    except Exception as e:
        print(f"[HATA] İndirilemedi. Sebep: {str(e)}")
        return None

def process_song_automatically(song_name, artist_name=""):
    output_csv = "music_features.csv"

    mp3_path = download_mp3(song_name, artist_name)

    if mp3_path is None:
        print(f"HATA: {song_name} indirilemedi, atlanıyor.")
        return

    try:

        y, sr = librosa.load(mp3_path, duration=30)
        tempo_output = librosa.beat.beat_track(y=y, sr=sr) # Librosa'nın yeni sürümlerinde tempo_output[0] bir array
        tempo_value = float(np.mean(tempo_output[0])) # Tempo değerini tek bir float olarak almak için mean alıyoruz
        rms = float(np.mean(librosa.feature.rms(y=y))) # RMS değerini tek bir float olarak almak için mean alıyoruz
        spec_cent = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))

        features = {
            "song_id": f"{artist_name}_{song_name}".replace(" ", "_"),
            "tempo": tempo_value,
            "energy_rms": rms,
            "spectral_centroid": spec_cent
        }

        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        for i, m in enumerate(np.mean(mfccs, axis=1)):
            features[f"mfcc_{i}"] = m

        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        for i, c in enumerate(np.mean(chroma, axis=1)):
            features[f"chroma_{i}"] = c

        df_new = pd.DataFrame([features])
        if not os.path.isfile(output_csv):
            df_new.to_csv(output_csv, index=False)
        else:
            df_new.to_csv(output_csv, mode='a', header=False, index=False)

        print(f"BAŞARILI: {song_name} verileri CSV'ye eklendi.")
        return features

    except Exception as e:
        print(f"HATA Oluştu: {e}")

    finally:
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)
            print(f"Temizlik: {mp3_path} silindi.")
