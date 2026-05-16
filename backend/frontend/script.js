/* ═════════════════════════════════════════════════════════════════════════
   MMMA Frontend — Backend API entegrasyonu
   ═════════════════════════════════════════════════════════════════════════

   Yapı:
     1) DOM referansları & state
     2) API katmanı (fetch wrapper)
     3) Form handling (mode switch, validation, submit)
     4) Loading state animasyonu (artık gerçek API gecikmesine bağlı)
     5) Renderers — result section'larını dolduran fonksiyonlar
     6) Charts — radar (çift seri), mood bars, lyrics bars
     7) Extras — neighbors, wordcloud, journey planner
   ═════════════════════════════════════════════════════════════════════════ */


// ── 1) DOM ────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const body = document.body;
const themeToggle = $('themeToggle');
const tabButtons = document.querySelectorAll('.tab-btn');
const spotifyPanel = $('spotifyPanel');
const manualPanel = $('manualPanel');
const spotifyUrlInput = $('spotifyUrl');
const artistInput = $('artistName');
const songInput = $('songName');
const analyzeBtn = $('analyzeBtn');
const analysisForm = $('analysisForm');

const emptyState = $('emptyState');
const loadingState = $('loadingState');
const resultsSection = $('resultsSection');

const errorBanner = $('errorBanner');
const progressFill = $('progressFill');
const loadingSteps = [...document.querySelectorAll('#loadingSteps li')];

let currentMode = 'spotify';
let loadingTimer = null;
let loadingIndex = 0;

// Son analiz sonucu — journey/neighbors/wordcloud bunu kullanır
let currentAnalysis = null;

// API base URL — backend'in nerede koştuğuna göre değiştir
const API_BASE = '';


// ── 2) API katmanı ────────────────────────────────────────────────────────
// ── 2) API katmanı ────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const timeout = options.timeout || 30000; // Varsayılan 30 saniye
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);

  const url = API_BASE + path;
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      signal: controller.signal,
      ...options,
    });
    clearTimeout(id);

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body.detail || JSON.stringify(body);
      } catch { /* yoksay */ }
      throw new Error(detail);
    }
    return res.json();
  } catch (err) {
    clearTimeout(id);
    if (err.name === 'AbortError') {
      throw new Error('İstek zaman aşımına uğradı (Analiz çok uzun sürdü, lütfen tekrar deneyin).');
    }
    throw err;
  }
}

const API = {
  // Analiz işlemi yeni şarkılarda 60 saniye sürebileceği için timeout'u 90 sn yapıyoruz
  analyze: (payload) => apiFetch('/api/analyze', { 
      method: 'POST', 
      body: JSON.stringify(payload),
      timeout: 90000 // 90 Saniye
  }),
  neighbors: (x, y, limit = 12, excludeId = null) => {
    const params = new URLSearchParams({ x, y, limit, enrich: 'true' });
    if (excludeId) params.set('exclude_song_id', excludeId);
    return apiFetch(`/api/cell/neighbors?${params}`);
  },
  musicalDNA: (songId) => apiFetch(`/api/musical-dna/${encodeURIComponent(songId)}`),
  wordcloud: (x, y, topN = 60) => apiFetch(`/api/cell/wordcloud?x=${x}&y=${y}&top_n=${topN}`),
  journey: (sx, sy, ex, ey, steps = 8) => apiFetch('/api/journey', {
    method: 'POST',
    body: JSON.stringify({ start_x: sx, start_y: sy, end_x: ex, end_y: ey, steps }),
  }),
};


// ── 3) Form handling ──────────────────────────────────────────────────────
function setTheme(next) {
  body.setAttribute('data-theme', next);
  localStorage.setItem('mmm-theme', next);
}

function initTheme() {
  const saved = localStorage.getItem('mmm-theme');
  if (saved) setTheme(saved);
}

