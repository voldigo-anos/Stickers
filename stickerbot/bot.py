"""Bot Telegram de création de stickers — 100% en français."""

import asyncio
import html
import logging
import re

from telegram import InputSticker, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import hashlib

import config
import converter
import db
import keyboards as kb
import strings as S
import pinterest
import themes
import wastickers
from text_renderer import normalize_color

logger = logging.getLogger(__name__)

LINK_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{2,39}$')

# etats de conversation (stockes dans user_data['step'])
STEP_TITLE = 'title'
STEP_LINK = 'link'
STEP_SHAPE = 'shape'
STEP_WM = 'watermark'
STEP_COLOR = 'watermark_color'
STEP_AUTO_QUERY = 'auto_query'
STEP_AUTO_COUNT = 'auto_count'

_auto_running = set()

# les conversions ffmpeg/PIL sont lourdes : on limite le nombre simultane
# (mais on ne bloque JAMAIS la boucle d'evenements -> les autres users
# continuent d'utiliser le bot pendant une conversion)
_convert_sem = None
_user_locks = {}


def convert_semaphore() -> asyncio.Semaphore:
    global _convert_sem
    if _convert_sem is None:
        _convert_sem = asyncio.Semaphore(config.MAX_PARALLEL_CONVERSIONS)
    return _convert_sem


async def run_convert(func, *args):
    """execute une conversion dans un thread, avec limite de parallelisme"""
    async with convert_semaphore():
        return await asyncio.to_thread(func, *args)


def user_lock(user_id: int) -> asyncio.Lock:
    """une file d'attente par utilisateur : ses medias restent dans l'ordre,
    sans jamais bloquer les autres utilisateurs"""
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = _user_locks[user_id] = asyncio.Lock()
    return lock



# --------------------------------------------------------------------------
# utilitaires
# --------------------------------------------------------------------------

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMINS


def pack_link(name: str) -> str:
    return f'https://t.me/addstickers/{name}'


async def send_pack_card(bot, chat_id: int, title: str, count: int, name: str):
    """envoie le pack termine avec le bouton « Voir le pack » (pas de lien brut)"""
    return await bot.send_message(
        chat_id,
        S.PACK_CARD.format(title=html.escape(title), count=count),
        parse_mode=ParseMode.HTML,
        reply_markup=kb.pack_actions(name),
    )


async def reply(update: Update, text: str, **kwargs):
    return await update.effective_message.reply_html(text, **kwargs)


def extract_media(message):
    """renvoie (kind, file_id, file_unique_id, suffix, emoji, set_name) ou None.

    kind ∈ static | video | animated (format Telegram du sticker a creer)
    """
    if message.sticker:
        st = message.sticker
        if st.is_animated:
            kind, suffix = 'animated', '.tgs'
        elif st.is_video:
            kind, suffix = 'video', '.webm'
        else:
            kind, suffix = 'static', '.webp'
        return kind, st.file_id, st.file_unique_id, suffix, st.emoji or '🙂', st.set_name

    if message.photo:
        ph = message.photo[-1]
        return 'photo', ph.file_id, ph.file_unique_id, '.jpg', '🙂', None

    if message.animation:
        an = message.animation
        return 'anim', an.file_id, an.file_unique_id, '.mp4', '🙂', None

    if message.video:
        vi = message.video
        return 'anim', vi.file_id, vi.file_unique_id, '.mp4', '🙂', None

    if message.document:
        doc = message.document
        mime = doc.mime_type or ''
        if mime.startswith('image/'):
            return 'photo', doc.file_id, doc.file_unique_id, '.png', '🙂', None
        if mime.startswith('video/'):
            return 'anim', doc.file_id, doc.file_unique_id, '.mp4', '🙂', None

    return None


async def download(context, file_id: str) -> bytes:
    tg_file = await context.bot.get_file(file_id)
    return bytes(await tg_file.download_as_bytearray())


def styled(active) -> bool:
    """le pack impose-t-il une forme ou une ecriture ?"""
    return bool(
        active.get('shape', converter.SHAPE_ORIGINAL) != converter.SHAPE_ORIGINAL
        or (active.get('watermark') or '').strip()
    )


async def build_input_sticker(context, kind, file_id, suffix, emoji, active) -> InputSticker:
    """prepare un InputSticker en appliquant la forme et l'ecriture du pack.

    Les stickers existants passent par leur file_id quand aucun style n'est
    demande, sinon ils sont re-encodes pour porter la forme / l'ecriture.
    """
    shape = active.get('shape', converter.SHAPE_ORIGINAL)
    watermark = (active.get('watermark') or '').strip()
    color = active.get('watermark_color', '#FFFFFF')

    if kind == 'animated':
        # les .tgs (stickers animes Telegram) ne peuvent pas etre retouches
        return InputSticker(sticker=file_id, emoji_list=[emoji], format='animated')

    if kind in ('static', 'video') and not styled(active):
        return InputSticker(sticker=file_id, emoji_list=[emoji], format=kind)

    raw = await download(context, file_id)

    if kind in ('photo', 'static'):
        data = await run_convert(converter.image_to_webp, raw, shape, watermark, color)
        return InputSticker(sticker=data, emoji_list=[emoji], format='static')

    data = await run_convert(converter.video_to_webm, raw, suffix, shape, watermark, color)
    return InputSticker(sticker=data, emoji_list=[emoji], format='video')


