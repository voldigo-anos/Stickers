"""Telegram-native presentation applied at the outgoing request boundary."""
import html
import json

from telegram.request import HTTPXRequest


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
        return await super().do_request(
            url, method, request_data=present_request(endpoint, request_data), **kwargs
        )