function setMode(mode) {
  currentMode = mode;
  tabButtons.forEach(btn => {
    const active = btn.dataset.mode === mode;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  spotifyPanel.classList.toggle('hidden', mode !== 'spotify');
  manualPanel.classList.toggle('hidden', mode !== 'manual');
  validateForm();
}

function validateForm() {
  const validSpotify = spotifyUrlInput.value.trim().length > 0;
  const validManual = artistInput.value.trim() && songInput.value.trim();
  analyzeBtn.disabled = currentMode === 'spotify' ? !validSpotify : !validManual;
}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.remove('hidden');
}
function clearError() { errorBanner.classList.add('hidden'); }


// ── 4) Loading state ──────────────────────────────────────────────────────
let loadingSeconds = 0; // Geçen saniyeyi tutmak için

function updateLoadingStep(index) {
  loadingSteps.forEach((step, i) => {
    step.classList.toggle('active', i === index);
    step.classList.toggle('done', i < index);
  });
  const progress = [24, 46, 68, 92];
  progressFill.style.width = `${progress[index] || 24}%`;
}

function resetLoading() {
  if (loadingTimer) clearInterval(loadingTimer);
  loadingIndex = 0;
  loadingSeconds = 0;
  updateLoadingStep(0);
  
  // Varsa eski bilgilendirme mesajını temizle
  const hint = $('aiLoadingHint');
  if (hint) hint.remove();
}

function showLoadingState() {
  clearError();
  emptyState.classList.add('hidden');
  resultsSection.classList.add('hidden');
  loadingState.classList.remove('hidden');
  resetLoading();

  loadingTimer = setInterval(() => {
    loadingSeconds += 1;
    
    // Animasyonu her 1 saniyede bir kademe ilerlet
    if (loadingIndex < loadingSteps.length - 1) {
        loadingIndex += 1;
        updateLoadingStep(loadingIndex);
    } else {
        progressFill.style.width = '94%'; // Sonda bekle
    }

    // 4 Saniyeyi geçtiyse (Şarkı DB'de yok demektir, AI devreye girmiştir)
    if (loadingSeconds === 4) {
        const hint = document.createElement('div');
        hint.id = 'aiLoadingHint';
        hint.innerHTML = '✨ <b>Yapay Zeka Devrede!</b><br>Şarkı indiriliyor ve sözleri analiz ediliyor. Bu işlem 30-60 saniye sürebilir, lütfen sekmeden ayrılmayın...';
        
        // Estetik ayarlar (Kendi CSS sınıflarına göre değiştirebilirsin)
        hint.style.color = '#00e4a8';
        hint.style.marginTop = '1.5rem';
        hint.style.fontSize = '0.95rem';
        hint.style.textAlign = 'center';
        hint.style.lineHeight = '1.5';
        hint.style.animation = 'pulse 2s infinite';
        
        loadingState.appendChild(hint);
    }
  }, 1000); // 600ms yerine 1 saniyeye çıkardık
}

function hideLoading() {
  if (loadingTimer) clearInterval(loadingTimer);
  loadingState.classList.add('hidden');
  const hint = $('aiLoadingHint');
  if (hint) hint.remove();
}


// ── 5) Renderers ──────────────────────────────────────────────────────────
function renderAnalysis(data) {
  currentAnalysis = data;

  // Mood card
  $('moodTitle').textContent = data.mood.label;
  $('confidenceValue').textContent = `${data.mood.confidence}%`;
  $('intensityValue').textContent = `${data.mood.intensity}%`;
  $('confidenceBar').style.width = `${data.mood.confidence}%`;
  $('intensityBar').style.width = `${data.mood.intensity}%`;
  $('footnote').textContent = data.mood.footnote;

  // Song card
  $('songTitle').textContent = data.song.title;
  $('artistTitle').textContent = data.song.artist;
  $('sourceValue').textContent = data.song.source;
  $('languageValue').textContent = languageLabel(data.song.language);

  const sourceEl = $('sourceValue');
  if (data.song.source === 'on_the_fly') {
    sourceEl.innerHTML = '<span style="background: rgba(0, 228, 168, 0.2); color: #00e4a8; padding: 2px 8px; border-radius: 12px; font-weight: bold;">✨ Yapay Zeka (Anlık)</span>';
  } else {
    sourceEl.textContent = 'Veritabanı';
  }

  // Album art + preview
  const albumArt = $('albumArt');
  if (data.song.album_art_url) {
    albumArt.src = data.song.album_art_url;
    albumArt.classList.remove('hidden');
  } else {
    albumArt.classList.add('hidden');
  }

  const previewPlayer = $('previewPlayer');
  const previewAudio = $('previewAudio');
  const spotifyLink = $('spotifyOpenLink');
  if (data.song.spotify_preview_url) {
    previewAudio.src = data.song.spotify_preview_url;
    previewPlayer.classList.remove('hidden');
  } else {
    previewAudio.removeAttribute('src');
    previewPlayer.classList.add('hidden');
  }
  if (data.song.spotify_url) {
    spotifyLink.href = data.song.spotify_url;
    spotifyLink.classList.remove('hidden');
  } else {
    spotifyLink.classList.add('hidden');
  }

  // SOM marker — koordinatları SOM grid'inin yüzdesine çevir
  const SOM_SIZE = 20; // backend grid_x/grid_y eşleşmeli
  const px = ((data.coordinates.x + 0.5) / SOM_SIZE) * 100;
  const py = ((data.coordinates.y + 0.5) / SOM_SIZE) * 100;
  $('coordChip').textContent = `Konum: ${data.coordinates.text}`;
  const marker = $('songMarker');
  marker.style.setProperty('--marker-x', `${px}%`);
  marker.style.setProperty('--marker-y', `${py}%`);

  // Journey planner: başlangıç hücresini kilitle
  const journeyStart = $('journeyStart');
  journeyStart.textContent = `(${data.coordinates.x}, ${data.coordinates.y})`;
  journeyStart.dataset.x = data.coordinates.x;
  journeyStart.dataset.y = data.coordinates.y;

  resultsSection.classList.remove('hidden');
  hideLoading();
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Asenkron yan içerikler — paralel başlat
  loadMusicalDNA(data.song.song_id);
  loadNeighbors(data.coordinates.x, data.coordinates.y, data.song.song_id);
  loadWordCloud(data.coordinates.x, data.coordinates.y);
}

function languageLabel(code) {
  const map = { tr: 'Türkçe', en: 'İngilizce' };
  return map[code?.toLowerCase()] || code || '—';
}


// ── 6) Charts ─────────────────────────────────────────────────────────────
const radarLabels = ['Enerji', 'Tempo', 'Parlaklık', 'MFCC', 'Tını', 'Renk'];

function renderRadar(songValues, cellAverages = null) {
  const svg = $('radarChart');
  const width = 420, height = 320, cx = 210, cy = 165, maxRadius = 110, levels = 4;
  svg.innerHTML = '';

  // Grid katmanları
  for (let lv = 1; lv <= levels; lv++) {
    const r = (maxRadius / levels) * lv;
    const pts = radarLabels.map((_, i) => {
      const a = (-Math.PI / 2) + (i * Math.PI * 2 / radarLabels.length);
      return `${cx + Math.cos(a) * r},${cy + Math.sin(a) * r}`;
    }).join(' ');
    appendSVG(svg, 'polygon', {
      points: pts, fill: 'none',
      stroke: 'rgba(127, 148, 180, 0.28)', 'stroke-width': '1',
    });
  }

  // Eksenler + etiketler
  radarLabels.forEach((label, i) => {
    const a = (-Math.PI / 2) + (i * Math.PI * 2 / radarLabels.length);
    const x = cx + Math.cos(a) * maxRadius;
    const y = cy + Math.sin(a) * maxRadius;
    appendSVG(svg, 'line', {
      x1: cx, y1: cy, x2: x, y2: y,
      stroke: 'rgba(127, 148, 180, 0.28)', 'stroke-width': '1',
    });
    appendSVG(svg, 'text', {
      x: cx + Math.cos(a) * (maxRadius + 24),
      y: cy + Math.sin(a) * (maxRadius + 24),
      fill: 'var(--text-soft)', 'font-size': '13', 'text-anchor': 'middle',
    }, label);
  });

  // Hücre ortalaması (önce çiz, altta kalsın)
  if (cellAverages) {
    const pts = cellAverages.map((v, i) => {
      const a = (-Math.PI / 2) + (i * Math.PI * 2 / radarLabels.length);
      const r = (v / 100) * maxRadius;
      return `${cx + Math.cos(a) * r},${cy + Math.sin(a) * r}`;
    }).join(' ');
    appendSVG(svg, 'polygon', {
      points: pts,
      fill: 'rgba(24, 199, 255, 0.18)',
      stroke: '#18c7ff', 'stroke-width': '2', 'stroke-dasharray': '4 3',
    });
  }

  // Şarkı değerleri
  const pts = songValues.map((v, i) => {
    const a = (-Math.PI / 2) + (i * Math.PI * 2 / radarLabels.length);
    const r = (v / 100) * maxRadius;
    return `${cx + Math.cos(a) * r},${cy + Math.sin(a) * r}`;
  }).join(' ');
  appendSVG(svg, 'polygon', {
    points: pts,
    fill: 'rgba(0, 228, 168, 0.32)',
    stroke: '#00e4a8', 'stroke-width': '2.5',
  });
}

function appendSVG(parent, tag, attrs, text = null) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  if (text !== null) el.textContent = text;
  parent.appendChild(el);
  return el;
}


