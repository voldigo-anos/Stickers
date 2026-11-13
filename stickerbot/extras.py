"""Nouvelles fonctionnalités : texte sur sticker, enlever le fond, sticker IA, gestion des packs."""

import asyncio
import io
import logging
import os
import urllib.parse

import httpx
from PIL import Image, ImageDraw, ImageFont
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputSticker, Update
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, CallbackQueryHandler, ContextTypes, MessageHandler, filters

import db
import keyboards as kb

logger = logging.getLogger(__name__)

SIZE = 512
FONT_PATHS = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
]
AI_URL = 'https://image.pollinations.ai/prompt/{q}'
_rembg_session = None


# ---------------------------------------------------------------- images

def _font(size):
    for path in FONT_PATHS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_sticker(im: Image.Image) -> Image.Image:
    """redimensionne pour que le plus grand côté fasse 512 px (règle Telegram)."""
    im = im.convert('RGBA')
    im.thumbnail((SIZE, SIZE), Image.LANCZOS)
    if max(im.size) < SIZE:
        r = SIZE / max(im.size)
        im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
    return im


def to_webp(im: Image.Image) -> bytes:
    out = io.BytesIO()
    fit_sticker(im).save(out, 'WEBP', quality=90)
    return out.getvalue()


def caption_image(data: bytes, text: str) -> bytes:
    """écrit le texte en gros, en bas, blanc avec contour noir."""
    im = fit_sticker(Image.open(io.BytesIO(data)))
    draw = ImageDraw.Draw(im)
    text = text.strip()[:80]
    max_w = im.width - 24
    size = max(18, im.width // 7)
    while True:
        font = _font(size)
        words, lines, cur = text.split(), [], ''
        for w in words:
            test = (cur + ' ' + w).strip()
            if draw.textlength(test, font=font) <= max_w or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        too_wide = any(draw.textlength(l, font=font) > max_w for l in lines)
        if (len(lines) <= 3 and not too_wide) or size <= 18:
            break
        size -= 4
    stroke = max(2, size // 12)
    line_h = size + stroke * 2
    y = im.height - line_h * len(lines) - 12
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((im.width - w) / 2, y), line, font=font, fill='white', stroke_width=stroke, stroke_fill='black')
        y += line_h
    return to_webp(im)


def remove_background(data: bytes) -> bytes:
    global _rembg_session
    from rembg import new_session, remove
    if _rembg_session is None:
        _rembg_session = new_session(os.getenv('REMBG_MODEL', 'u2netp'))
    out = remove(Image.open(io.BytesIO(data)).convert('RGB'), session=_rembg_session)
    bbox = out.getbbox()
    if bbox:
        out = out.crop(bbox)
    return to_webp(out)


async def ai_image(prompt: str) -> bytes:
    q = urllib.parse.quote(f'{prompt}, sticker style, centered, plain white background, no text')
    params = {'width': 512, 'height': 512, 'nologo': 'true', 'model': 'flux'}
    headers = {}
    token = os.getenv('POLLINATIONS_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    async with httpx.AsyncClient(timeout=120) as client:
        for attempt in range(4):
            r = await client.get(AI_URL.format(q=q), params=params, headers=headers)
            if r.status_code == 200 and r.headers.get('content-type', '').startswith('image/'):
                return r.content
            if r.status_code in (429, 500, 502, 503):
                await asyncio.sleep(20 + attempt * 10)
                continue
            raise RuntimeError(f'service de dessin indisponible ({r.status_code})')
    raise RuntimeError('service de dessin trop occupé, réessaie dans une minute')


# ---------------------------------------------------------------- envoi

async def _deliver(update: Update, context, webp: bytes, emoji: str = '🙂'):
    """ajoute au pack ouvert s'il y en a un, sinon envoie le sticker."""
    import bot  # import tardif : évite l'import circulaire
    msg = update.effective_message
    active = context.user_data.get('active')
    if active:
        try:
            await bot.push_sticker(context, active, InputSticker(sticker=webp, emoji_list=[emoji], format='static'),
                                   update.effective_user.id)
            await msg.reply_html(f'✅ Ajouté au pack <b>{active["title"]}</b>\n{bot.pack_link(active["name"])}')
            return
        except TelegramError as e:
            logger.warning('ajout au pack impossible: %s', e)
            await msg.reply_text(f'⚠️ Ajout au pack impossible ({e.message}). Voici ton sticker :')
    await msg.reply_sticker(webp)


def _menu(update):
    import bot
    return kb.main_menu(bot.is_admin(update.effective_user.id))


# ---------------------------------------------------------------- gestion des packs

def _packs_kb(user_id):
    rows = [[InlineKeyboardButton(f'📦 {p["title"]}', callback_data=f'xm:{p["id"]}')]
            for p in (db.user_packs(user_id) or [])[:30]]
    return InlineKeyboardMarkup(rows) if rows else None


def _manage_kb(pid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('🗑 Supprimer un sticker', callback_data=f'xd:{pid}')],
        [InlineKeyboardButton('↕️ Déplacer un sticker', callback_data=f'xv:{pid}')],
        [InlineKeyboardButton('✏️ Renommer le pack', callback_data=f'xr:{pid}')],
        [InlineKeyboardButton('💣 Supprimer tout le pack', callback_data=f'xk:{pid}')],
    ])