async def push_sticker(context, active, input_sticker, user_id) -> None:
    """cree le pack s'il n'existe pas encore, sinon ajoute le sticker"""
    if not active['created']:
        await context.bot.create_new_sticker_set(
            user_id=user_id,
            name=active['name'],
            title=active['title'],
            stickers=[input_sticker],
        )
        active['created'] = True
        active['id'] = db.add_pack(
            user_id, active['name'], active['title'],
            active.get('shape', converter.SHAPE_ORIGINAL),
            active.get('watermark', ''),
            active.get('watermark_color', '#FFFFFF'),
        )

    else:
        await context.bot.add_sticker_to_set(
            user_id=user_id,
            name=active['name'],
            sticker=input_sticker,
        )


# --------------------------------------------------------------------------
# commandes de base
# --------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.save_user(user)
    if db.is_banned(user.id):
        return await reply(update, S.BANNED, reply_markup=kb.remove())

    context.user_data.clear()
    await reply(
        update,
        S.START.format(name=user.first_name or 'toi'),
        reply_markup=kb.main_menu(is_admin(user.id)),
    )
    await update.effective_message.reply_html(
        '🔗 <b>Rejoins-nous :</b>', reply_markup=kb.start_links()
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update, S.HELP, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await reply(update, S.CANCELLED, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.save_user(update.effective_user)
    context.user_data.clear()
    context.user_data['step'] = STEP_TITLE
    await reply(update, S.ASK_TITLE, reply_markup=kb.cancel_menu())


async def cmd_mypacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    packs = db.user_packs(update.effective_user.id)
    if not packs:
        return await reply(update, S.NO_ACTIVE_PACK, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))

    await reply(update, f'📦 <b>Tes packs</b> — {len(packs)} au total')
    for row in packs[:20]:
        text = (
            f'📦 <b>{row["title"]}</b>\n'
            f'🔢 {row["count"]} sticker(s)\n'
            f'🔗 <code>{pack_link(row["name"])}</code>'
        )
        await update.effective_message.reply_html(text, reply_markup=kb.pack_actions(row['name']))


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        limit = int(context.args[0]) if context.args else 10
    except (ValueError, IndexError):
        limit = 10
    limit = max(3, min(limit, 50))

    rows = db.leaderboard(limit)
    if not rows:
        return await reply(update, S.LEADERBOARD_EMPTY)

    medals = ['🥇', '🥈', '🥉']
    lines = [S.LEADERBOARD_HEADER]
    for i, row in enumerate(rows):
        medal = medals[i] if i < 3 else f'{i + 1}.'
        name = row['first_name'] or (f'@{row["username"]}' if row['username'] else 'Anonyme')
        lines.append(S.LEADERBOARD_ROW.format(medal=medal, name=name, packs=row['packs'], stickers=row['stickers']))

    text = '\n'.join(lines)
    rank, me = db.user_rank(update.effective_user.id)
    if rank:
        text += S.LEADERBOARD_ME.format(rank=rank, stickers=me['stickers'])

    await reply(update, text, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))