// ── 7) Async extras ───────────────────────────────────────────────────────
async function loadMusicalDNA(songId) {
  try {
    const dna = await API.musicalDNA(songId);
    const songVals = dna.dna.map(d => d.song_value);
    const cellAvgs = dna.dna.map(d => d.cell_average);
    renderRadar(songVals, cellAvgs);
    const sim = computeSimilarity(songVals, cellAvgs);
    $('dnaCaption').textContent =
      `Bu şarkı bulunduğu hücreye %${sim} oranında uyuyor — ` +
      `aynı hücredeki ${dna.cell_size} şarkıyla karşılaştırıldı.`;
  } catch (e) {
    console.warn('Musical DNA yüklenemedi:', e.message);
    // Fallback — sadece şarkıyı çiz
    if (currentAnalysis) {
      const f = currentAnalysis.audio_features;
      renderRadar([f.energy, f.tempo, f.danceability, f.acousticness, f.loudness, f.valence]);
    }
  }
}

function computeSimilarity(a, b) {
  // İki vektör arasında ortalama mutlak fark → benzerlik yüzdesi
  if (a.length !== b.length || a.length === 0) return 0;
  let totalDiff = 0;
  for (let i = 0; i < a.length; i++) totalDiff += Math.abs(a[i] - b[i]);
  const avgDiff = totalDiff / a.length;
  return Math.max(0, Math.round(100 - avgDiff));
}

