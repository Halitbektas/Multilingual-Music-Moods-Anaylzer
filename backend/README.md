# MMMA Backend — Çok Dilli Müzik Duygu Analiz Sistemi

FastAPI tabanlı backend. Eğittiğin SOM modeline frontend'in HTTP üzerinden erişebilmesi için 5 endpoint sunar.

## Klasör Yapısı

```
mmma_backend/
├── app/
│   ├── main.py              # FastAPI uygulaması + endpoint'ler
│   ├── config.py            # .env'den ayarları okur
│   ├── ml_loader.py         # SOM + scaler + PCA'yı bellekte tutan singleton
│   ├── models.py            # Pydantic request/response şemaları
│   └── services/
│       ├── analyzer_service.py     # /api/analyze
│       ├── som_service.py          # /api/cell/neighbors
│       ├── musical_dna_service.py  # /api/musical-dna/{song_id}
│       ├── wordcloud_service.py    # /api/cell/wordcloud
│       ├── journey_service.py      # /api/journey
│       └── spotify_service.py      # Spotipy entegrasyonu (preview + albüm görseli)
├── som_results/             # Buraya .pkl dosyalarını koy (aşağıda detay)
├── requirements.txt
├── .env.example
└── README.md
```

## Kurulum

### 1. Sanal ortam + bağımlılıklar

```bash
cd mmma_backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Model dosyalarını yerleştir

`som_results/` klasörüne şu dosyaları kopyala (eğitim pipeline'ından çıktılar):

- `mmma_som_model_final.pkl` — eğitilmiş MiniSom (20x20)
- `laser_scaler.pkl` — LASER embedding'leri için StandardScaler
- `laser_pca_model.pkl` — LASER için PCA
- `final_som_scaler.pkl` — SOM giriş vektörü için son scaler
- `som_music_database.csv` — her şarkının `winner_x`, `winner_y` ile eşleştirildiği veri

Ek olarak proje kökünde `raw_music_dataset.csv` bulunmalı — bu dosya, kelime bulutu özelliği için `clean_lyrics` sütununu içeriyor olmalı (aşağıdaki **Bilinen Sınırlamalar**'a bak).

### 3. .env dosyası

```bash
cp .env.example .env
```

Sonra `.env` dosyasını aç ve doldur:

```env
SPOTIFY_CLIENT_ID=xxxxxxxxxxxx
SPOTIFY_CLIENT_SECRET=xxxxxxxxxxxx
GENIUS_TOKEN=xxxxxxxxxxxx          # şu an opsiyonel
ALLOWED_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

**Spotify credentials almak için:** https://developer.spotify.com/dashboard → Create app → Client ID + Client Secret. Redirect URI gerekmez çünkü Client Credentials Flow kullanıyoruz (sadece public veri okuyor, kullanıcı playlist'ine yazmıyor).

`ALLOWED_ORIGINS` — frontend'i hangi adresten servis edeceksen onu yaz. VSCode Live Server varsayılan `http://localhost:5500` ya da `http://127.0.0.1:5500` kullanır.

### 4. Çalıştır

```bash
uvicorn app.main:app --reload --port 8000
```

Açıldığında:
- API: http://localhost:8000
- Otomatik Swagger UI: http://localhost:8000/docs ← her endpoint'i buradan test edebilirsin
- Health check: http://localhost:8000/health

İlk istek geldiğinde ML modelleri belleğe yüklenir (lifespan startup); birkaç saniye sürebilir.

## API Endpoint'leri

### `POST /api/analyze`
Şarkıyı SOM'da konumlandırır, hücredeki duygu dağılımını ve audio feature'larını döner.

**Request:**
```json
{ "spotify_url": "https://open.spotify.com/track/..." }
```
veya
```json
{ "artist": "Sezen Aksu", "title": "Firuze" }
```

**Response:** koordinatlar, mood prediction, audio features (radar için), mood distribution, lyrics analysis.

### `GET /api/cell/neighbors?x=10&y=10&limit=8&exclude_song_id=...`
Belirtilen hücredeki diğer şarkıları döner (Spotify metadata ile zenginleştirilmiş).

### `GET /api/musical-dna/{song_id}`
Tek bir şarkının 6 feature değeri vs. bulunduğu hücrenin ortalaması — radar grafik için.

