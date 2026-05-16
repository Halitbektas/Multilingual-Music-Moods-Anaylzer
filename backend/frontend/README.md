# MMMA Frontend

Vanilla HTML/CSS/JS — mevcut Spotify temalı UI'a Spotify preview, Musical DNA radar, kelime bulutu, komşu şarkılar ve yolculuk playlist'i özellikleri eklendi.

## Dosyalar

- `index.html` — yapı (orijinal düzen korundu, yeni section'lar eklendi)
- `styles.css` — orijinal stil (değişmedi)
- `styles-extra.css` — yeni özellikler için ek stiller (sadece ekleme, override yok)
- `script.js` — tam yeniden yazım, gerçek API'ye bağlı

## Çalıştırma

Backend'i önce `mmma_backend/` içinden başlat (oradaki README'ye bak), sonra:

**VSCode Live Server (en kolayı):**
`index.html`'e sağ tıkla → "Open with Live Server"

**veya komut satırından:**
```bash
cd mmma_frontend
python -m http.server 5500
```

Sonra http://localhost:5500 adresine git.

## Backend Adresi

`script.js` içindeki `API_BASE` otomatik algılıyor:
- Frontend 8000'de servisleniyorsa → boş (aynı origin)
- Başka bir portta servisleniyorsa → `http://localhost:8000`

Backend'i farklı bir host/port'ta çalıştırıyorsan `script.js` başındaki `API_BASE` değerini değiştir.

## CORS Notu

Backend `.env` dosyasındaki `ALLOWED_ORIGINS` değeri bu frontend'in URL'ini içermeli (örn. `http://localhost:5500`). Aksi halde tarayıcı isteği keser.
