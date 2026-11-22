"""Regression checks for preserving Telegram actions and upload metadata."""
import asyncio
import json
import os
import sys
import unittest
from urllib.parse import parse_qs

import httpx
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from presentation import PresentationRequest, present_request, style_markup


class RequestFixture:
    def __init__(self, parameters, files=None):
        self.parameters = parameters
        self.multipart_data = files or {}


class PresentationIntegrityTests(unittest.TestCase):
    def test_callbacks_urls_and_keyboard_text_are_preserved(self):
        original = {'inline_keyboard': [[{'text': 'Supprimer', 'callback_data': 'del:pack_by_bot'},
                                        {'text': 'Voir', 'url': 'https://t.me/addstickers/pack_by_bot'}]]}
        result = style_markup(original)
        self.assertEqual(result['inline_keyboard'][0][0]['callback_data'], 'del:pack_by_bot')
        self.assertEqual(result['inline_keyboard'][0][1]['url'], 'https://t.me/addstickers/pack_by_bot')
        self.assertNotIn('style', original['inline_keyboard'][0][0])

    def test_media_attachments_and_captions_unchanged(self):
        files = {'photo': ('photo.png', b'png-bytes', 'image/png')}
        source = RequestFixture({'chat_id': 42, 'caption': 'Photo <3', 'photo': 'attach://photo'}, files)
        output = present_request('sendPhoto', source)
        self.assertIs(output.multipart_data, files)
        self.assertEqual(output.parameters, source.parameters)

    def test_explicit_entities_not_shifted(self):
        entities = [{'type': 'bold', 'offset': 0, 'length': 5}]
        output = present_request('sendMessage', RequestFixture({'text': 'Hello world', 'entities': entities}))
        self.assertEqual(output.parameters['text'], 'Hello world')
        self.assertEqual(output.parameters['entities'], entities)

    def test_non_message_text_not_changed(self):
        parameters = {'text': 'Stickers', 'show_alert': False, 'callback_query_id': '123'}
        self.assertEqual(present_request('answerCallbackQuery', RequestFixture(parameters)).parameters, parameters)

    def test_real_http_request_keeps_action_payload(self):
        async def flow():
            requests = []
            async def respond(request):
                data = parse_qs(request.content.decode())
                requests.append(data)
                return httpx.Response(200, json={'ok': True, 'result': True})
            request = PresentationRequest(httpx_kwargs={'transport': httpx.MockTransport(respond)})
            await request.initialize()
            try:
                status, _ = await request.do_request(
                    'https://api.telegram.org/botTEST/sendMessage', 'POST',
                    request_data=RequestFixture({'chat_id': 42, 'text': 'Menu\nDetails', 'parse_mode': 'HTML',
                    'reply_markup': {'inline_keyboard': [[{'text': 'Voir', 'callback_data': 'use:pack'}]]}}))
                self.assertEqual(status, 200)
                self.assertEqual(requests[0]['chat_id'], ['42'])
                self.assertEqual(json.loads(requests[0]['reply_markup'][0])['inline_keyboard'][0][0]['callback_data'], 'use:pack')
            finally:
                await request.shutdown()
        asyncio.run(flow())

    def test_reply_keyboard_message_still_fully_revealed(self):
        async def flow():
            sent = []
            async def respond(request):
                data = parse_qs(request.content.decode())
                sent.append((request.url.path.rsplit('/', 1)[-1], data))
                if request.url.path.endswith('editMessageText') and 'reply_markup' in data:
                    return httpx.Response(400, json={'ok': False, 'description': "message can't be edited"})
                return httpx.Response(200, json={'ok': True, 'result': {'message_id': 7}})
            request = PresentationRequest(httpx_kwargs={'transport': httpx.MockTransport(respond)})
            await request.initialize()
            text = '<b>Bienvenue</b>\n<blockquote>un deux trois quatre cinq six</blockquote>'
            keyboard = {'keyboard': [[{'text': 'Menu'}]], 'resize_keyboard': True}
            try:
                for _ in range(2):
                    await request.do_request('https://api.telegram.org/botTEST/sendMessage', 'POST',
                        request_data=RequestFixture({'chat_id': 42, 'text': text, 'parse_mode': 'HTML', 'reply_markup': keyboard}))
            finally:
                await request.shutdown()
            last = [d for e, d in sent if e == 'editMessageText'][-1]
            self.assertEqual(last['text'], [text])
            self.assertGreater(len(sent), 3)
        import presentation
        original = presentation.asyncio.sleep
        async def no_wait(_): pass
        presentation.asyncio.sleep = no_wait
        try:
            asyncio.run(flow())
        finally:
            presentation.asyncio.sleep = original


if __name__ == '__main__':
    unittest.main()