async function loadNeighbors(x, y, excludeId) {
  const grid = $('neighborsGrid');
  grid.innerHTML = '<p class="muted">Yükleniyor…</p>';
  try {
    const res = await API.neighbors(x, y, 12, excludeId);
    $('neighborsCount').textContent = `· ${res.total_in_cell} şarkı`;
    grid.innerHTML = '';
    if (res.neighbors.length === 0) {
      grid.innerHTML = '<p class="muted">Bu hücrede başka şarkı yok.</p>';
      return;
    }
    res.neighbors.forEach(n => grid.appendChild(makeNeighborCard(n)));
  } catch (e) {
    grid.innerHTML = `<p class="muted">Komşular yüklenemedi: ${e.message}</p>`;
  }
}

function makeNeighborCard(n) {
  const card = document.createElement('div');
  card.className = 'neighbor-card' + (n.spotify_preview_url ? '' : ' no-preview');
  const imgSrc = n.album_art_url || transparentPixel();
  card.innerHTML = `
    <img src="${escapeHtml(imgSrc)}" alt="${escapeHtml(n.title)}" loading="lazy" />
    <div class="neighbor-title" title="${escapeHtml(n.title)}">${escapeHtml(n.title)}</div>
    <div class="neighbor-artist">${escapeHtml(n.artist)}</div>
    ${n.spotify_preview_url
      ? `<audio controls preload="none" src="${escapeHtml(n.spotify_preview_url)}"></audio>`
      : ''}
  `;
  if (n.spotify_url) {
    card.addEventListener('click', (e) => {
      if (e.target.tagName === 'AUDIO') return; // audio kontrollerine müdahale etme
      window.open(n.spotify_url, '_blank', 'noopener');
    });
  }
  return card;
}

function renderWordCloudWords(words) {
  const wc = $('wordCloud');
  wc.innerHTML = '';
  if (!words.length) {
    wc.innerHTML = '<span class="empty-state">Kelime bulutu için yeterli veri yok.</span>';
    return;
  }
  const maxWeight = words[0].weight;
  words.forEach(({ word, weight }) => {
    const ratio = weight / maxWeight;
    const fontSize = 14 + ratio * 38;
    const hue = 160 + Math.floor(ratio * 60);
    const span = document.createElement('span');
    span.className = 'wc-item';
    span.textContent = word;
    span.style.fontSize = `${fontSize.toFixed(1)}px`;
    span.style.color = `hsl(${hue}, 70%, 65%)`;
    span.style.opacity = (0.55 + ratio * 0.45).toFixed(2);
    span.title = `${word} — ${weight} kez geçti`;
    wc.appendChild(span);
  });
}

