import json
import subprocess
import unittest
from backend import catalog, db, settings
import test_backend as fixtures
GALLERY = fixtures.GALLERY


class CatalogTests(fixtures.BackendTests):
    # Reuse database fixture, without rerunning BackendTests' inherited tests.
    def test_sql_search_matches_frontend_and_preserves_overrides(self):
        source = [
            dict(GALLERY, gid=1, title='School romance', uploader='Alice', tags=['female:sole female', 'artist:asanagi']),
            dict(GALLERY, gid=2, title='School WEBTOON', category='Doujinshi', tags=['female:schoolgirl', 'other:webtoon']),
            dict(GALLERY, gid=3, title='日本語', title_jpn='テスト', tags=['male:sole male', 'other:vanilla']),
            dict(GALLERY, gid=4, title='hidden source'),
        ]
        patches = {'4': {'hidden': True}, '3': {'title': 'Edited romance', 'category': 'Misc'}}
        with db.connect() as con:
            db.replace_galleries(con, source)
            db.put_resource(con, 'overrides', patches)
        effective = [dict(g, **patches.get(str(g['gid']), {})) for g in source if not patches.get(str(g['gid']), {}).get('hidden')]
        queries = ['', 'school', 'title:school', 'uploader:ALICE', 'category:doujinshi', 'gid:3',
                   'f:"sole female$"', 'tag:"sole female$"', 'tag:school*', 'f:school%',
                   'school -webtoon', '~romance ~vanilla', 'school,romance', '"sole female"',
                   'f:school* -o:webtoon$', 'a:asanagi', 'title:edited', 'category:misc', 'female:sole_female$',
                   'title:"School romance"', '~school ~テスト -o:webtoon', 'title:school*', 'male:sole',
                   "title:' OR 1=1 --", 'title:😀', 'tag:missing$', '-romance', 'f:sole%$', 'tag:artist:ignored']
        script = '''import { parseQuery, passesQuery, matchGalleryTerm } from './web-static/src/utils/gallerySearch.js';
let text=''; for await (const chunk of process.stdin) text+=chunk;
const {source,queries}=JSON.parse(text);
console.log(JSON.stringify(queries.map(q=>source.filter(g=>passesQuery(g,parseQuery(q),matchGalleryTerm)).map(g=>g.gid))));'''
        expected = json.loads(subprocess.run(['node', '--input-type=module', '-e', script], cwd=settings.ROOT,
            input=json.dumps({'source': effective, 'queries': queries}), text=True, capture_output=True, check=True).stdout)
        for query, ids in zip(queries, expected):
            response = self.client.get('/api/galleries', params={'q': query})
            self.assertEqual(response.status_code, 200, (query, response.text))
            self.assertEqual([i['gid'] for i in response.json()['items']], ids, query)
            self.assertEqual(response.json()['total'], len(ids), query)

    def test_page_payload_is_bounded_counts_and_clamping(self):
        source = [dict(GALLERY, gid=i, category='Manga' if i % 2 else 'Doujinshi', torrents=[{'huge': 'x' * 2000}]) for i in range(1, 76)]
        with db.connect() as con:
            db.replace_galleries(con, source)
        response = self.client.get('/api/galleries').json()
        self.assertEqual(len(response['items']), 30)
        self.assertEqual(response['total'], 75)
        self.assertEqual(response['totalAll'], 75)
        self.assertNotIn('torrents', response['items'][0])
        self.assertNotIn('tags', response['items'][0])
        page2 = self.client.get('/api/galleries', params={'page': 2}).json()
        self.assertEqual(page2['items'][0]['gid'], 31)
        filtered = self.client.get('/api/galleries', params={'types': 'Manga', 'page': 999}).json()
        self.assertEqual(filtered['total'], 38)
        self.assertEqual(filtered['page'], 2)
        self.assertEqual(len(filtered['items']), 8)
        self.assertEqual(filtered['categoryCounts'], {'Manga': 38, 'Doujinshi': 37})
        self.assertEqual(self.client.get('/api/galleries', params={'types': 'unknown'}).json()['total'], 0)
        for params in [{'page': 0}, {'page': 'NaN'}, {'per_page': 999}, {'q': 'x' * 2001}]:
            self.assertEqual(self.client.get('/api/galleries', params=params).status_code, 400)

    def test_tag_labels_suggestions_and_translation_updates(self):
        with db.connect() as con:
            db.put_snapshot(con, 'translations', {'data': [{'namespace': 'artist', 'data': {'test': {'name': '作者'}}}]})
        self.assertEqual(self.client.get('/api/galleries').json()['items'][0]['tagLabels'], ['作者'])
        suggestions = self.client.get('/api/tags/suggestions', params={'token': 'a:te'}).json()['items']
        self.assertEqual(suggestions[0]['value'], 'test')
        self.assertEqual(suggestions[0]['tag_cn'], '作者')
        with db.connect() as con:
            db.put_snapshot(con, 'translations', {'data': [{'namespace': 'artist', 'data': {'test': {'name': '更新'}}}]})
        self.assertEqual(self.client.get('/api/galleries').json()['items'][0]['tagLabels'], ['更新'])
        self.assertEqual(self.client.get('/api/tags/suggestions', params={'token': '-test'}).json()['items'], [])
        self.assertEqual(self.save('overrides', {'123': {'hidden': True}}).status_code, 200)
        self.assertEqual(self.client.get('/api/galleries').json()['total'], 0)

    def test_detail_queries_one_gallery_with_daily_fallback_and_hiding(self):
        response = self.client.get('/api/galleries/123')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['gallery']['gid'], 123)
        self.assertEqual(len(response.json()['tagDetails']), 1)
        with db.connect() as con:
            db.put_snapshot(con, 'daily', [{'galleries': [dict(GALLERY, gid=999, title='daily')]}])
        self.assertEqual(self.client.get('/api/galleries/999').json()['gallery']['title'], 'daily')
        self.assertEqual(self.client.get('/api/galleries/123', params={'source': 'daily'}).status_code, 404)
        self.assertEqual(self.save('overrides', {'123': {'hidden': True}}).status_code, 200)
        self.assertEqual(self.client.get('/api/galleries/123').status_code, 404)
        self.assertEqual(self.client.get('/api/galleries/not-an-id').status_code, 400)

    def test_cached_page_updates_after_source_refresh_and_category_patch(self):
        self.assertEqual(self.client.get('/api/galleries').json()['items'][0]['title'], 'source')
        with db.connect() as con:
            db.replace_galleries(con, [dict(GALLERY, title='refreshed')])
        self.assertEqual(self.client.get('/api/galleries').json()['items'][0]['title'], 'refreshed')
        self.assertEqual(self.save('overrides', {'123': {'category': 'Doujinshi'}}).status_code, 200)
        response = self.client.get('/api/galleries').json()
        self.assertEqual(response['categoryCounts'], {'Doujinshi': 1})
        self.assertEqual(response['items'][0]['category'], 'Doujinshi')


# unittest would otherwise rerun all inherited integration tests for this class.
for name in list(fixtures.BackendTests.__dict__):
    if name.startswith('test_'):
        setattr(CatalogTests, name, None)


if __name__ == '__main__':
    unittest.main()
