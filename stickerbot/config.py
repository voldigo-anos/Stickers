import os
import re


def _int_list(value: str):
    out = []
    for part in (value or '').replace(';', ',').split(','):
        part = part.strip()
        if part.lstrip('-').isdigit():
            out.append(int(part))
    return out


def _int_env(name: str, default: int) -> int:
    """Lit une variable d'environnement entière.
    Si elle est absente, vide ou invalide, retourne la valeur par défaut."""
    raw = os.environ.get(name, '')
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


BOT_TOKEN = os.environ.get('BOT_TOKEN', '').strip()
ADMINS = _int_list(os.environ.get('ADMINS', ''))

CREATOR_URL = os.environ.get('CREATOR_URL', '').strip() or 'https://t.me/telegram'
CHANNEL_URL = os.environ.get('CHANNEL_URL', '').strip() or 'https://t.me/Stickers_light'
GROUP_URL = os.environ.get('GROUP_URL', '').strip() or 'https://t.me/telegram'

def _channel_chat_id():
    """chaine ou le bot publie les packs (reserve aux admins).

    - CHANNEL_CHAT_ID (ex. @Stickers_light ou -1001234567890) s'il est renseigne ;
    - sinon deduit de CHANNEL_URL quand c'est un lien public (https://t.me/NomDeLaChaine).
    """
    raw = os.environ.get('CHANNEL_CHAT_ID', '').strip()
    if raw:
        if raw.lstrip('-').isdigit():
            return int(raw)
        return raw if raw.startswith('@') else '@' + raw.rsplit('/', 1)[-1]
    match = re.match(r'^https?://t\.me/([A-Za-z][A-Za-z0-9_]{3,})/?$', CHANNEL_URL)
    return '@' + match.group(1) if match else None


CHANNEL_CHAT_ID = _channel_chat_id()

DEFAULT_DB_PATH = '/var/data/bot.db' if os.environ.get('RENDER') else os.path.join(os.path.dirname(__file__), 'bot.db')
DB_PATH = os.environ.get('DB_PATH', '').strip() or DEFAULT_DB_PATH
PORT = _int_env('PORT', 8080)

# limites
MAX_STICKERS_PER_PACK = 120
WA_STICKERS_PER_FILE = 30

# performance / multi-utilisateurs
CONCURRENT_UPDATES = _int_env('CONCURRENT_UPDATES', 256)
CONNECTION_POOL_SIZE = _int_env('CONNECTION_POOL_SIZE', 64)
MAX_PARALLEL_CONVERSIONS = _int_env('MAX_PARALLEL_CONVERSIONS', 3)
