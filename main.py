
from lyrics_pipeline import build_lyrics_dataset


GENIUS_TOKEN = "GENIUS-TOKEN'INIZI_BURAYA_YAPISTIRIN"
sarkilar = [
    ("Saygımdan", "Bengü"),
    ("505", "Arctic Monkeys")
]


df_lyrics = build_lyrics_dataset(sarkilar, GENIUS_TOKEN, "feature_fusion_lyrics.csv")


print("\n--- BERT MİMARİSİNE GİDECEK VERİ ---")
print(df_lyrics.head())

