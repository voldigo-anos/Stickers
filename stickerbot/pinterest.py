"""Recherche automatique d'images et de GIF via l'API Pinterest du créateur.

API : https://image-explorer-max.vercel.app/api/pin?query=...&num=...
Les GIF sont obtenus en ajoutant « gif » à la recherche puis en ne gardant
que les liens .gif : aucune API GIF séparée n'est nécessaire.
"""

import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

API_URL = os.environ.get('PINTEREST_API_URL', 'https://image-explorer-max.vercel.app').rstrip('/')
MAX_RESULTS = 200
MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
TIMEOUT = 30
UA = {'User-Agent': 'Mozilla/5.0 StickerBot'}

MIN_AUTO = 60
MAX_AUTO = 120

MODE_STATIC = 'static'
MODE_GIF = 'gif'

STATIC_EXT = ('.jpg', '.jpeg', '.png', '.webp')
GIF_EXT = ('.gif',)


def parse_count(text: str):
    """nombre de stickers choisi par l'utilisateur (60 à 120), sinon None"""
    text = (text or '').strip()
    if not text.isdigit():
        return None
    value = int(text)
    return value if MIN_AUTO <= value <= MAX_AUTO else None


def search(query: str, num: int = MAX_RESULTS) -> list:
    url = f'{API_URL}/api/pin?' + urllib.parse.urlencode({'query': query, 'num': min(num, MAX_RESULTS)})
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    if not data.get('status'):
        return []
    return [u for u in data.get('results') or [] if isinstance(u, str) and u.startswith('http')]


def _ext(url: str) -> str:
    return os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()


def _queries(query: str, mode: str) -> list:
    if mode == MODE_GIF:
        return [f'{query} gif', f'{query} animated gif', f'{query} gif anime', f'{query} aesthetic gif']
    return [query, f'{query} aesthetic', f'{query} icon', f'{query} pfp', f'{query} wallpaper']


def collect(query: str, mode: str, want: int) -> tuple:
    """renvoie (urls_principales, urls_photos_de_secours) sans doublons.

    En mode GIF, si Pinterest ne fournit pas assez de vrais GIF, les photos
    de secours sont animées par le bot pour atteindre le nombre demandé.
    """
    exts = GIF_EXT if mode == MODE_GIF else STATIC_EXT
    main, backup, seen = [], [], set()
    target = want * 2  # marge : certains fichiers échouent à la conversion
    for q in _queries(query, mode):
        try:
            results = search(q)
        except Exception:  # noqa: BLE001 - on tente la recherche suivante
            logger.exception('recherche pinterest échouée: %s', q)
            continue
        for url in results:
            if url in seen:
                continue
            seen.add(url)
            ext = _ext(url)
            if ext in exts:
                main.append(url)
            elif mode == MODE_GIF and ext in STATIC_EXT:
                backup.append(url)
        if len(main) >= target:
            break
    if mode == MODE_GIF and len(main) < target:
        for q in _queries(query, MODE_STATIC)[:2]:
            try:
                for url in search(q):
                    if url not in seen and _ext(url) in STATIC_EXT:
                        seen.add(url)
                        backup.append(url)
            except Exception:  # noqa: BLE001
                logger.exception('recherche pinterest échouée: %s', q)
    return main, backup


def fetch(url: str) -> bytes:
    """télécharge l'image ; si pinimg refuse, passe par /api/pin/download"""
    try:
        return _fetch(url)
    except Exception:  # noqa: BLE001
        proxy = f'{API_URL}/api/pin/download?' + urllib.parse.urlencode({'url': url})
        return _fetch(proxy)


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={**UA, 'Referer': 'https://www.pinterest.com/'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        length = resp.headers.get('Content-Length')
        if length and int(length) > MAX_DOWNLOAD_BYTES:
            raise ValueError('fichier trop lourd')
        data = resp.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError('fichier trop lourd')
    return data
