import librosa
import numpy as np

print("Kütüphaneler yüklendi, test başlıyor...")

try:
    path = librosa.ex('trumpet')
    y, sr = librosa.load(path, duration=5)

    # Tempo değerini alırken float'a zorlayalım (Hata burada çıkıyordu)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo_value = float(tempo)  # Diziden tekil sayıya çeviriyoruz

    print("-" * 30)
    print("BAŞARILI!")
    print(f"Örnek sesin temposu: {tempo_value:.2f} BPM")
    print(f"Ses dizisi boyutu (Sinyal uzunluğu): {y.shape}")
    print("-" * 30)
except Exception as e:
                import traceback
                print(f"{file_name} analiz edilirken hata oluştu: {e}")
                traceback.print_exc() # Hatanın tam yerini ve nedenini gösterir