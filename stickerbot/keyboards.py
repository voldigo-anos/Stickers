from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

import config

BTN_NEW = '✏️ Nouveau pack'
BTN_MY_PACKS = '📦 Mes packs'
BTN_TOP = '🏆 Classement'
BTN_HELP = '❓ Aide'
BTN_DONE = '✅ Terminer'
BTN_CANCEL = '🚫 Annuler'
BTN_WA = '🟢 Vers WhatsApp'
BTN_ADMIN = '🛡 Admin'
BTN_STYLE = '🎨 Format & écriture'
BTN_NO_WM = '🚫 Sans écriture'
BTN_CONVERT = '🔄 Convertir en WhatsApp'
BTN_THEME = '🌈 Créer un thème'
BTN_AUTO = '🤖 Pack automatique'


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(BTN_NEW), KeyboardButton(BTN_MY_PACKS)],
        [KeyboardButton(BTN_CONVERT), KeyboardButton(BTN_THEME)],
        [KeyboardButton(BTN_AUTO)],
        [KeyboardButton(BTN_TOP), KeyboardButton(BTN_HELP)],
    ]
    if is_admin:
        rows.append([KeyboardButton(BTN_ADMIN)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, input_field_placeholder='Choisis une option 👇')


def pack_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_DONE), KeyboardButton(BTN_WA)],
            [KeyboardButton(BTN_STYLE)],
            [KeyboardButton(BTN_MY_PACKS), KeyboardButton(BTN_CANCEL)],
        ],
        resize_keyboard=True,
        input_field_placeholder='Envoie une photo, vidéo, GIF ou sticker 📨',
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_CANCEL)]],
        resize_keyboard=True,
        input_field_placeholder='En attente de ta réponse ✍️',
    )


def wm_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_NO_WM)], [KeyboardButton(BTN_CANCEL)]],
        resize_keyboard=True,
        input_field_placeholder='Écris le mot à afficher ✍️',
    )


def shape_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('⬛ Carré', callback_data='shape:square')],
            [InlineKeyboardButton('⚪ Rond', callback_data='shape:round')],
            [InlineKeyboardButton('🖼 Format original', callback_data='shape:original')],
        ]
    )


def remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def convert_choice(set_name=None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton('🧩 Ce sticker seulement', callback_data='wa_one')]]
    if set_name:
        # Store the name in user_data: Telegram limits callback_data to 64 bytes.
        rows.append([InlineKeyboardButton('📦 Tout le pack', callback_data='wa_pack')])
    rows.append([InlineKeyboardButton('🚫 Annuler', callback_data='wa_no')])
    return InlineKeyboardMarkup(rows)


def start_links() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('👤 Contacter le créateur', url=config.CREATOR_URL)],
            [
                InlineKeyboardButton('📢 La chaîne', url=config.CHANNEL_URL),
                InlineKeyboardButton('💬 Le groupe', url=config.GROUP_URL),
            ],
        ]
    )


def import_choice(set_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('✅ Importer tout le pack', callback_data=f'imp:{set_name}')],
            [InlineKeyboardButton('🧩 Ce sticker seulement', callback_data='imp_one')],
            [InlineKeyboardButton('🚫 Annuler', callback_data='imp_no')],
        ]
    )


def _cb_ok(data: str) -> bool:
    """Telegram refuse un callback_data de plus de 64 octets"""
    return len(data.encode('utf-8')) <= 64


def view_pack_only(pack_name: str) -> InlineKeyboardMarkup:
    """clavier minimal : uniquement le bouton « Voir le pack » (bouton lien, sans limite)"""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton('🔗 Voir le pack', url=f'https://t.me/addstickers/{pack_name}')]]
    )


def pack_actions(pack_name: str) -> InlineKeyboardMarkup:
    rows = []
    use_data, wa_data, del_data = f'use:{pack_name}', f'wa:{pack_name}', f'del:{pack_name}'
    if _cb_ok(use_data):
        rows.append([InlineKeyboardButton('📨 Continuer ce pack', callback_data=use_data)])
    second = []
    if _cb_ok(wa_data):
        second.append(InlineKeyboardButton('🟢 WhatsApp', callback_data=wa_data))
    if _cb_ok(del_data):
        second.append(InlineKeyboardButton('🗑 Oublier', callback_data=del_data))
    if second:
        rows.append(second)
    # le bouton « Voir le pack » est TOUJOURS present
    rows.append([InlineKeyboardButton('🔗 Voir le pack', url=f'https://t.me/addstickers/{pack_name}')])
    return InlineKeyboardMarkup(rows)


COLOR_CHOICES = {
    '⚪ Blanc': '#FFFFFF', '⚫ Noir': '#000000', '🔴 Rouge': '#FF0000',
    '🔵 Bleu': '#0088FF', '🟢 Vert': '#00CC66', '🟡 Jaune': '#FFFF00',
    '🩷 Rose': '#FF69B4', '🟣 Violet': '#9933FF', '🟠 Orange': '#FF8800',
    '◻️ Transparent': '#FFFFFF00',
}


def selected_color(value: str):
    """Recognize keyboard labels even when Telegram changes emoji selectors."""
    cleaned = (value or '').replace('\ufe0f', '').strip()
    for label, color in COLOR_CHOICES.items():
        if cleaned == label.replace('\ufe0f', ''):
            return color, label
    return value, value.upper()


def color_label(color: str) -> str:
    for label, value in COLOR_CHOICES.items():
        if value == color:
            return label
    return color


def color_menu() -> ReplyKeyboardMarkup:
    labels = list(COLOR_CHOICES)
    return ReplyKeyboardMarkup(
        [[KeyboardButton(label) for label in labels[i:i + 3]] for i in range(0, len(labels), 3)]
        + [[KeyboardButton(BTN_CANCEL)]], resize_keyboard=True,
        input_field_placeholder='Choisis une couleur ou envoie #RRGGBB 🎨',
    )


def auto_format_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('🖼 Stickers statiques', callback_data='auto:static')],
            [InlineKeyboardButton('🎞 Stickers GIF (animés)', callback_data='auto:gif')],
            [InlineKeyboardButton('🚫 Annuler', callback_data='auto:no')],
        ]
    )


def auto_count_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton('60'), KeyboardButton('80'), KeyboardButton('100'), KeyboardButton('120')],
         [KeyboardButton(BTN_CANCEL)]],
        resize_keyboard=True,
        input_field_placeholder='Un nombre entre 60 et 120 🔢',
    )
