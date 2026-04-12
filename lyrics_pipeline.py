# lyrics_pipeline.py
import lyricsgenius
from langdetect import detect, LangDetectException
import re
import pandas as pd

def clean_lyrics(raw_lyrics):
    text = re.sub(r'\[.*?\]', '', raw_lyrics)
    text = re.sub(r'\d*Embed$', '', text)    
    text = text.replace('\n', ' ')          
    text = re.sub(r'\s+', ' ', text).strip()  
    return text.lower()                     

def build_lyrics_dataset(songs_list, api_token, output_csv="clean_lyrics_dataset.csv"):
    """
    Şarkı listesini alır, Genius'tan çeker, dilini kontrol eder, temizler 
    ve makine öğrenmesi için hazır bir Pandas DataFrame döndürür.
    
    Parametreler:
        songs_list (list of tuples): [("Şarkı Adı", "Sanatçı"), ...]
        api_token (str): Genius API Token
        output_csv (str): Çıktı olarak kaydedilecek CSV dosyasının adı
        
    Dönüş:
        pd.DataFrame: Temizlenmiş veriyi içeren tablo
    """
    genius = lyricsgenius.Genius(api_token)
    genius.verbose = False
    genius.remove_playlists = True 
    genius.timeout = 15
    genius.retries = 3
    
    processed_data = []
    
    print("Şarkılar Genius'tan çekiliyor ve temizleniyor...\n" + "-"*40)
    
    for title, artist in songs_list:
        print(f"-> İşleniyor: {artist} - {title}", end=" ... ")
        
        try:
            song = genius.search_song(title, artist)
            
            if song is None:
                print("[HATA: Bulunamadı]")
                continue
                
            lyrics_text = song.lyrics
            
            try:
                detected_lang = detect(lyrics_text)
            except LangDetectException:
                print("[HATA: Dil tespiti başarısız]")
                continue
                
            if detected_lang in ['en', 'tr']:
                cleaned_text = clean_lyrics(lyrics_text)
                processed_data.append({
                    "title": song.title,
                    "artist": song.artist,
                    "detected_language": detected_lang,
                    "clean_lyrics": cleaned_text
                })
                print(f"[BAŞARILI] (Dil: {detected_lang})")
            else:
                print(f"[ATLANDI: Hedef dil değil ({detected_lang})]")
                
        except Exception as e:
            print(f"[HATA: {str(e)}]")

    print("-" * 40)
    if len(processed_data) > 0:
        df = pd.DataFrame(processed_data)
        df.to_csv(output_csv, index=False, encoding='utf-8')
        print(f"Harika! Toplam {len(df)} şarkı işlendi ve '{output_csv}' olarak kaydedildi.")
        return df
    else:
        print("Hiç şarkı işlenemediği için DataFrame oluşturulamadı.")
        return pd.DataFrame()