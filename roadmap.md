# Écriture des stickers
- [ ] Corriger et tester la réception des médias pour la conversion WhatsApp.
- [ ] Valider les stickers et archives selon les limites WhatsApp avant envoi.
- [ ] Corriger le format du fond intégré et les couleurs des thèmes.
- [x] Ajouter une couleur par pack, avec choix prédéfinis, transparent et code personnalisé.
- [x] Confirmer immédiatement la couleur choisie.
- [x] Déplacer le texte en bas à gauche sur images et vidéos.
- [x] Remplacer le rendu à police unique par un rendu Unicode avec repli de polices.
- [ ] Tester dans Telegram après redéploiement Render les couleurs et les caractères décoratifs.

# Sauvegarde permanente
- [x] Monter la base SQLite sur un disque permanent Render.
- [x] Utiliser automatiquement `/var/data/bot.db` sur Render.
- [x] Sécuriser les écritures SQLite concurrentes.
- [ ] Vérifier les données existantes après le prochain redéploiement Render.

# Création de thèmes Telegram
- [x] Bouton « 🌈 Créer un thème » dans le menu principal.
- [x] Générer un .attheme (couleurs extraites de la photo + photo en fond d'écran).
- [x] Tester la génération localement (offset du fond d'écran, palette).
- [ ] Tester dans Telegram (Android + iPhone) après redéploiement Render.

# Thèmes : photo en fond des discussions
- [x] Photo du thème en fond de chaque discussion, bulles translucides et écritures assorties.
- [ ] Tester dans Telegram Android après redéploiement.

# Pack automatique Pinterest
- [x] Choix statique / GIF, thème de recherche, 60 à 120 stickers.
- [x] GIF trouvés via Pinterest (recherche « … gif »), photos animées en secours.
- [ ] Tester un pack complet dans Telegram après redéploiement.
