"""Tous les textes du bot, en francais, avec emojis et mise en forme HTML."""

START = (
    "🎉 <b>Bienvenue {name} !</b> 🎀\n\n"
    "Je suis ton assistant <b>stickers</b> 📦\n"
    "Avec moi tu peux :\n\n"
    "✏️ <b>Créer</b> un pack (tu choisis le nom <i>et</i> le lien)\n"
    "🖼 Ajouter des <b>photos</b>, <b>vidéos</b>, <b>GIF</b> ou <b>stickers</b>\n"
    "📥 <b>Importer</b> un pack entier d'un seul coup\n"
    "🟢 <b>Exporter</b> tes stickers vers <b>WhatsApp</b>\n"
    "🏆 Grimper dans le <b>classement</b>\n\n"
    "👇 Utilise les boutons ci-dessous pour commencer."
)

HELP = (
    "❓ <b>Aide</b>\n\n"
    "1️⃣ Appuie sur <b>➕ Nouveau pack</b>\n"
    "2️⃣ Envoie le <b>nom</b> du pack (le titre affiché)\n"
    "3️⃣ Envoie le <b>lien</b> du pack (ex : <code>mon_pack</code>)\n"
    "4️⃣ Envoie tout ce que tu veux : 🖼 photo, 🎬 vidéo, 🎞 GIF, 🧩 sticker\n\n"
    "🤖 Pas besoin de choisir <i>statique</i> ou <i>vidéo</i> : je détecte tout seul.\n"
    "🚫 Un même sticker ne peut pas être ajouté deux fois dans un pack.\n"
    "📦 Envoie un sticker d'un pack existant → je peux importer <b>tout le pack</b>.\n\n"
    "<b>Commandes</b>\n"
    "/start — menu principal\n"
    "/new — créer un pack\n"
    "/mypacks — mes packs\n"
    "/top — classement\n"
    "🤖 <b>Pack automatique</b> : choisis statique ou GIF, un thème et 60 à 120 stickers, "
    "je trouve les images sur Pinterest et je crée le pack.\n"
    "/cancel — annuler l'opération en cours\n\n"
    "🎨 <b>Format</b> : à la création tu choisis <b>carré</b>, <b>rond</b> ou <b>original</b>.\n"
    "✍️ <b>Écriture</b> : le mot choisi est écrit en bas à gauche de <b>chaque</b> sticker du pack "
    "(statique ou vidéo), avec la couleur de ton choix. Modifiable via <b>🎨 Format &amp; écriture</b>.\n"
    "⚡ Plusieurs personnes peuvent utiliser le bot en même temps, même pendant une conversion."
)

ASK_TITLE = (
    "✏️ <b>Nom du pack</b>\n\n"
    "Envoie-moi le titre que tu veux afficher (max 64 caractères).\n"
    "Exemple : <code>Dazai Osamu</code>"
)

ASK_LINK = (
    "🔗 <b>Lien du pack</b>\n\n"
    "Envoie maintenant le lien souhaité (lettres, chiffres et <code>_</code> uniquement).\n"
    "Exemple : <code>dazai_osamu</code>\n\n"
    "Le lien final sera : <code>t.me/addstickers/ton_lien_by_{bot}</code>"
)

BAD_LINK = (
    "⚠️ Lien invalide.\n"
    "Il doit commencer par une lettre et ne contenir que des lettres, chiffres et <code>_</code> (max 40)."
)

LINK_TAKEN = "🚫 Ce lien est déjà utilisé. Choisis-en un autre 🔁"

ASK_SHAPE = (
    "🎨 <b>Format des stickers</b>\n\n"
    "Choisis la forme que doivent avoir <b>tous</b> les stickers de ce pack :\n\n"
    "⬛ <b>Carré</b> — image entière dans un carré 512×512\n"
    "⚪ <b>Rond</b> — découpe circulaire\n"
    "🖼 <b>Original</b> — je garde les proportions"
)

SHAPE_LABELS = {
    'original': '🖼 Original',
    'square': '⬛ Carré',
    'round': '⚪ Rond',
    'cover': '⬛ Carré',
}

SHAPE_CHOSEN = "✅ Format retenu : <b>{shape}</b>"

