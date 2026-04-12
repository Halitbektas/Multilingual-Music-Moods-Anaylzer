import librosa
import numpy as np
import pandas as pd
import os
import traceback


def extract_features(folder_path):
    data_list = []
    print(f"'{folder_path}' klasörü taranıyor...")

    if not os.path.exists(folder_path):
        print(f"HATA: {folder_path} klasörü bulunamadı!")
        return

    for file_name in os.listdir(folder_path):
        if file_name.endswith(('.mp3', '.wav', '.m4a')):
            file_path = os.path.join(folder_path, file_name)
            print(f"--- Analiz ediliyor: {file_name} ---")

            try:
                # Sesi yükle
                y, sr = librosa.load(file_path, duration=30)

                # 1. MFCC
                mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
                mfccs_mean = np.mean(mfccs, axis=1)

                # 2. Chroma
                chroma = librosa.feature.chroma_stft(y=y, sr=sr)
                chroma_mean = np.mean(chroma, axis=1)

                # 3. Tempo (Hata payı en yüksek yer burası, güvenli alıyoruz)
                tempo_data = librosa.beat.beat_track(y=y, sr=sr)
                # Librosa versiyonuna göre tempo ilk veya ikinci değer olabilir
                tempo = tempo_data[0] if isinstance(tempo_data, (list, tuple)) else tempo_data
                tempo_value = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)

                # 4. Enerji ve Diğerleri
                rms = np.mean(librosa.feature.rms(y=y))
                cent = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))

                features = {
                    "file_name": file_name,
                    "tempo": tempo_value,
                    "energy_rms": rms,
                    "spectral_centroid": cent,
                }

                for i, m in enumerate(mfccs_mean):
                    features[f"mfcc_{i}"] = m
                for i, c in enumerate(chroma_mean):
                    features[f"chroma_{i}"] = c

                data_list.append(features)
                print(f"BAŞARILI: {file_name} verileri eklendi.")

            except Exception as e:
                print(f"HATA ({file_name}): {e}")
                traceback.print_exc()  # Hatanın tam yerini terminale basar

    if data_list:
        df = pd.DataFrame(data_list)
        df.to_csv("music_features.csv", index=False)
        print(f"\nİşlem bitti! {len(data_list)} şarkı 'music_features.csv' dosyasına kaydedildi.")
    else:
        print("\nUYARI: Hiçbir şarkı analiz edilemedi, liste boş.")


if __name__ == "__main__":
    extract_features("songs")