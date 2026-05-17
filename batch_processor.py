import pandas as pd
import time
from tqdm import tqdm
import os
from dotenv import load_dotenv

load_dotenv()

# Kendi yazdığın fonksiyonu paket olarak içe aktarıyorsun
from lyrics_pipeline import fetch_single_lyrics

# AYARLAR
GENIUS_TOKEN = os.getenv("GENIUS_TOKEN")
CSV_PATH = "som_results/raw_music_data_v2.csv"
SAVE_INTERVAL = 50  # Her 50 şarkıda bir kaydet


def process_dataset():
    print("Veri seti yükleniyor...")
    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        print(f"Hata: {CSV_PATH} bulunamadı!")
        return

    # Backend'in beklediği sütunlar yoksa oluştur
    if 'clean_lyrics' not in df.columns:
        df['clean_lyrics'] = None
    if 'language' not in df.columns:
        df['language'] = None

    # Sadece sözleri henüz çekilmemiş olanları filtrele
    missing_idx = df[df['clean_lyrics'].isna()].index

    print(f"Toplam şarkı: {len(df)} | Eksik şarkı: {len(missing_idx)}")
    if len(missing_idx) == 0:
        print("Çekilecek yeni şarkı yok. Her şey tamam!")
        return

    print("Şarkı sözü indirme işlemi başlatılıyor...\n")
    save_counter = 0

    # tqdm ile görsel ilerleme çubuğu
    for idx in tqdm(missing_idx, desc="İşleniyor"):
        artist = str(df.loc[idx, 'artist'])
        title = str(df.loc[idx, 'title'])

        # SENİN FONKSİYONUNU ÇAĞIRIYORUZ
        result = fetch_single_lyrics(title, artist, GENIUS_TOKEN)

        if result:
            # Fonksiyonun başarılı olursa sözleri ve dili kaydet
            df.loc[idx, 'clean_lyrics'] = result['clean_lyrics']
            df.loc[idx, 'language'] = result['detected_language']
        else:
            # Bulunamazsa veya yabancı dilse es geçmek için işaretle
            df.loc[idx, 'clean_lyrics'] = "BULUNAMADI"
            df.loc[idx, 'language'] = "unknown"

        save_counter += 1

        # Olası bir çökmeye karşı belirli aralıklarla CSV'yi kaydet
        if save_counter % SAVE_INTERVAL == 0:
            df.to_csv(CSV_PATH, index=False)

        # API'yi çok yormamak için her istek arasına minik bir nefes koyuyoruz
        time.sleep(0.5)

    # Döngü bitince son durumu kesin kaydet
    df.to_csv(CSV_PATH, index=False)
    print("\n🎉 Bütün şarkıların söz çekme işlemi başarıyla tamamlandı!")


if __name__ == "__main__":
    process_dataset()