import os


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
CHANNEL_URL = os.environ.get('CHANNEL_URL', '').strip() or 'https://t.me/telegram'
GROUP_URL = os.environ.get('GROUP_URL', '').strip() or 'https://t.me/telegram'

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