async function loadWordCloud(x, y) {
  const wc = $('wordCloud');
  const heading = document.querySelector('#wordCloudCard h3');

  // Yeni şarkılarda Genius'tan alınan sözlerle anlık kelime bulutu
  if (currentAnalysis?.lyrics_wordcloud?.length) {
    if (heading) heading.textContent = 'Bu Şarkının Kelime Bulutu';
    renderWordCloudWords(currentAnalysis.lyrics_wordcloud);
    return;
  }

  if (heading) heading.textContent = 'Bu Hücrenin Kelime Bulutu';
  wc.innerHTML = '<span class="empty-state">Yükleniyor…</span>';
  try {
    const res = await API.wordcloud(x, y, 60);
    if (!res.words.length) {
      wc.innerHTML = '<span class="empty-state">Bu hücredeki şarkıların temizlenmiş sözleri henüz veri setinde değil.</span>';
      return;
    }
    renderWordCloudWords(res.words);
  } catch (e) {
    wc.innerHTML = `<span class="empty-state">Kelime bulutu yüklenemedi: ${escapeHtml(e.message)}</span>`;
  }
}

async function runJourney() {
  if (!currentAnalysis) return;
  const start = $('journeyStart');
  const sx = parseInt(start.dataset.x, 10);
  const sy = parseInt(start.dataset.y, 10);
  const [ex, ey] = $('journeyTarget').value.split(',').map(Number);
  const steps = parseInt($('journeySteps').value, 10) || 8;

  const list = $('journeyList');
  const narrative = $('journeyNarrative');
  list.innerHTML = '<li class="muted">Yolculuk hazırlanıyor…</li>';
  narrative.classList.add('hidden');

  try {
    const res = await API.journey(sx, sy, ex, ey, steps);
    narrative.textContent = res.narrative;
    narrative.classList.remove('hidden');

    list.innerHTML = '';
    res.stops.forEach(stop => {
      const li = document.createElement('li');
      li.innerHTML = `
        <span class="step-no">${stop.step}</span>
        <img src="${escapeHtml(stop.song.album_art_url || transparentPixel())}" alt="" loading="lazy" />
        <div>
          <div class="song-title">${escapeHtml(stop.song.title)}</div>
          <div class="song-artist">${escapeHtml(stop.song.artist)}</div>
        </div>
        ${stop.song.spotify_preview_url
          ? `<audio controls preload="none" src="${escapeHtml(stop.song.spotify_preview_url)}"></audio>`
          : `<span class="cell-coord">${stop.cell.text}</span>`}
      `;
      list.appendChild(li);
    });
  } catch (e) {
    list.innerHTML = `<li class="muted">Yolculuk oluşturulamadı: ${escapeHtml(e.message)}</li>`;
  }
}


// ── 8) Utils ──────────────────────────────────────────────────────────────
function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function transparentPixel() {
  return 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><rect width="1" height="1" fill="%23123"/></svg>'
  );
}


// ── 9) Events ─────────────────────────────────────────────────────────────
analysisForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearError();

  const payload = currentMode === 'spotify'
    ? { spotify_url: spotifyUrlInput.value.trim() }
    : { artist: artistInput.value.trim(), song: songInput.value.trim() };

  showLoadingState();
  try {
    const data = await API.analyze(payload);
    renderAnalysis(data);
  } catch (err) {
    hideLoading();
    emptyState.classList.remove('hidden');
    showError(err.message);
  }
});

tabButtons.forEach(btn => btn.addEventListener('click', () => setMode(btn.dataset.mode)));
[spotifyUrlInput, artistInput, songInput].forEach(input =>
  input.addEventListener('input', validateForm));

themeToggle.addEventListener('click', () => {
  const next = body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  setTheme(next);
});

$('journeyBtn').addEventListener('click', runJourney);


// ── 10) Boot ──────────────────────────────────────────────────────────────
initTheme();
setMode('spotify');
// İlk açılışta nötr radar — analiz yapılınca dolacak
renderRadar([50, 50, 50, 50, 50, 50]);
