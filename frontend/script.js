const body = document.body;
const themeToggle = document.getElementById('themeToggle');
const tabButtons = document.querySelectorAll('.tab-btn');
const spotifyPanel = document.getElementById('spotifyPanel');
const manualPanel = document.getElementById('manualPanel');
const spotifyUrl = document.getElementById('spotifyUrl');
const artistName = document.getElementById('artistName');
const songName = document.getElementById('songName');
const analyzeBtn = document.getElementById('analyzeBtn');
const analysisForm = document.getElementById('analysisForm');
const emptyState = document.getElementById('emptyState');
const loadingState = document.getElementById('loadingState');
const resultsSection = document.getElementById('resultsSection');
const progressFill = document.getElementById('progressFill');
const loadingSteps = [...document.querySelectorAll('#loadingSteps li')];

let currentMode = 'spotify';
let loadingTimer = null;
let loadingIndex = 0;

const sampleData = {
  spotify: {
    title: 'Yalnızlık Paylaşılmaz',
    artist: 'Teoman',
    source: 'Spotify',
    language: 'Türkçe',
    mood: 'Enerjik ve Mutlu',
    confidence: 87,
    intensity: 78,
    footnote: 'Yüksek korelasyon tespit edildi',
    coords: { x: 74, y: 46, text: '(3.2, 1.8)' },
    audioFeatures: [72, 55, 81, 28, 63, 47],
    moodDistribution: [36, 45, 8, 7, 5],
    lyricsScores: [68, 74, 61]
  },
  manual: {
    title: 'Zalim',
    artist: 'Sezen Aksu',
    source: 'Manuel Giriş',
    language: 'Türkçe',
    mood: 'Duygusal ve Melankolik',
    confidence: 83,
    intensity: 71,
    footnote: 'Dilsel ağırlık daha baskın bulundu',
    coords: { x: 77, y: 73, text: '(3.6, 3.1)' },
    audioFeatures: [48, 41, 52, 66, 37, 44],
    moodDistribution: [12, 18, 20, 42, 8],
    lyricsScores: [54, 79, 72]
  }
};

const moodChartLabels = ['Mutlu', 'Enerjik', 'Sakin', 'Melankolik', 'Nötr'];
const moodChartColors = ['#fbbf24', '#19c38a', '#18c7ff', '#a855f7', '#7a8699'];
const radarLabels = ['Enerji', 'Valans', 'Dansedilebilirlik', 'Akustiklik', 'Tempo', 'Ses Yüksekliği'];
const lyricsLabels = ['Şarkı Sözü Pozitifliği', 'Duygusal Derinlik', 'Anlatım Tonu'];

function setTheme(nextTheme) {
  body.setAttribute('data-theme', nextTheme);
  localStorage.setItem('mmm-theme', nextTheme);
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
  const validSpotify = spotifyUrl.value.trim().length > 0;
  const validManual = artistName.value.trim().length > 0 && songName.value.trim().length > 0;
  analyzeBtn.disabled = currentMode === 'spotify' ? !validSpotify : !validManual;
}

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
  updateLoadingStep(0);
}

function showLoadingState() {
  emptyState.classList.add('hidden');
  resultsSection.classList.add('hidden');
  loadingState.classList.remove('hidden');
  resetLoading();

  loadingTimer = setInterval(() => {
    loadingIndex += 1;

    if (loadingIndex < loadingSteps.length) {
      updateLoadingStep(loadingIndex);
    } else {
      clearInterval(loadingTimer);
      progressFill.style.width = '96%';
    }
  }, 800);
}

