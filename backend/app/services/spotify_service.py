"""
Spotify Client Credentials wrapper'ı.

Bu akış playlist-modify gibi user-scope'lar için yetmez ama bizim ihtiyacımız
(track info, preview_url, albüm kapağı) için tam yeterli — ve oauth callback
sıkıntısı yok.

Search ve track lookup'ları LRU cache ile koruyoruz: aynı şarkı için
defalarca API çağırmıyoruz.
"""

import logging
import re
from functools import lru_cache

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from app.config import settings


logger = logging.getLogger("mmma.spotify")


# ── Spotipy istemcisi (lazy, ilk kullanımda kurulur) ────────────────────────
_client: spotipy.Spotify | None = None


def _get_client() -> spotipy.Spotify | None:
    """Spotify credentials yoksa None döner; servis nazikçe degrade olur."""
    global _client
    if _client is not None:
        return _client

    if not (settings.spotify_client_id and settings.spotify_client_secret):
        logger.warning(
            "SPOTIFY_CLIENT_ID/SECRET tanımsız. "
            "preview_url ve albüm kapağı eklenemeyecek."
        )
        return None

    auth = SpotifyClientCredentials(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
    )
    _client = spotipy.Spotify(auth_manager=auth, requests_timeout=10, retries=3)
    return _client


# ── URL/ID ayrıştırma ───────────────────────────────────────────────────────
_TRACK_ID_RE = re.compile(r"track[/:]([a-zA-Z0-9]{22})")


def extract_track_id(url_or_id: str) -> str | None:
    """Spotify track URL veya saf id'yi 22 karakterlik id'ye çevirir."""
    if not url_or_id:
        return None
    s = url_or_id.strip()

    # Zaten 22 karakter alfanümerikse (genelde id'dir)
    if re.fullmatch(r"[a-zA-Z0-9]{22}", s):
        return s

    m = _TRACK_ID_RE.search(s)
    return m.group(1) if m else None


# ── Track lookup (LRU cache) ────────────────────────────────────────────────
@lru_cache(maxsize=settings.spotify_cache_size)
def get_track_meta(track_id: str) -> dict | None:
    """
    Track id'den minimum metadata döner:
      {title, artist, preview_url, album_art_url, external_url}
    Hata varsa None döner — frontend bunu nazikçe işler.
    """
    client = _get_client()
    if client is None or not track_id:
        return None

    try:
        t = client.track(track_id)
    except Exception as e:
        logger.error("Spotify track(%s) hatası: %s", track_id, e)
        return None

    images = (t.get("album") or {}).get("images") or []
    album_art = images[0]["url"] if images else None
    artists = t.get("artists") or []
    artist_name = artists[0]["name"] if artists else ""

    return {
        "song_id": t.get("id") or track_id,
        "title": t.get("name") or "",
        "artist": artist_name,
        "preview_url": t.get("preview_url"),
        "album_art_url": album_art,
        "external_url": (t.get("external_urls") or {}).get("spotify"),
    }


# ── Search: (artist, title) → track id ──────────────────────────────────────
@lru_cache(maxsize=settings.spotify_cache_size)
def search_track(artist: str, title: str) -> dict | None:
    """
    Yerel veritabanında olmayan şarkıları Spotify'da arar.
    Yine cache'li; aynı arama tekrar API'ye gitmez.
    """
    client = _get_client()
    if client is None:
        return None

    query = f'track:"{title}" artist:"{artist}"'
    try:
        res = client.search(q=query, type="track", limit=1, market="TR")
    except Exception as e:
        logger.error("Spotify search('%s') hatası: %s", query, e)
        return None

    items = (res.get("tracks") or {}).get("items") or []
    if not items:
        return None

    t = items[0]
    images = (t.get("album") or {}).get("images") or []
    artists = t.get("artists") or []
    return {
        "song_id": t.get("id"),
        "title": t.get("name") or title,
        "artist": (artists[0]["name"] if artists else artist),
        "preview_url": t.get("preview_url"),
        "album_art_url": images[0]["url"] if images else None,
        "external_url": (t.get("external_urls") or {}).get("spotify"),
    }


# ── Veritabanı satırı (title, artist) → zenginleştirme ──────────────────────
def enrich_song_row(row) -> dict:
    """
    DataFrame'den gelen bir şarkıya Spotify metadata'sını ekler.
    row: {song_id, title, artist}
    """
    song_id = str(row.get("song_id") or "")
    title = str(row.get("title") or "")
    artist = str(row.get("artist") or "")

    base = {
        "song_id": song_id, "title": title, "artist": artist,
        "spotify_preview_url": None,
        "album_art_url": None,
        "spotify_url": None,
    }

    # song_id 22 karakterli ise muhtemelen Spotify track id'sidir; direkt aç.
    if re.fullmatch(r"[a-zA-Z0-9]{22}", song_id):
        meta = get_track_meta(song_id)
    else:
        meta = search_track(artist, title)

    if meta:
        base["spotify_preview_url"] = meta.get("preview_url")
        base["album_art_url"] = meta.get("album_art_url")
        base["spotify_url"] = meta.get("external_url")

    return base