ASK_WM = (
    "✍️ <b>Écriture sur les stickers</b>\n\n"
    "Envoie le mot à écrire <b>en bas à gauche</b> de chaque sticker du pack, "
    "Tu choisiras ensuite sa couleur. De façon <b>discrète</b> (semi-transparente) "
    "(exemple : <code>Christus</code>).\n"
    "Ça marche pour les stickers <b>statiques</b> 🖼 <i>et</i> <b>vidéo</b> 🎬.\n\n"
    "Si tu n'en veux pas, appuie sur <b>🚫 Sans écriture</b>."
)

PACK_READY = (
    "✅ <b>Pack prêt !</b>\n\n"
    "📦 <b>{title}</b>\n"
    "🔗 <code>{link}</code>\n"
    "🎨 Format : <b>{shape}</b>\n"
    "✍️ Écriture : <b>{wm}</b>\n\n"
    "📨 Envoie-moi maintenant tes <b>photos</b> 🖼, <b>vidéos</b> 🎬, <b>GIF</b> 🎞 ou <b>stickers</b> 🧩.\n"
    "Quand tu as fini, appuie sur <b>✅ Terminer</b>."
)


ADDED = "✅ Ajouté ! 🔢 <b>{count}</b> sticker(s) dans <b>{title}</b>\n🔗 {link}"
DUPLICATE = "♻️ Ce sticker est <b>déjà</b> dans le pack — je ne l'ajoute pas deux fois."
PACK_FULL = "⚠️ Pack plein ({max} stickers max). Crée un nouveau pack ✏️"
NO_ACTIVE_PACK = (
    "📦 Aucun pack en cours.\n"
    "Appuie sur <b>➕ Nouveau pack</b> ou <b>📦 Mes packs</b> pour en sélectionner un."
)
FINISHED = "🎉 <b>Terminé !</b> Ton pack est prêt 👇"
PACK_CARD = "📦 <b>{title}</b>\n🔢 {count} sticker(s)"
WORKING = "⏳ Traitement en cours... le bot reste disponible pour tout le monde 🙂"
IMPORT_ASK = (
    "📦 <b>{title}</b>\n"
    "🔢 <b>{count}</b> stickers dans ce pack\n\n"
    "Que veux-tu faire ?"
)
IMPORT_DONE = (
    "✅ <b>Importation terminée</b>\n\n"
    "➕ Ajoutés : <b>{added}</b>\n"
    "♻️ Doublons ignorés : <b>{dupes}</b>\n"
    "⚠️ Échecs : <b>{failed}</b>\n\n"
    "🔗 {link}"
)
CANCELLED = "🚫 Opération annulée."
ERROR = "⚠️ Une erreur est survenue : <code>{error}</code>"
UNSUPPORTED = "🤔 Je ne sais pas quoi faire avec ça. Envoie une photo, une vidéo, un GIF ou un sticker."
BANNED = "🚫 Tu es banni de ce bot."

WA_START = (
    "⏳ <b>Conversion vers WhatsApp lancée</b>\n"
    "Je t'envoie les fichiers dès qu'ils sont prêts — pendant ce temps le bot "
    "continue de fonctionner normalement pour toi et pour les autres 🙂"
)
WA_SPLIT = "⚠️ Pack trop grand — divisé en <b>{files} fichiers</b> max {per} stickers."
WA_DONE = (
    "🟢 <b>Fichiers vérifiés pour WhatsApp !</b>\n"
    "Ouvre les fichiers avec <i>Sticker Maker</i> à jour. Les packs animés et statiques sont séparés.\n"
    "Un média seul est répété pour atteindre le minimum de 3 stickers exigé par WhatsApp."
)

LEADERBOARD_HEADER = "🏆 <b>Classement des créateurs</b> 🎉\n"
LEADERBOARD_ROW = "{medal} <b>{name}</b>\n     📦 {packs} packs • 🔢 {stickers} stickers"
LEADERBOARD_ME = "\n\n👤 Toi : <b>#{rank}</b> — 🔢 {stickers} stickers"
LEADERBOARD_EMPTY = "🏆 Le classement est vide pour l'instant. Sois le premier ! ✏️"

ADMIN_PANEL = (
    "🛡 <b>Panneau administrateur</b>\n\n"
    "👥 Utilisateurs : <b>{users}</b> (🚫 {banned} bannis)\n"
    "📦 Packs : <b>{packs}</b>\n"
    "🔢 Stickers : <b>{stickers}</b>\n\n"
    "<b>Commandes admin</b>\n"
    "/stats — statistiques\n"
    "/broadcast &lt;message&gt; — message à tous\n"
    "/ban &lt;id&gt; — bannir\n"
    "/unban &lt;id&gt; — débannir\n"
    "/top 20 — classement étendu"
)
NOT_ADMIN = "🚫 Réservé à l'administrateur du bot."
BROADCAST_DONE = "📣 Diffusion terminée : ✅ {ok} • ⚠️ {failed}"

