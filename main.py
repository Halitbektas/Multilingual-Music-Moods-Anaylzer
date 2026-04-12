# arkadaşının_main_dosyası.py
from lyrics_pipeline import build_lyrics_dataset

# 1. Ayarlar
GENIUS_TOKEN = "GENIUS-TOKEN'INIZI_BURAYA_YAPISTIRIN"
sarkilar = [
    ("Saygımdan", "Bengü"),
    ("505", "Arctic Monkeys")
]

# 2. Senin yazdığın muazzam pipeline'ı tek satırda çağırıyor
df_lyrics = build_lyrics_dataset(sarkilar, GENIUS_TOKEN, "feature_fusion_lyrics.csv")

# 3. Kendi modeline bu tabloyu doğrudan yolluyor!
print("\n--- BERT MİMARİSİNE GİDECEK VERİ ---")
print(df_lyrics.head())

# Arkadaşın artık buradan df_lyrics['clean_lyrics'] sütununu alıp BERT modeline sokabilir.