### `GET /api/cell/wordcloud?x=10&y=10&top_n=50`
Hücredeki şarkıların lyrics'lerinden en sık geçen kelimeler (Türkçe + İngilizce stopword filtreli).

### `POST /api/journey`
Bir hücreden diğerine kademeli geçiş playlist'i.

**Request:**
```json
{ "start_x": 0, "start_y": 0, "end_x": 19, "end_y": 19, "steps": 5 }
```

**Response:** her adım için bir şarkı + otomatik üretilmiş Türkçe anlatı.

Hepsinin tam şeması Swagger'da: http://localhost:8000/docs

## Frontend'i Bağlamak

Frontend dosyalarını (`index.html`, `styles.css`, `styles-extra.css`, `script.js`) ayrı bir klasörden servis et:

- **VSCode Live Server** en kolayı — `index.html`'e sağ tıkla → "Open with Live Server"
- ya da `python -m http.server 5500` o klasörde

`script.js` içindeki `API_BASE` otomatik algılıyor — eğer frontend 8000 portunda servis edilmiyorsa `http://localhost:8000`'e gidiyor.

`.env` dosyandaki `ALLOWED_ORIGINS` değerinde frontend'in adresi yazıyor olmalı, yoksa CORS hatası alırsın.

## Bilinen Sınırlamalar / Sonraki Adımlar

**1. Kelime bulutu için `clean_lyrics` sütunu**
Şu an `raw_music_dataset.csv`'de embedding'ler var ama temizlenmiş lyrics text'i yok. Kelime bulutu çalışsın diye `clean_lyrics` sütununu CSV'ye ekle. Yoksa endpoint boş liste döner (hata vermez).

**2. Mood label'ları kural tabanlı**
`analyzer_service._quadrant_label` şu an SOM grid'ini 3x3'e bölüp manuel etiketliyor (Mutlu/Enerjik/Sakin/Melankolik vs.). Eğitim sırasında her hücreye gerçek etiket atadıysan, bunu JSON map'e çevirip oradan oku. Değişmesi gereken tek fonksiyon bu.

**3. Audio feature scaling aralıkları tahmin**
`analyzer_service._audio_features_for_song` içindeki min/max değerleri (tempo 60-180, energy_rms 0.02-0.15, vb.) datasetinin gerçek dağılımına göre güncelle — şu an radar grafik mantıklı görünsün diye konulmuş tahminler.

**4. Yeni şarkı analizi henüz aktif değil**
MVP'de sadece DB'deki şarkılar analiz edilebiliyor. Spotify URL veya artist+title DB'de yoksa "yakında" hatası dönüyor. On-the-fly path için gerekli parçalar zaten elinde:
- `audio_fetcher.py` → YouTube'dan indirme
- `nlp_pipeline.py` → LASER embedding
- `som.winner()` → SOM'da hücre bulma

İstersen bir sonraki adımda bu glue'yu yazabiliriz (5-10 sn sürer, async task queue'ya alınması gerekir).

**5. "Save to Spotify" butonu yok**
Journey playlist'i Spotify hesabına kaydetmek user OAuth gerektiriyor (scope: `playlist-modify-public`). Şu anki Client Credentials Flow sadece public veri okuyabiliyor. Eklenebilir ama redirect URI + giriş ekranı işin içine giriyor.

## Test

Swagger UI'dan elle test edebilirsin (http://localhost:8000/docs). Health check için:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

## Sorun Giderme

| Hata | Sebep | Çözüm |
|---|---|---|
| `FileNotFoundError: mmma_som_model_final.pkl` | Model dosyaları eksik | `som_results/` klasörüne `.pkl`'leri koy |
| `ValueError: SOM weights shape` | MiniSom versiyon uyuşmazlığı | `pip install minisom==2.3.1` (eğittiğin versiyonla aynı) |
| Frontend'de CORS hatası | `.env`'de origins eksik | `ALLOWED_ORIGINS`'a frontend URL'ini ekle, sunucuyu yeniden başlat |
| `Spotify credentials missing` warning | `.env` boş | Endpoint yine çalışır ama albüm görseli/preview gelmez |
| `/api/analyze` 404 "yakında" | Şarkı DB'de değil | Şimdilik DB'deki şarkılarla test et |
