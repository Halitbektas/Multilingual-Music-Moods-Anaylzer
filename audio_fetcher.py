# audio_fetcher.py
import yt_dlp
import os

def download_mp3(song_title, artist_name, output_folder="audio_files"):
    """
    YouTube üzerinden şarkıyı aratır, en iyi ses kalitesinde bulur ve MP3 olarak indirir.
    
    Parametreler:
        song_title (str): Şarkı adı
        artist_name (str): Sanatçı adı
        output_folder (str): MP3'lerin kaydedileceği klasör adı
        
    Dönüş:
        str: Başarılı olursa dosyanın tam yolunu, başarısız olursa None döndürür.
    """
    
    # Eğer kaydedilecek klasör yoksa otomatik oluştur
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    # YouTube'da arama yapacağımız metin (ytsearch1: sadece ilk ve en iyi sonucu getir demek)
    search_query = f"ytsearch1:{artist_name} {song_title} official audio"
    
    # Dosyanın ismini "Sanatçı - Şarkı Adı.mp3" formatında ayarlıyoruz
    # Windows dosya isimlerinde geçersiz olabilecek karakterleri temizlemek iyi bir pratiktir
    safe_title = "".join([c for c in song_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    safe_artist = "".join([c for c in artist_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    file_name = f"{safe_artist} - {safe_title}"
    output_path = os.path.join(output_folder, f"{file_name}.%(ext)s")

    # yt-dlp ayarları
    ydl_opts = {
        'format': 'bestaudio/best', # Sadece sesi, en iyi kalitede al
        'outtmpl': output_path,     # Çıktı adı ve konumu
        'noplaylist': True,         # Oynatma listesi indirmeyi engelle
        'quiet': True,              # Terminali gereksiz yazılarla doldurma
        'no_warnings': True,
        'postprocessors': [{        # Sesi MP3'e dönüştüren eklenti (FFmpeg gerektirir)
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192', # 192kbps Librosa frekans analizi için gayet yeterlidir
        }],
    }

    print(f"🎵 Ses İndiriliyor: {artist_name} - {song_title} ...", end=" ")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_query])
            
        # İnen dosyanın son (MP3) yolunu oluştur
        final_mp3_path = os.path.join(output_folder, f"{file_name}.mp3")
        print("[BAŞARILI]")
        return final_mp3_path
        
    except Exception as e:
        print(f"[HATA] İndirilemedi. Sebep: {str(e)}")
        return None

# === TEST BÖLÜMÜ ===
if __name__ == "__main__":
    # Test için bir şarkı deneyelim
    indirme_yolu = download_mp3("Saygımdan", "Bengü")
    if indirme_yolu:
        print(f"Dosya şu konuma kaydedildi: {os.path.abspath(indirme_yolu)}")