# --------------------------------------------------------------------------
# creation de pack (texte)
# --------------------------------------------------------------------------

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.save_user(user)
    if db.is_banned(user.id):
        return await reply(update, S.BANNED, reply_markup=kb.remove())

    text = (update.effective_message.text or '').strip()

    if text == kb.BTN_NEW:
        return await cmd_new(update, context)
    if text == kb.BTN_MY_PACKS:
        return await cmd_mypacks(update, context)
    if text == kb.BTN_TOP:
        return await cmd_top(update, context)
    if text == kb.BTN_HELP:
        return await cmd_help(update, context)
    if text == kb.BTN_CANCEL:
        return await cmd_cancel(update, context)
    if text == kb.BTN_ADMIN:
        return await cmd_admin(update, context)
    if text == kb.BTN_DONE:
        return await finish_pack(update, context)
    if text == kb.BTN_CONVERT:
        context.user_data.pop('theme_mode', None)
        context.user_data.pop('step', None)
        context.user_data.pop('wa_pending', None)
        context.user_data['convert_mode'] = True
        return await reply(update, S.CONVERT_ASK, reply_markup=kb.cancel_menu())
    if text == kb.BTN_AUTO:
        context.user_data.clear()
        return await reply(update, S.AUTO_ASK_FORMAT, reply_markup=kb.auto_format_choice())
    if text == kb.BTN_THEME:
        context.user_data.clear()
        context.user_data['theme_mode'] = True
        return await reply(update, S.THEME_ASK, reply_markup=kb.cancel_menu())
    if text == kb.BTN_WA:
        active = context.user_data.get('active')
        if not active:
            context.user_data.pop('theme_mode', None)
            context.user_data.pop('step', None)
            context.user_data['convert_mode'] = True
            return await reply(update, S.CONVERT_ASK, reply_markup=kb.cancel_menu())
        return await export_whatsapp(update, context, active['name'])
    if text == kb.BTN_STYLE:
        active = context.user_data.get('active')
        if not active:
            return await reply(update, S.NO_ACTIVE_PACK)
        context.user_data['step'] = STEP_SHAPE
        return await reply(update, S.ASK_SHAPE, reply_markup=kb.shape_choice())
    if text == kb.BTN_NO_WM and context.user_data.get('step') == STEP_WM:
        return await apply_watermark(update, context, '')


    step = context.user_data.get('step')

    if step == STEP_AUTO_QUERY:
        query = text[:80]
        if not query:
            return await reply(update, S.AUTO_ASK_QUERY.format(fmt=''))
        context.user_data['auto']['query'] = query
        context.user_data['step'] = STEP_AUTO_COUNT
        return await reply(update, S.AUTO_ASK_COUNT, reply_markup=kb.auto_count_menu())

    if step == STEP_AUTO_COUNT:
        count = pinterest.parse_count(text)
        if count is None:
            return await reply(update, S.AUTO_BAD_COUNT, reply_markup=kb.auto_count_menu())
        context.user_data['auto']['count'] = count
        context.user_data['step'] = STEP_TITLE
        return await reply(update, S.ASK_TITLE, reply_markup=kb.cancel_menu())

    if step == STEP_TITLE:
        title = text[:64]
        context.user_data['title'] = title
        context.user_data['step'] = STEP_LINK
        return await reply(
            update,
            S.ASK_LINK.format(bot=context.bot.username),
            reply_markup=kb.cancel_menu(),
        )

    if step == STEP_LINK:
        link = text.lstrip('@').strip()
        if not LINK_RE.match(link):
            return await reply(update, S.BAD_LINK)

        name = f'{link}_by_{context.bot.username}'
        if db.get_pack_by_name(name):
            return await reply(update, S.LINK_TAKEN)
        try:
            await context.bot.get_sticker_set(name)
            return await reply(update, S.LINK_TAKEN)
        except TelegramError:
            pass

        auto = context.user_data.get('auto')
        if auto and auto.get('count'):
            # pack automatique : forme carree imposee, on demande juste l'ecriture
            auto['name'] = name
            context.user_data['step'] = STEP_WM
            return await reply(update, S.ASK_WM, reply_markup=kb.wm_menu())

        context.user_data['step'] = STEP_SHAPE
        context.user_data['draft'] = {'name': name, 'title': context.user_data.get('title', 'Mon pack')}
        return await reply(update, S.ASK_SHAPE, reply_markup=kb.shape_choice())

    if step == STEP_WM:
        if len(text) > 100:
            return await reply(update, '⚠️ Écriture trop longue : maximum 100 caractères.')
        return await apply_watermark(update, context, text)

    if step == STEP_COLOR:
        try:
            color_value, color_name = kb.selected_color(text)
            color = normalize_color(color_value)
        except ValueError:
            return await reply(update, S.BAD_COLOR, reply_markup=kb.color_menu())
        await reply(update, S.COLOR_CHOSEN.format(color=html.escape(color_name)))
        return await finish_style(update, context, color)


    await reply(update, S.NO_ACTIVE_PACK, reply_markup=kb.main_menu(is_admin(user.id)))


async def apply_shape(update: Update, context: ContextTypes.DEFAULT_TYPE, shape: str):
    """etape 1 du style : la forme du sticker (original / carre / rond)"""
    context.user_data['shape'] = shape
    context.user_data['step'] = STEP_WM
    await context.bot.send_message(
        update.effective_chat.id,
        S.ASK_WM,
        parse_mode=ParseMode.HTML,
        reply_markup=kb.wm_menu(),
    )