CONVERT_ASK = (
    "🔄 <b>Conversion vers WhatsApp</b>\n\n"
    "Envoie-moi <b>n'importe quel sticker</b> 🧩 (ou photo 🖼, vidéo 🎬, GIF 🎞).\n"
    "Pas besoin de créer un pack : je le convertis directement ✨"
)
CONVERT_CHOICE = (
    "🟢 <b>Convertir vers WhatsApp</b>\n\n"
    "📦 Ce sticker vient du pack <b>{title}</b> ({count} stickers).\n"
    "Que veux-tu convertir ?"
)
CONVERT_ONE_ASK = "🟢 <b>Convertir vers WhatsApp</b>\n\nJe convertis ce média en sticker WhatsApp ?"

ASK_COLOR = "🎨 <b>Couleur de l’écriture</b>\nChoisis une couleur ou envoie ton code personnalisé, par exemple <code>#FF8800</code>."
BAD_COLOR = "⚠️ Choisis une couleur ci-dessous ou un code de 6 chiffres/lettres comme <code>#FF0000</code>."
COLOR_CHOSEN = "✅ Couleur choisie : <b>{color}</b>"

THEME_ASK = (
    "🌈 <b>Création de thème Telegram</b>\n\n"
    "Envoie-moi la <b>photo</b> qui servira de base à ton thème 🖼\n"
    "J'en extrais les couleurs pour te créer un thème complet : fonds, écritures, "
    "bulles, vocaux, boutons... tout sera assorti à ta photo ✨\n\n"
    "🤖 Le fichier <b>.attheme</b> est destiné à <b>Telegram Android</b>.\n"
    "🍏 iPhone utilise un autre format : ce fichier ne s’y applique pas."
)
THEME_WORKING = "⏳ Je crée ton thème à partir de la photo..."
THEME_DONE = (
    "🌈 <b>Voici ton thème !</b>\n\n"
    "Ouvre le fichier <b>.attheme</b> avec Telegram pour l'appliquer :\n"
    "🤖 <b>Android</b> : touche le fichier → <i>Appliquer</i>\n"
    "🍏 <b>iPhone</b> : ce format n’est pas compatible.\n\n"
    "🖼 Ta photo est le <b>fond de chaque discussion</b>, et les bulles et écritures "
    "prennent ses couleurs."
)
THEME_BAD_MEDIA = "⚠️ Pour créer un thème, envoie une <b>photo</b> 🖼 (pas une vidéo ni un sticker)."


AUTO_ASK_FORMAT = (
    "🤖 <b>Pack automatique</b>\n\n"
    "Je cherche les images sur <b>Pinterest</b> et je crée le pack tout seul ✨\n\n"
    "Choisis le type de stickers :"
)
AUTO_ASK_QUERY = (
    "🔎 <b>Recherche</b> — format : <b>{fmt}</b>\n\n"
    "Envoie le thème des stickers.\nExemple : <code>gojo satoru</code>, <code>cute cat</code>"
)
AUTO_ASK_COUNT = (
    "🔢 <b>Combien de stickers ?</b>\n\n"
    "Choisis ou envoie un nombre entre <b>60</b> et <b>120</b>."
)
AUTO_BAD_COUNT = "⚠️ Envoie un nombre entre <b>60</b> et <b>120</b>."
AUTO_FORMATS = {'static': 'statique 🖼', 'gif': 'GIF 🎞'}
AUTO_SEARCHING = "🔎 Je cherche « <b>{query}</b> » sur Pinterest..."
AUTO_NOTHING = "😕 Aucun résultat Pinterest pour « <b>{query}</b> ». Essaie un autre thème."
AUTO_PROGRESS = "⚙️ Création en cours : <b>{done}/{want}</b> stickers ({fmt})"
AUTO_DONE = (
    "🎉 <b>Pack automatique terminé !</b>\n\n"
    "📦 <b>{title}</b> — {done} sticker(s)\n"
    "👇 Appuie sur <b>Voir le pack</b> pour l'ajouter à Telegram."
)
AUTO_PARTIAL = "\n\n⚠️ Pinterest n'a fourni que {done} images utilisables sur {want} demandées."
AUTO_BUSY = "⏳ Un pack automatique est déjà en cours pour toi, attends qu'il se termine."
