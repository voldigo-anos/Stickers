"""Telegram-native presentation applied at the outgoing request boundary."""
import asyncio
import html
import json
import logging
import re

from telegram.request import HTTPXRequest

logger = logging.getLogger(__name__)


def progressive_frames(text, max_frames=12):
    """Reveal words without cutting HTML tags/entities or leaving tags unclosed."""
    tokens = re.findall(r'<[^>]+>|&(?:#\d+|#x[\da-fA-F]+|\w+);|[^\s<&]+|\s+|[<&]', text)
    words = sum(1 for token in tokens if not token.startswith('<') and token.strip())
    if words < 5:
        return [text]
    stride = max(1, (words + max_frames - 1) // max_frames)
    frames, stack, prefix, count = [], [], [], 0
    for token in tokens:
        prefix.append(token)
        if token.startswith('<'):
            match = re.match(r'</?([\w-]+)', token)
            if match:
                tag = match.group(1)
                if token.startswith('</'):
                    if stack and stack[-1] == tag:
                        stack.pop()
                elif not token.endswith('/>'):
                    stack.append(tag)
        elif token.strip():
            count += 1
            if count % stride == 0 and count < words:
                frames.append(''.join(prefix) + ''.join('</' + tag + '>' for tag in reversed(stack)))
    return frames + [text]


def button_style(button):
    action = str(button.get('callback_data', '')).lower()
    label = str(button.get('text', '')).casefold()
    if any(word in label for word in ('annuler', 'arrêter', 'supprimer', 'oublier', 'fermer')) or action.startswith(('del:', 'sx:')):
        return 'danger'
    if any(word in label for word in ('terminer', 'importer', 'whatsapp', 'créateur', 'confirmer')):
        return 'success'
    return 'primary'


def style_markup(markup):
    """Only decorate real buttons; retain URLs, callback data and other actions."""
    markup = dict(markup)
    for key in ('inline_keyboard', 'keyboard'):
        if key in markup:
            markup[key] = [
                [dict(button, style=button.get('style') or button_style(button))
                 if isinstance(button, dict) else {'text': button, 'style': button_style({'text': button})}
                 for button in row]
                for row in markup[key]
            ]
    return markup


def format_message(text, parse_mode=None):
    """Preserve rich messages and keep details in a native Telegram quotation."""
    if parse_mode not in (None, 'HTML'):
        return text, parse_mode
    if not text or '<blockquote' in text or '<pre' in text:
        return text, parse_mode
    if parse_mode is None:
        text = html.escape(text)
    title, separator, details = text.partition('\n')
    if '<b>' not in title:
        title = '<b>' + title + '</b>'
    if separator and details.strip():
        expandable = ' expandable' if len(details.splitlines()) > 6 else ''
        text = title + '\n\n<blockquote' + expandable + '>' + details.strip() + '</blockquote>'
    else:
        text = title
    return text, 'HTML'


class PresentedData:
    """Public RequestData properties, preserving multipart attachment objects."""
    def __init__(self, original, parameters):
        self.original = original
        self.parameters = parameters

    @property
    def json_parameters(self):
        return {key: value if isinstance(value, str) else json.dumps(value)
                for key, value in self.parameters.items()}

    @property
    def multipart_data(self):
        return self.original.multipart_data


def present_request(endpoint, request_data):
    if request_data is None:
        return None
    parameters = dict(request_data.parameters)
    if 'reply_markup' in parameters:
        markup = parameters['reply_markup']
        if isinstance(markup, str):
            markup = json.loads(markup)
        if isinstance(markup, dict):
            parameters['reply_markup'] = style_markup(markup)
    # Never change captions, poll options, user text/entities or attachment metadata.
    if endpoint in ('sendMessage', 'editMessageText') and 'text' in parameters and not parameters.get('entities'):
        parameters['text'], mode = format_message(parameters['text'], parameters.get('parse_mode'))
        if mode:
            parameters['parse_mode'] = mode
    return PresentedData(request_data, parameters)


class PresentationRequest(HTTPXRequest):
    async def do_request(self, url, method, request_data=None, **kwargs):
        endpoint = url.rsplit('/', 1)[-1]
        data = present_request(endpoint, request_data)
        if data is None:
            return await super().do_request(url, method, request_data=data, **kwargs)
        final_markup = data.parameters.pop('presentation_final_markup', None)
        parameters = data.parameters
        frames = [parameters.get('text', '')]
        if (endpoint == 'sendMessage' and parameters.get('parse_mode') == 'HTML'
                and not parameters.get('entities') and not parameters.get('business_connection_id')):
            frames = progressive_frames(parameters['text'])
        if len(frames) == 1 and final_markup is None:
            return await super().do_request(url, method, request_data=data, **kwargs)
        initial = dict(parameters, text=frames[0])
        response = await super().do_request(
            url, method, request_data=PresentedData(data, initial), **kwargs
        )
        status, body = response
        result = json.loads(body)
        if status != 200 or not result.get('ok'):
            return response
        message = result.get('result') or {}
        if not isinstance(message, dict) or not message.get('message_id'):
            return response
        markup = final_markup or parameters.get('reply_markup')
        if isinstance(markup, str):
            markup = json.loads(markup)
        # Reply keyboards stay available; only inline keyboards can be attached to edits.
        if not isinstance(markup, dict) or 'inline_keyboard' not in markup:
            markup = None
        elif markup:
            markup = style_markup(markup)
        remaining = frames[1:] or [frames[-1]]
        edit_url = url.rsplit('/', 1)[0] + '/editMessageText'
        for index, frame in enumerate(remaining):
            await asyncio.sleep(0.7)
            edit = {'chat_id': parameters['chat_id'], 'message_id': message['message_id'],
                    'text': frame, 'parse_mode': 'HTML'}
            if markup:
                edit['reply_markup'] = markup
            if 'link_preview_options' in parameters:
                edit['link_preview_options'] = parameters['link_preview_options']
            try:
                edit_status, edit_body = await super().do_request(
                    edit_url, method, request_data=PresentedData(data, edit), **kwargs
                )
                outcome = json.loads(edit_body)
                if edit_status == 200 and outcome.get('ok'):
                    response = (edit_status, edit_body)
                    continue
                # Skip intermediate frames when Telegram throttles edits, then finish in full.
                delay = outcome.get('parameters', {}).get('retry_after')
                if delay:
                    await asyncio.sleep(float(delay))
                if index < len(remaining) - 1 or delay:
                    edit['text'] = frames[-1]
                    final_status, final_body = await super().do_request(
                        edit_url, method, request_data=PresentedData(data, edit), **kwargs
                    )
                    if final_status == 200 and json.loads(final_body).get('ok'):
                        response = (final_status, final_body)
                break
            except Exception:
                logger.warning('Ecriture progressive interrompue', exc_info=True)
                # Recover the complete message even if an intermediate edit timed out.
                edit['text'] = frames[-1]
                try:
                    response_status, response_body = await super().do_request(
                        edit_url, method, request_data=PresentedData(data, edit), **kwargs
                    )
                    if response_status == 200 and json.loads(response_body).get('ok'):
                        response = (response_status, response_body)
                except Exception:
                    logger.warning('Message complet non actualise', exc_info=True)
                break
        return response