async def apply_watermark(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Store text, then let the user choose its color."""
    context.user_data['watermark'] = (text or '').strip()
    if text.strip():
        context.user_data['step'] = STEP_COLOR
        return await reply(update, S.ASK_COLOR, reply_markup=kb.color_menu())
    return await finish_style(update, context, '#FFFFFF')


async def finish_style(update, context, color):
    auto = context.user_data.get('auto')
    if auto and auto.get('name') and auto.get('count'):
        watermark = (context.user_data.pop('watermark', '') or '').strip()
        if watermark:
            # on teste l'ecriture avant de lancer 60 a 120 stickers
            try:
                await asyncio.to_thread(
                    converter.watermark_layer, 512, 512, watermark, converter.SHAPE_COVER, color
                )
            except ValueError as exc:
                context.user_data['step'] = STEP_WM
                return await reply(update, f'⚠️ {html.escape(str(exc))}', reply_markup=kb.wm_menu())
        return await start_auto_pack(update, context, auto['name'], auto, watermark, color)

    text = context.user_data.pop('watermark', '')
    shape = context.user_data.pop('shape', converter.SHAPE_ORIGINAL)
    watermark = (text or '').strip()
    context.user_data['step'] = None

    active = context.user_data.get('active')
    draft = context.user_data.pop('draft', None)

    if draft:
        active = {
            'name': draft['name'],
            'title': draft['title'],
            'created': False,
            'id': None,
            'shape': shape,
            'watermark': watermark,
            'watermark_color': color,
        }
        context.user_data['active'] = active
    elif active:
        active['shape'] = shape
        active['watermark'] = watermark
        active['watermark_color'] = color
        if active.get('id'):
            db.set_pack_style(active['id'], shape, watermark, color)
    else:
        return await reply(update, S.NO_ACTIVE_PACK, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))

    return await reply(
        update,
        S.PACK_READY.format(
            title=html.escape(active['title']),
            link=pack_link(active['name']),
            shape=S.SHAPE_LABELS[shape],
            wm=html.escape(watermark) + ' · ' + kb.color_label(color) if watermark else 'aucune',
        ),
        reply_markup=kb.pack_menu(),
    )


async def finish_pack(update: Update, context: ContextTypes.DEFAULT_TYPE):

    active = context.user_data.get('active')
    if not active or not active.get('created'):
        return await reply(update, S.NO_ACTIVE_PACK, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))

    count = db.pack_count(active['id'])
    context.user_data.pop('active', None)
    await reply(
        update,
        S.FINISHED,
        reply_markup=kb.main_menu(is_admin(update.effective_user.id)),
    )
    await send_pack_card(context.bot, update.effective_chat.id, active['title'], count, active['name'])


# --------------------------------------------------------------------------
# medias
# --------------------------------------------------------------------------

async def on_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.save_user(user)
    if db.is_banned(user.id):
        return await reply(update, S.BANNED, reply_markup=kb.remove())

    media = extract_media(update.effective_message)
    if not media:
        return await reply(update, S.UNSUPPORTED)

    if context.user_data.get('theme_mode'):
        if media[0] != 'photo':
            return await reply(update, S.THEME_BAD_MEDIA, reply_markup=kb.cancel_menu())
        context.user_data['theme_mode'] = False
        waiting = await reply(update, S.THEME_WORKING)
        context.application.create_task(
            _theme_job(context, update.effective_chat.id, media[1], waiting)
        )
        return

    active = context.user_data.get('active')
    if not active or context.user_data.get('convert_mode'):
        # conversion directe vers WhatsApp, sans creer de pack
        context.user_data['wa_pending'] = media
        await reply(update, '✅ Sticker reçu ! Je prépare les options de conversion 🟢')
        set_name = media[5]
        count = 0
        title = ''
        if set_name:
            try:
                source = await context.bot.get_sticker_set(set_name)
                count, title = len(source.stickers), source.title
            except TelegramError:
                set_name = None
        context.user_data['wa_source'] = set_name
        return await reply(
            update,
            S.CONVERT_CHOICE.format(title=html.escape(title), count=count) if set_name else S.CONVERT_ONE_ASK,
            reply_markup=kb.convert_choice(set_name),
        )

    kind, file_id, unique_id, suffix, emoji, set_name = media

    # sticker appartenant a un pack existant -> on propose d'importer tout le pack
    if set_name and set_name != active['name']:
        try:
            source = await context.bot.get_sticker_set(set_name)
        except TelegramError:
            source = None
        if source:
            context.user_data['pending'] = media
            return await reply(
                update,
                S.IMPORT_ASK.format(title=source.title, count=len(source.stickers)),
                reply_markup=kb.import_choice(set_name),
            )

    await add_one(update, context, media)


async def add_one(update: Update, context: ContextTypes.DEFAULT_TYPE, media):
    """ajoute un media au pack actif, en tache de fond pour ne pas bloquer le bot"""
    active = context.user_data.get('active')
    if not active:
        return await reply(update, S.NO_ACTIVE_PACK, reply_markup=kb.main_menu(is_admin(update.effective_user.id)))

    if active['id'] and db.pack_count(active['id']) >= config.MAX_STICKERS_PER_PACK:
        return await reply(update, S.PACK_FULL.format(max=config.MAX_STICKERS_PER_PACK))

    if active['id'] and db.has_sticker(active['id'], media[2]):
        return await reply(update, S.DUPLICATE)

    waiting = await reply(update, S.WORKING)
    context.application.create_task(
        _add_one_job(context, update.effective_user.id, active, media, waiting)
    )


async def _add_one_job(context, user_id, active, media, waiting):
    kind, file_id, unique_id, suffix, emoji, _ = media
    try:
        async with user_lock(user_id):
            if active['id'] and db.has_sticker(active['id'], unique_id):
                return await waiting.edit_text(S.DUPLICATE, parse_mode=ParseMode.HTML)
            input_sticker = await build_input_sticker(context, kind, file_id, suffix, emoji, active)
            await push_sticker(context, active, input_sticker, user_id)
            db.add_sticker(active['id'], unique_id)

        await waiting.edit_text(
            S.ADDED.format(count=db.pack_count(active['id']), title=active['title'], link=pack_link(active['name'])),
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:  # noqa: BLE001 - l'utilisateur doit TOUJOURS avoir une reponse
        logger.exception('ajout impossible')
        try:
            await waiting.edit_text(S.ERROR.format(error=html.escape(str(exc)[:200])), parse_mode=ParseMode.HTML)
        except TelegramError:
            pass



async def import_full_pack(update: Update, context: ContextTypes.DEFAULT_TYPE, set_name: str):
    query = update.callback_query
    active = context.user_data.get('active')
    if not active:
        return await query.edit_message_text(S.NO_ACTIVE_PACK, parse_mode=ParseMode.HTML)

    await query.edit_message_text(S.WORKING, parse_mode=ParseMode.HTML)
    # tache de fond : les autres utilisateurs continuent d'etre servis
    context.application.create_task(
        _import_full_pack_job(
            context, update.effective_user.id, update.effective_chat.id, active, set_name
        )
    )


async def _import_full_pack_job(context, user_id, chat_id, active, set_name):
    try:
        source = await context.bot.get_sticker_set(set_name)
    except TelegramError as exc:
        return await context.bot.send_message(
            chat_id, S.ERROR.format(error=html.escape(str(exc)[:200])), parse_mode=ParseMode.HTML
        )

    added = dupes = failed = 0
    async with user_lock(user_id):
        for st in source.stickers:
            if active['id'] and db.pack_count(active['id']) >= config.MAX_STICKERS_PER_PACK:
                break
            if active['id'] and db.has_sticker(active['id'], st.file_unique_id):
                dupes += 1
                continue

            if st.is_animated:
                kind = 'animated'
            elif st.is_video:
                kind = 'video'
            else:
                kind = 'static'
            suffix = '.webm' if kind == 'video' else '.webp'

            try:
                input_sticker = await build_input_sticker(
                    context, kind, st.file_id, suffix, st.emoji or '🙂', active
                )
                await push_sticker(context, active, input_sticker, user_id)
                db.add_sticker(active['id'], st.file_unique_id)
                added += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning('import sticker echoue: %s', exc)
                failed += 1
            await asyncio.sleep(0.6)

    await context.bot.send_message(
        chat_id=chat_id,
        text=S.IMPORT_DONE.format(added=added, dupes=dupes, failed=failed, link=pack_link(active['name'])),
        parse_mode=ParseMode.HTML,
        reply_markup=kb.pack_menu(),
    )



# --------------------------------------------------------------------------
# WhatsApp
# --------------------------------------------------------------------------

async def export_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE, set_name: str):
    """la conversion tourne en tache de fond : le bot reste dispo pour tous"""
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id, S.WA_START, parse_mode=ParseMode.HTML)
    context.application.create_task(_export_whatsapp_job(context, chat_id, set_name))


async def _export_whatsapp_job(context, chat_id, set_name):
    try:
        await _build_whatsapp_export(context, chat_id, set_name)
    except Exception as exc:
        await report_job_error(context, chat_id, exc)


async def report_job_error(context, chat_id, exc):
    logger.error('conversion whatsapp echouee', exc_info=(type(exc), exc, exc.__traceback__))
    try:
        await context.bot.send_message(
            chat_id, S.ERROR.format(error=html.escape(str(exc)[:200])), parse_mode=ParseMode.HTML
        )
    except TelegramError:
        logger.exception('impossible de transmettre le message d’erreur')


async def _build_whatsapp_export(context, chat_id, set_name):
    try:
        source = await context.bot.get_sticker_set(set_name)
    except TelegramError as exc:
        return await context.bot.send_message(
            chat_id, S.ERROR.format(error=html.escape(str(exc)[:200])), parse_mode=ParseMode.HTML
        )

    webps = []
    failed = 0
    for st in source.stickers[:config.MAX_STICKERS_PER_PACK]:
        if st.is_animated:
            failed += 1
            continue  # les stickers .tgs ne sont pas supportes par WhatsApp
        suffix = '.webm' if st.is_video else '.webp'
        try:
            raw = await download(context, st.file_id)
            webps.append(await run_convert(converter.to_wa_webp, raw, suffix))
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.warning('conversion whatsapp echouee: %s', exc)

    if not webps:
        return await context.bot.send_message(
            chat_id, S.ERROR.format(error='aucun sticker convertible'), parse_mode=ParseMode.HTML
        )

    tray = await run_convert(wastickers.build_tray_icon_png, webps[0])
    files = await run_convert(
        wastickers.build_wastickers_files,
        source.title,
        f'@{context.bot.username}',
        webps,
        tray,
        config.WA_STICKERS_PER_FILE,
    )
    if len(files) > 1:
        await context.bot.send_message(
            chat_id, S.WA_SPLIT.format(files=len(files), per=config.WA_STICKERS_PER_FILE),
            parse_mode=ParseMode.HTML,
        )
    if failed:
        await context.bot.send_message(
            chat_id, f'⚠️ {failed} sticker(s) non convertible(s) ignoré(s) (dont les animations .tgs).'
        )

    for filename, buf in files:
        await context.bot.send_document(chat_id, document=buf, filename=filename)

    await context.bot.send_message(chat_id, S.WA_DONE, parse_mode=ParseMode.HTML)


async def _convert_one_job(context, chat_id, media):
    """convertit un seul sticker / media en fichier .wastickers"""
    kind, file_id, unique_id, suffix, emoji, _ = media
    try:
        if kind == 'animated':
            raise RuntimeError('les stickers animés (.tgs) ne sont pas supportés par WhatsApp')
        raw = await download(context, file_id)
        webp = await run_convert(converter.to_wa_webp, raw, suffix)
        tray = await run_convert(wastickers.build_tray_icon_png, webp)
        files = await run_convert(
            wastickers.build_wastickers_files, 'Sticker', f'@{context.bot.username}', [webp], tray, 30
        )
        for filename, buf in files:
            await context.bot.send_document(chat_id, document=buf, filename=filename)
        await context.bot.send_message(chat_id, S.WA_DONE, parse_mode=ParseMode.HTML)
    except Exception as exc:  # noqa: BLE001
        await report_job_error(context, chat_id, exc)



async def _theme_job(context, chat_id, file_id, waiting):
    """cree un theme .attheme a partir d'une photo, en tache de fond"""
    try:
        raw = await download(context, file_id)
        attheme = await run_convert(themes.build_attheme, raw)
        await context.bot.send_document(
            chat_id, document=attheme, filename='mon_theme.attheme',
            caption=S.THEME_DONE, parse_mode=ParseMode.HTML,
        )
        try:
            await waiting.delete()
        except TelegramError:
            pass
    except Exception as exc:  # noqa: BLE001
        logger.exception('creation de theme echouee')
        try:
            await waiting.edit_text(
                S.ERROR.format(error=html.escape(str(exc)[:200])),
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            pass


# --------------------------------------------------------------------------
# pack automatique (Pinterest)
# --------------------------------------------------------------------------

async def start_auto_pack(update, context, name, auto, watermark='', color='#FFFFFF'):
    user_id = update.effective_user.id
    if user_id in _auto_running:
        return await reply(update, S.AUTO_BUSY)
    active = {
        'name': name,
        'title': context.user_data.get('title', 'Mon pack'),
        'created': False,
        'id': None,
        # tous les stickers du pack automatique sont carres (image pleine 512x512)
        'shape': converter.SHAPE_COVER,
        'watermark': watermark,
        'watermark_color': color,
    }
    context.user_data.clear()
    waiting = await reply(
        update, S.AUTO_SEARCHING.format(query=html.escape(auto['query'])),
        reply_markup=kb.main_menu(is_admin(user_id)),
    )
    _auto_running.add(user_id)
    context.application.create_task(
        _auto_pack_job(context, user_id, active, auto['mode'], auto['query'], auto['count'], waiting)
    )


async def _auto_sticker(url, mode, is_backup, active):
    shape = active.get('shape', converter.SHAPE_COVER)
    watermark = (active.get('watermark') or '').strip()
    color = active.get('watermark_color', '#FFFFFF')
    raw = await asyncio.to_thread(pinterest.fetch, url)
    if mode == pinterest.MODE_STATIC:
        data = await run_convert(converter.image_to_webp, raw, shape, watermark, color)
        return InputSticker(sticker=data, emoji_list=['🙂'], format='static')
    if is_backup:
        raw = await run_convert(converter.photo_to_motion_mp4, raw)
        suffix = '.mp4'
    else:
        suffix = '.gif'
    data = await run_convert(converter.video_to_webm, raw, suffix, shape, watermark, color)
    return InputSticker(sticker=data, emoji_list=['🙂'], format='video')


async def _auto_pack_job(context, user_id, active, mode, query, want, waiting):
    fmt = S.AUTO_FORMATS[mode]
    done = 0
    try:
        main, backup = await asyncio.to_thread(pinterest.collect, query, mode, want)
        candidates = [(u, False) for u in main] + [(u, True) for u in backup]
        if not candidates:
            return await waiting.edit_text(S.AUTO_NOTHING.format(query=html.escape(query)), parse_mode=ParseMode.HTML)
        seen = set()
        for url, is_backup in candidates:
            if done >= want:
                break
            key = hashlib.sha1(url.encode()).hexdigest()[:32]
            if key in seen:
                continue
            seen.add(key)
            try:
                sticker = await _auto_sticker(url, mode, is_backup, active)
                async with user_lock(user_id):
                    await push_sticker(context, active, sticker, user_id)
                    db.add_sticker(active['id'], 'pin_' + key)
                done += 1
            except Exception:  # noqa: BLE001 - une image ratée ne bloque pas le pack
                logger.warning('image pinterest ignorée: %s', url, exc_info=True)
                continue
            if done % 10 == 0 and done < want:
                try:
                    await waiting.edit_text(
                        S.AUTO_PROGRESS.format(done=done, want=want, fmt=fmt),
                        parse_mode=ParseMode.HTML,
                    )
                except TelegramError:
                    pass
            await asyncio.sleep(0.3)  # reste sous les limites de Telegram
        if not done:
            return await waiting.edit_text(S.AUTO_NOTHING.format(query=html.escape(query)), parse_mode=ParseMode.HTML)
        text = S.AUTO_DONE.format(title=html.escape(active['title']), done=done)
        if done < want:
            text += S.AUTO_PARTIAL.format(done=done, want=want)
        await waiting.edit_text(text, parse_mode=ParseMode.HTML)
        # le pack est envoye avec le bouton « Voir le pack » (pas de lien brut)
        await send_pack_card(
            context.bot, waiting.chat_id, active['title'],
            db.pack_count(active['id']), active['name'],
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception('pack automatique échoué')
        try:
            await waiting.edit_text(S.ERROR.format(error=html.escape(str(exc)[:200])), parse_mode=ParseMode.HTML)
        except TelegramError:
            pass
    finally:
        _auto_running.discard(user_id)


# --------------------------------------------------------------------------
# callbacks
# --------------------------------------------------------------------------

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ''

    if data.startswith('auto:'):
        mode = data[5:]
        if mode not in (pinterest.MODE_STATIC, pinterest.MODE_GIF):
            context.user_data.clear()
            return await query.edit_message_text(S.CANCELLED, parse_mode=ParseMode.HTML)
        context.user_data.clear()
        context.user_data['auto'] = {'mode': mode}
        context.user_data['step'] = STEP_AUTO_QUERY
        await query.edit_message_text(
            S.AUTO_ASK_QUERY.format(fmt=S.AUTO_FORMATS[mode]), parse_mode=ParseMode.HTML
        )
        return await context.bot.send_message(
            update.effective_chat.id, '✍️', reply_markup=kb.cancel_menu()
        )

    if data.startswith('shape:'):
        shape = data.split(':', 1)[1]
        if shape not in (converter.SHAPE_ORIGINAL, converter.SHAPE_SQUARE, converter.SHAPE_ROUND):
            shape = converter.SHAPE_ORIGINAL
        await query.edit_message_text(
            S.SHAPE_CHOSEN.format(shape=S.SHAPE_LABELS[shape]), parse_mode=ParseMode.HTML
        )
        return await apply_shape(update, context, shape)

    if data.startswith('imp:'):
        return await import_full_pack(update, context, data[4:])


    if data == 'imp_one':
        media = context.user_data.pop('pending', None)
        if not media:
            return await query.edit_message_text(S.CANCELLED, parse_mode=ParseMode.HTML)
        await query.edit_message_text('🧩 Ajout du sticker...', parse_mode=ParseMode.HTML)
        return await add_one(update, context, media)

    if data == 'imp_no':
        context.user_data.pop('pending', None)
        return await query.edit_message_text(S.CANCELLED, parse_mode=ParseMode.HTML)

    if data.startswith('use:'):
        name = data[4:]
        row = db.get_pack(update.effective_user.id, name)
        if not row:
            return await query.edit_message_text(S.NO_ACTIVE_PACK, parse_mode=ParseMode.HTML)
        context.user_data['active'] = {
            'name': row['name'], 'title': row['title'], 'created': True, 'id': row['id'],
            'shape': (row['shape'] if 'shape' in row.keys() else None) or converter.SHAPE_ORIGINAL,
            'watermark': (row['watermark'] if 'watermark' in row.keys() else '') or '',
            'watermark_color': row['watermark_color'] if 'watermark_color' in row.keys() else '#FFFFFF',
        }
        await query.edit_message_text(
            S.PACK_READY.format(
                title=row['title'],
                link=pack_link(row['name']),
                shape=S.SHAPE_LABELS[context.user_data['active']['shape']],
                wm=html.escape(context.user_data['active']['watermark']) or 'aucune',
            ),
            parse_mode=ParseMode.HTML,
        )

        return await context.bot.send_message(
            update.effective_chat.id, '📨 En attente de tes médias...', reply_markup=kb.pack_menu()
        )

    if data.startswith('wa:'):
        return await export_whatsapp(update, context, data[3:])

    if data == 'wa_pack':
        name = context.user_data.pop('wa_source', None)
        context.user_data.pop('wa_pending', None)
        if not name:
            return await query.edit_message_text(S.CANCELLED, parse_mode=ParseMode.HTML)
        await query.edit_message_text('📦 Conversion du pack sélectionnée.', parse_mode=ParseMode.HTML)
        return await export_whatsapp(update, context, name)

    if data == 'wa_one':
        media = context.user_data.pop('wa_pending', None)
        context.user_data.pop('wa_source', None)
        if not media:
            return await query.edit_message_text(S.CANCELLED, parse_mode=ParseMode.HTML)
        await query.edit_message_text(S.WA_START, parse_mode=ParseMode.HTML)
        context.application.create_task(
            _convert_one_job(context, update.effective_chat.id, media)
        )
        return

    if data == 'wa_no':
        context.user_data.pop('wa_pending', None)
        context.user_data.pop('wa_source', None)
        return await query.edit_message_text(S.CANCELLED, parse_mode=ParseMode.HTML)

    if data.startswith('del:'):
        name = data[4:]
        row = db.get_pack(update.effective_user.id, name)
        if row:
            db.delete_pack(row['id'])
        return await query.edit_message_text('🗑 Pack oublié (il reste sur Telegram).', parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------
# admin
# --------------------------------------------------------------------------

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await reply(update, S.NOT_ADMIN)
    stats = db.global_stats()
    await reply(update, S.ADMIN_PANEL.format(**stats), reply_markup=kb.main_menu(True))


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_admin(update, context)


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await reply(update, S.NOT_ADMIN)
    if not context.args:
        return await reply(update, '📣 Utilisation : <code>/broadcast ton message</code>')

    message = update.effective_message.text.split(' ', 1)[1]
    ok = failed = 0
    for user_id in db.all_user_ids():
        try:
            await context.bot.send_message(user_id, message, parse_mode=ParseMode.HTML)
            ok += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)
    await reply(update, S.BROADCAST_DONE.format(ok=ok, failed=failed))


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await reply(update, S.NOT_ADMIN)
    if not context.args or not context.args[0].isdigit():
        return await reply(update, '🚫 Utilisation : <code>/ban 123456789</code>')
    db.set_banned(int(context.args[0]), True)
    await reply(update, f'🚫 Utilisateur <code>{context.args[0]}</code> banni.')


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await reply(update, S.NOT_ADMIN)
    if not context.args or not context.args[0].isdigit():
        return await reply(update, '✅ Utilisation : <code>/unban 123456789</code>')
    db.set_banned(int(context.args[0]), False)
    await reply(update, f'✅ Utilisateur <code>{context.args[0]}</code> débanni.')


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception('erreur non gerée', exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                update.effective_chat.id,
                '⚠️ Je n’ai pas pu traiter ce message. Réessaie depuis le menu /start.'
            )
        except TelegramError:
            logger.exception('impossible de signaler l’erreur à l’utilisateur')


# --------------------------------------------------------------------------
# app
# --------------------------------------------------------------------------

async def post_init(app: Application):
    from telegram import BotCommand

    await app.bot.set_my_commands([
        BotCommand('start', '🏠 Menu principal'),
        BotCommand('new', '✏️ Créer un pack'),
        BotCommand('mypacks', '📦 Mes packs'),
        BotCommand('top', '🏆 Classement'),
        BotCommand('help', '❓ Aide'),
        BotCommand('cancel', '🚫 Annuler'),
    ])


def build_application() -> Application:
    db.init()

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        # plusieurs mises a jour traitees en parallele : un utilisateur qui
        # convertit un gros pack ne bloque plus les autres
        .concurrent_updates(config.CONCURRENT_UPDATES)
        .connection_pool_size(config.CONNECTION_POOL_SIZE)
        .pool_timeout(60.0)
        .read_timeout(60.0)
        .write_timeout(120.0)
        .connect_timeout(30.0)
        .media_write_timeout(180.0)
        .build()
    )


    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('help', cmd_help))
    app.add_handler(CommandHandler('new', cmd_new))
    app.add_handler(CommandHandler('mypacks', cmd_mypacks))
    app.add_handler(CommandHandler('top', cmd_top))
    app.add_handler(CommandHandler('cancel', cmd_cancel))
    app.add_handler(CommandHandler('admin', cmd_admin))
    app.add_handler(CommandHandler('stats', cmd_stats))
    app.add_handler(CommandHandler('broadcast', cmd_broadcast))
    app.add_handler(CommandHandler('ban', cmd_ban))
    app.add_handler(CommandHandler('unban', cmd_unban))

    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Sticker.ALL | filters.Document.ALL,
        on_media,
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    return app
