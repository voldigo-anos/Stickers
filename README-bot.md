> Ce dossier contient le bot Telegram (Python). Il est indépendant du site web du projet.

# 🎉 Bot de création de stickers (français)

Bot Telegram qui crée des packs de stickers à partir de **photos, vidéos, GIF et stickers existants**, sans jamais demander à l'utilisateur de choisir entre *statique* et *vidéo* : le format est détecté automatiquement.

## ✨ Fonctionnalités

- ✏️ L'utilisateur choisit **le nom** et **le lien** du pack
- 🖼 Ajout de photos, 🎬 vidéos, 🎞 GIF et 🧩 stickers (statique / vidéo / animé)
- 📥 Envoi d'un sticker d'un pack existant → **import de tout le pack** dans le nouveau pack
- ♻️ **Anti-doublon** : un même sticker ne peut pas être ajouté deux fois dans un pack
- ⌨️ **Reply keyboard** (boutons sous le clavier) + boutons inline
- 🔗 Boutons `/start` : contacter le créateur, la chaîne, le groupe
- 🟢 Export **Telegram → WhatsApp** (`.wastickers`, découpage automatique en fichiers de 30)
- 🌈 Création de **thèmes Telegram Android** (`.attheme`) : couleurs des fonds, écritures, bulles et vocaux extraites de la photo, intégrée comme fond avec les marqueurs Telegram `WPS`/`WPE`. Le format `.attheme` ne s’applique pas sur iPhone ; un thème iOS ou cloud distinct serait nécessaire.
- ✅ Contrôle des fichiers WhatsApp avant envoi : WebP décodable 512×512, statique ≤100 Ko, animé ≤500 Ko, durée ≤10 s et images ≥8 ms ; icône PNG 96×96 ≤50 Ko, packs homogènes de 3–30 stickers. Un média isolé est répété trois fois pour rester importable.
- 🏆 **Classement** des créateurs (packs & stickers)
- 🛡 Commandes **admin** : `/admin`, `/stats`, `/broadcast`, `/ban`, `/unban`

## 🚀 Déploiement sur Render

1. Pousse ce dossier sur GitHub.
2. Sur Render : **New → Web Service → Docker** (ou « Blueprint » avec `render.yaml`).
   Utilise bien le Blueprint fourni : il crée une instance **Starter** et monte le disque permanent `stickers-data` sur `/var/data`.
3. Variables d'environnement :

| Variable | Description |
|---|---|
| `BOT_TOKEN` | token donné par [@BotFather](https://t.me/BotFather) |
| `ADMINS` | ID Telegram des admins, séparés par des virgules |
| `CREATOR_URL` | lien du créateur (bouton `/start`) |
| `CHANNEL_URL` | lien de la chaîne |
| `GROUP_URL` | lien du groupe |
| `DB_PATH` | chemin SQLite (ex. `/var/data/bot.db` avec un disque Render) |

Le service expose un petit serveur HTTP sur `$PORT` pour le health check de Render.

### 💾 Conservation des informations

La base est enregistrée dans `/var/data/bot.db`, sur le disque permanent Render. Les utilisateurs, packs, classements, bannissements, formats, écritures et couleurs restent donc présents après un redéploiement ou un redémarrage.

⚠️ Render ne propose pas de disque permanent sur son offre gratuite. Le fichier `render.yaml` utilise donc le plan `starter`. Ne supprime pas le disque `stickers-data` et ne change pas `DB_PATH`, sinon les anciennes informations ne seront plus accessibles.

## 🐳 Lancer en local

```bash
docker build -t stickers-bot .
docker run -e BOT_TOKEN=xxx -e ADMINS=123456789 -p 8080:8080 stickers-bot
```

Sans Docker (nécessite `ffmpeg`) :

```bash
pip install -r requirements.txt
BOT_TOKEN=xxx ADMINS=123456789 python main.py
```
