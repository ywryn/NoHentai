import unittest
from unittest.mock import patch
from fastapi import HTTPException
from backend import media, translation

HTML = b'''<div id="gdd"><div class="gdt1">Length:</div><div>2 pages</div></div>
<div id="gdt"><a href="https://e-hentai.org/s/abcdef/123-1"><div style="width:100px;height:142px;background:url(https://ehgt.org/sprite.jpg) -100px 0 no-repeat"></div></a></div>
<table class="ptt"><tr><td>1</td><td>2</td></tr></table>'''
PAGE2 = b'''<div id="gdt"><a href="https://e-hentai.org/s/bcdefg/123-2"><img src="https://ehgt.org/thumb.jpg" style="width:90px;height:130px"></a></div>'''


class MediaTests(unittest.TestCase):
    def test_gallery_pagination_and_sprite_contract(self):
        with patch.object(media, 'fetch', side_effect=[(HTML, 'text/html'), (PAGE2, 'text/html')]), \
             patch.object(media.db, 'get_cache', return_value=None), patch.object(media.db, 'set_cache'):
            result = media.gallery_images('123', 'abcdef1234')
        self.assertEqual(result['total'], 2)
        self.assertEqual([i['pageNum'] for i in result['images']], [1, 2])
        self.assertEqual(result['images'][0]['thumbX'], -100)
        self.assertEqual(result['images'][1]['thumbW'], 90)

    def test_denied_gallery_falls_back_and_partial_pages_fail(self):
        with patch.object(media, 'fetch', side_effect=[(b'login', 'text/html'), (HTML, 'text/html'), (PAGE2, 'text/html')]), \
             patch.object(media.db, 'get_cache', return_value=None), patch.object(media.db, 'set_cache'):
            self.assertEqual(media.gallery_images('123', 'abcdef1234')['source'], 'exhentai')
        with patch.object(media, 'fetch', side_effect=[(HTML, 'text/html'), (b'login', 'text/html')]), \
             patch.object(media.db, 'get_cache', return_value=None), patch.object(media.db, 'set_cache') as cache:
            with self.assertRaises(HTTPException):
                media.gallery_images('123', 'abcdef1234')
            cache.assert_not_called()

    def test_image_page_contract_and_dictionary_mapping(self):
        html = b'<img id="img" src="https://ehgt.org/page.jpg"><a id="loadfail" onclick="nl(\'retry\')"></a>'
        with patch.object(media, 'fetch', return_value=(html, 'text/html')), patch.object(media, 'validate_url'), \
             patch.object(media.db, 'get_cache', return_value=None), patch.object(media.db, 'set_cache'):
            self.assertEqual(media.image_url('https://e-hentai.org/s/abcdef/123-1'), {'imageUrl': 'https://ehgt.org/page.jpg', 'nlParam': 'retry'})
        entry = {'slug': 'test', 'japanese': [{'word': '本', 'reading': 'ほん'}], 'is_common': True, 'jlpt': ['jlpt-n5'], 'senses': [{'english_definitions': ['book']}]}
        with patch.object(media, 'json_request', return_value={'data': [entry]}), \
             patch.object(media.db, 'get_cache', return_value=None), patch.object(media.db, 'set_cache'):
            result = media.lookup('本')['results'][0]
        self.assertEqual(result['word'], '本')
        self.assertEqual(result['jlpt'], ['N5'])

    def test_ocr_bounding_boxes_and_provider_parsers(self):
        paddle = translation.parse_paddle({'result': {'ocrResults': [{'prunedResult': {
            'rec_texts': ['日本語'], 'rec_scores': [.99], 'rec_polys': [[[1, 2], [10, 2], [10, 30], [1, 30]]]}}]}})
        self.assertEqual(paddle[0]['bbox'], [1, 2, 10, 30])
        block = {
            'boundingBox': {'vertices': [{'x': 1, 'y': 1}, {'x': 4, 'y': 4}]},
            'paragraphs': [{'words': [{'symbols': [{'text': 'あ'}]}]}],
        }
        data = {'responses': [{'fullTextAnnotation': {'pages': [{'blocks': [block]}]}}]}
        vision = translation.parse_vision(data)
        self.assertEqual(vision[0]['text'], 'あ')
        self.assertEqual(vision[0]['bbox'][2] - vision[0]['bbox'][0], 12)


if __name__ == '__main__':
    unittest.main()