function showResults(data) {
  if (loadingTimer) clearInterval(loadingTimer);
  loadingState.classList.add('hidden');
  resultsSection.classList.remove('hidden');

  document.getElementById('moodTitle').textContent = data.mood;
  document.getElementById('confidenceValue').textContent = `${data.confidence}%`;
  document.getElementById('intensityValue').textContent = `${data.intensity}%`;
  document.getElementById('confidenceBar').style.width = `${data.confidence}%`;
  document.getElementById('intensityBar').style.width = `${data.intensity}%`;
  document.getElementById('footnote').textContent = data.footnote;

  document.getElementById('songTitle').textContent = data.title;
  document.getElementById('artistTitle').textContent = data.artist;
  document.getElementById('sourceValue').textContent = data.source;
  document.getElementById('languageValue').textContent = data.language;

  const coordChip = document.getElementById('coordChip');
  coordChip.textContent = `Konum: ${data.coords.text}`;

  const marker = document.getElementById('songMarker');
  marker.style.setProperty('--marker-x', `${data.coords.x}%`);
  marker.style.setProperty('--marker-y', `${data.coords.y}%`);

  renderRadarChart(data.audioFeatures);
  renderMoodDistribution(data.moodDistribution);
  renderLyricsChart(data.lyricsScores);

  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderRadarChart(values) {
  const svg = document.getElementById('radarChart');
  const width = 420;
  const height = 320;
  const cx = 210;
  const cy = 165;
  const maxRadius = 110;
  const levels = 4;
  svg.innerHTML = '';

  for (let level = 1; level <= levels; level++) {
    const radius = (maxRadius / levels) * level;
    const points = radarLabels.map((_, i) => {
      const angle = (-Math.PI / 2) + (i * Math.PI * 2 / radarLabels.length);
      return `${cx + Math.cos(angle) * radius},${cy + Math.sin(angle) * radius}`;
    }).join(' ');

    const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    polygon.setAttribute('points', points);
    polygon.setAttribute('fill', 'none');
    polygon.setAttribute('stroke', 'rgba(127, 148, 180, 0.28)');
    polygon.setAttribute('stroke-width', '1');
    svg.appendChild(polygon);
  }

  radarLabels.forEach((label, i) => {
    const angle = (-Math.PI / 2) + (i * Math.PI * 2 / radarLabels.length);
    const x = cx + Math.cos(angle) * maxRadius;
    const y = cy + Math.sin(angle) * maxRadius;

    const axis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    axis.setAttribute('x1', cx);
    axis.setAttribute('y1', cy);
    axis.setAttribute('x2', x);
    axis.setAttribute('y2', y);
    axis.setAttribute('stroke', 'rgba(127, 148, 180, 0.28)');
    axis.setAttribute('stroke-width', '1');
    svg.appendChild(axis);

    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', cx + Math.cos(angle) * (maxRadius + 24));
    text.setAttribute('y', cy + Math.sin(angle) * (maxRadius + 24));
    text.setAttribute('fill', 'var(--text-soft)');
    text.setAttribute('font-size', '13');
    text.setAttribute('text-anchor', 'middle');
    text.textContent = label;
    svg.appendChild(text);
  });

  [25, 50, 75, 100].forEach((tick, idx) => {
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    t.setAttribute('x', cx + 6);
    t.setAttribute('y', cy - (maxRadius / levels) * (idx + 1) + 4);
    t.setAttribute('fill', 'var(--text-soft)');
    t.setAttribute('font-size', '11');
    t.textContent = tick;
    svg.appendChild(t);
  });

  const dataPoints = values.map((value, i) => {
    const angle = (-Math.PI / 2) + (i * Math.PI * 2 / radarLabels.length);
    const radius = (value / 100) * maxRadius;
    return `${cx + Math.cos(angle) * radius},${cy + Math.sin(angle) * radius}`;
  }).join(' ');

  const fillPoly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
  fillPoly.setAttribute('points', dataPoints);
  fillPoly.setAttribute('fill', 'rgba(0, 228, 168, 0.26)');
  fillPoly.setAttribute('stroke', '#00e4a8');
  fillPoly.setAttribute('stroke-width', '2');
  svg.appendChild(fillPoly);
}

function renderMoodDistribution(values) {
  const container = document.getElementById('moodBars');
  container.innerHTML = '';

  values.forEach((value, index) => {
    const row = document.createElement('div');
    row.className = 'mood-row';
    row.innerHTML = `
      <span class="label">${moodChartLabels[index]}</span>
      <div class="mood-track">
        <span class="mood-fill" style="width:${value}%; background:${moodChartColors[index]}"></span>
      </div>
      <span class="mood-value">${value}</span>
    `;
    container.appendChild(row);
  });
}

function renderLyricsChart(values) {
  const container = document.getElementById('lyricsBars');
  container.innerHTML = '';

  values.forEach((value, index) => {
    const item = document.createElement('div');
    item.className = 'vertical-item';
    item.innerHTML = `
      <div class="vertical-score">${value}</div>
      <div class="vertical-bar-wrap">
        <div class="vertical-bar" style="height:${value}%"></div>
      </div>
      <div class="vertical-label">${lyricsLabels[index]}</div>
    `;
    container.appendChild(item);
  });
}

analysisForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const data = currentMode === 'spotify' ? sampleData.spotify : sampleData.manual;
  showLoadingState();
  setTimeout(() => showResults(data), 3200);
});

tabButtons.forEach(button => {
  button.addEventListener('click', () => setMode(button.dataset.mode));
});

[spotifyUrl, artistName, songName].forEach(input => {
  input.addEventListener('input', validateForm);
});

themeToggle.addEventListener('click', () => {
  const next = body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  setTheme(next);
});

initTheme();
setMode('spotify');
renderRadarChart(sampleData.spotify.audioFeatures);
renderMoodDistribution(sampleData.spotify.moodDistribution);
renderLyricsChart(sampleData.spotify.lyricsScores);
