import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# le code du bot vit dans le dossier stickerbot/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stickerbot'))

import config


logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO,
)
logging.getLogger('httpx').setLevel(logging.WARNING)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write('🎉 Bot stickers en ligne'.encode('utf-8'))

    def log_message(self, *args):
        pass


def run_health_check_server():
    server = HTTPServer(('0.0.0.0', config.PORT), HealthCheckHandler)
    server.serve_forever()


if __name__ == '__main__':
    if not config.BOT_TOKEN:
        raise SystemExit('BOT_TOKEN manquant : ajoute-le dans les variables d\'environnement.')

    # serveur HTTP en arriere-plan pour le health check de Render
    threading.Thread(target=run_health_check_server, daemon=True).start()

    import bot

    application = bot.build_application()
    application.run_polling(drop_pending_updates=True)
