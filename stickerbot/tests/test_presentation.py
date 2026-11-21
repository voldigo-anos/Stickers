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


if __name__ == '__main__':
    unittest.main()
