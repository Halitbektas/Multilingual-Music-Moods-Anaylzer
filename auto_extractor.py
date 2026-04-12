import yt_dlp
import os
import librosa
import numpy as np
import pandas as pd


def process_song_automatically(song_name):
    temp_filename = "temp_audio"
    output_csv = "music_features.csv"

    print(f"\n--- '{song_name}' YouTube'da aranıyor ve indiriliyor... ---")
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_filename + '.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'no_warnings': True,
        'source_address': '0.0.0.0',
        'force_generic_extractor': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"ytsearch1:{song_name}"])

        target_file = temp_filename + ".mp3"

        # 2. ADIM: Librosa ile Detaylı Analiz
        print(f"--- Analiz ediliyor: {song_name} ---")
        y, sr = librosa.load(target_file, duration=30)

        # Temel Özellikler (Hata veren kısım düzeltildi)
        tempo_output = librosa.beat.beat_track(y=y, sr=sr)
        # Yeni Librosa sürümlerinde tempo_output[0] bir array olabilir, o yüzden mean alıyoruz
        tempo_value = float(np.mean(tempo_output[0]))

        rms = float(np.mean(librosa.feature.rms(y=y)))
        spec_cent = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        # Sözlüğü Hazırla (İlk 4 sütun)
        features = {
            "file_name": song_name,
            "tempo": tempo_value,
            "energy_rms": rms,
            "spectral_centroid": spec_cent
        }

        # MFCC Özelliklerini Ekle (13 adet)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        for i, m in enumerate(np.mean(mfccs, axis=1)):
            features[f"mfcc_{i}"] = m

        # Chroma Özelliklerini Ekle (12 adet)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        for i, c in enumerate(np.mean(chroma, axis=1)):
            features[f"chroma_{i}"] = c

        # 3. ADIM: CSV'ye Ekle
        df_new = pd.DataFrame([features])

        # Eğer dosya yoksa başlıklarla oluştur, varsa altına ekle
        if not os.path.isfile(output_csv):
            df_new.to_csv(output_csv, index=False)
        else:
            # Sütun sırasının bozulmaması için mevcut CSV'yi baz alarak ekliyoruz
            df_new.to_csv(output_csv, mode='a', header=False, index=False)

        print(f"BAŞARILI: {song_name} verileri CSV'ye eklendi.")

    except Exception as e:
        print(f"HATA Oluştu: {e}")

    finally:
        if os.path.exists(temp_filename + ".mp3"):
            os.remove(temp_filename + ".mp3")
            print(f"Temizlik: Geçici dosya silindi.")


if __name__ == "__main__":
    # Buraya istediğin kadar şarkı ekleyebilirsin!
    sarkilar = ["Semicenk Çıkmaz Bir Sokakta", "Mabel Matiz Antidepresan"]
    for sarki in sarkilar:
        process_song_automatically(sarki)