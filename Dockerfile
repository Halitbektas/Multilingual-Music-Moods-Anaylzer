# Python 3.11 tabanlı güncel bir Linux imajı kullanıyoruz
FROM python:3.11-slim

# Gerekli sistem araçlarını ve FFmpeg'i kuruyoruz
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Çalışma dizinini ayarla
WORKDIR /app

# Kütüphaneleri kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını konteynerin içine kopyala
COPY . .

# Konteyner çalıştığında extractor'ı başlat
CMD ["python", "auto_extractor.py"]