def _own_pack(user_id, pid):
    for p in db.user_packs(user_id) or []:
        if p['id'] == pid:
            return p
    return None


async def on_extra_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    action, _, arg = q.data.partition(':')
    uid = update.effective_user.id
    try:
        pid = int(arg)
    except ValueError:
        return await q.answer()
    pack = _own_pack(uid, pid)
    if not pack:
        return await q.answer('Pack introuvable.', show_alert=True)
    await q.answer()
    ud = context.user_data
    ud['x_pack'] = {'id': pack['id'], 'name': pack['name'], 'title': pack['title']}
    if action == 'xm':
        return await q.edit_message_text(f'🗂 Pack « {pack["title"]} » : que veux-tu faire ?', reply_markup=_manage_kb(pid))
    if action == 'xd':
        ud['x_step'] = 'del'
        return await q.edit_message_text('🗑 Envoie-moi le sticker de ce pack à supprimer.')
    if action == 'xv':
        ud['x_step'] = 'move'
        return await q.edit_message_text('↕️ Envoie-moi le sticker de ce pack à déplacer.')
    if action == 'xr':
        ud['x_step'] = 'rename'
        return await q.edit_message_text('✏️ Envoie le nouveau nom du pack (max 64 caractères).')
    if action == 'xk':
        return await q.edit_message_text(
            f'⚠️ Supprimer définitivement « {pack["title"]} » ?',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✅ Oui, supprimer', callback_data=f'xy:{pid}'),
                                                InlineKeyboardButton('🚫 Non', callback_data=f'xm:{pid}')]]))
    if action == 'xy':
        try:
            await context.bot.delete_sticker_set(pack['name'])
        except TelegramError as e:
            logger.warning('delete_sticker_set: %s', e)
        db.delete_pack(pack['id'])
        if (ud.get('active') or {}).get('name') == pack['name']:
            ud.pop('active', None)
        ud.pop('x_pack', None)
        return await q.edit_message_text(f'💣 Pack « {pack["title"]} » supprimé.')


# ---------------------------------------------------------------- messages

async def on_extra_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    ud = context.user_data
    text = (msg.text or '').strip()
    step = ud.get('x_step')

    # boutons du menu
    if text == kb.BTN_TXT:
        ud['x_step'] = 'txt_photo'
        await msg.reply_html('💬 Envoie la <b>photo</b> (ou un sticker statique) sur laquelle écrire.', reply_markup=kb.cancel_menu())
        raise ApplicationHandlerStop
    if text == kb.BTN_NOBG:
        ud['x_step'] = 'nobg'
        await msg.reply_html('✂️ Envoie la <b>photo</b> : je garde seulement la personne ou l\'objet.', reply_markup=kb.cancel_menu())
        raise ApplicationHandlerStop
    if text == kb.BTN_AI:
        ud['x_step'] = 'ai'
        await msg.reply_html('🪄 Décris le sticker que tu veux (ex : <i>un chat ninja qui rigole</i>).', reply_markup=kb.cancel_menu())
        raise ApplicationHandlerStop
    if text == kb.BTN_MANAGE:
        markup = _packs_kb(update.effective_user.id)
        await msg.reply_text('🗂 Choisis le pack à gérer :' if markup else '📭 Tu n\'as encore aucun pack.', reply_markup=markup)
        raise ApplicationHandlerStop

    if not step:
        return
    if text == kb.BTN_CANCEL:
        for k in ('x_step', 'x_photo', 'x_sticker', 'x_pack'):
            ud.pop(k, None)
        return  # le bouton Annuler habituel prend le relais

    photo_id = None
    if msg.photo:
        photo_id = msg.photo[-1].file_id
    elif msg.sticker and not (msg.sticker.is_animated or msg.sticker.is_video):
        photo_id = msg.sticker.file_id
    elif msg.document and (msg.document.mime_type or '').startswith('image/'):
        photo_id = msg.document.file_id

    import bot
    try:
        if step == 'txt_photo':
            if not photo_id:
                await msg.reply_text('📸 Envoie une photo ou un sticker statique.')
            else:
                ud['x_photo'] = photo_id
                ud['x_step'] = 'txt_text'
                await msg.reply_text('✍️ Maintenant, écris le texte à afficher.')
        elif step == 'txt_text':
            if not text:
                await msg.reply_text('✍️ Écris le texte à afficher.')
            else:
                raw = await bot.download(context, ud.pop('x_photo'))
                ud.pop('x_step', None)
                webp = await bot.run_convert(caption_image, raw, text)
                await _deliver(update, context, webp, '💬')
                await msg.reply_text('🎉 Terminé !', reply_markup=_menu(update) if not ud.get('active') else kb.pack_menu())
        elif step == 'nobg':
            if not photo_id:
                await msg.reply_text('📸 Envoie une photo.')
            else:
                wait = await msg.reply_text('✂️ Je découpe… (quelques secondes)')
                raw = await bot.download(context, photo_id)
                webp = await bot.run_convert(remove_background, raw)
                ud.pop('x_step', None)
                await wait.delete()
                await _deliver(update, context, webp, '✂️')
                await msg.reply_text('🎉 Terminé !', reply_markup=_menu(update) if not ud.get('active') else kb.pack_menu())
        elif step == 'ai':
            if not text:
                await msg.reply_text('✍️ Décris le sticker en quelques mots.')
            else:
                ud.pop('x_step', None)
                wait = await msg.reply_text('🪄 Je dessine ton sticker… (jusqu\'à 2 minutes si le service est chargé)')
                img = await ai_image(text[:300])
                webp = await bot.run_convert(remove_background, img)
                await wait.delete()
                await _deliver(update, context, webp, '🪄')
                await msg.reply_text('🎉 Terminé !', reply_markup=_menu(update) if not ud.get('active') else kb.pack_menu())
        elif step in ('del', 'move'):
            pack = ud.get('x_pack') or {}
            if not msg.sticker or msg.sticker.set_name != pack.get('name'):
                await msg.reply_text('🧩 Envoie un sticker qui vient de ce pack.')
            elif step == 'del':
                await context.bot.delete_sticker_from_set(msg.sticker.file_id)
                db.remove_sticker(pack['id'], msg.sticker.file_unique_id)
                ud.pop('x_step', None)
                await msg.reply_text('🗑 Sticker supprimé du pack.')
            else:
                ud['x_sticker'] = msg.sticker.file_id
                ud['x_step'] = 'move_pos'
                await msg.reply_text('🔢 À quelle position ? (1 = premier)')
        elif step == 'move_pos':
            if not text.isdigit() or int(text) < 1:
                await msg.reply_text('🔢 Envoie un numéro (1, 2, 3…).')
            else:
                await context.bot.set_sticker_position_in_set(ud.pop('x_sticker'), int(text) - 1)
                ud.pop('x_step', None)
                await msg.reply_text(f'↕️ Sticker déplacé en position {text}.')
        elif step == 'rename':
            if not text or len(text) > 64:
                await msg.reply_text('✏️ Envoie un nom de 1 à 64 caractères.')
            else:
                pack = ud['x_pack']
                await context.bot.set_sticker_set_title(pack['name'], text)
                db.rename_pack(pack['id'], text)
                if (ud.get('active') or {}).get('name') == pack['name']:
                    ud['active']['title'] = text
                ud.pop('x_step', None)
                await msg.reply_text(f'✏️ Pack renommé en « {text} ».')
    except TelegramError as e:
        ud.pop('x_step', None)
        await msg.reply_text(f'❌ Telegram a refusé : {e.message}')
    except Exception as e:  # noqa: BLE001
        logger.exception('extras')
        ud.pop('x_step', None)
        await msg.reply_text(f'❌ Oups, ça n\'a pas marché : {e}')
    raise ApplicationHandlerStop


def register(app):
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND
                                   & (filters.TEXT | filters.PHOTO | filters.Sticker.ALL | filters.Document.IMAGE),
                                   on_extra_message), group=-1)
    app.add_handler(CallbackQueryHandler(on_extra_callback, pattern=r'^x[mdvrky]:'))
