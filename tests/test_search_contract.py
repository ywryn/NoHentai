"""The same query contract in browser filters and SQL, with scope-specific adapters."""
import json
import subprocess
import unittest
import test_backend as fixtures
from backend import db


class SearchContractTests(unittest.TestCase):
    setUp = fixtures.BackendTests.setUp
    tearDown = fixtures.BackendTests.tearDown
    admin = fixtures.BackendTests.admin

    def test_book_query_matches_browser_adapter_including_overrides_and_unlinked_books(self):
        source=[dict(fixtures.GALLERY,gid=123,title='School romance',uploader='Alice',tags=['female:sole female']),
                dict(fixtures.GALLERY,gid=456,title='WEBTOON',tags=['other:webtoon'])]
        books=[dict(fixtures.BOOK,ID='DUP',sid='123',书名='中文书名',日文名='日本語',备注='note first'),
               dict(fixtures.BOOK,ID='DUP',sid='456',书名='Second book'),
               dict(fixtures.BOOK,ID='00123',sid='',书名='Unlinked book',备注='standalone')]
        patch={'123':{'title':'Edited romance','tags':['female:sole female','artist:asanagi']}}
        with db.connect() as con:
            db.replace_galleries(con,source)
            db.put_resource(con,'printed',books)
            db.put_resource(con,'overrides',patch)
        queries=['','DUP','id:dup','00123','sid:123','name:中文','jpname:日本語','name:second*','-name:second',
                 'f:"sole female$"','a:asanagi','tag:webtoon','title:edited','uploader:alice','gid:456',
                 '~name:中文 ~name:unlinked','note -webtoon','standalone','"unlinked book"',"name:' OR 1=1 --"]
        effective={str(g['gid']):dict(g,**patch.get(str(g['gid']),{})) for g in source}
        script='''import {parseQuery,passesQuery,matchBookTerm,BOOK_FIELDS} from './web-static/src/utils/gallerySearch.js';
let text='';for await(const chunk of process.stdin)text+=chunk;
const {books,effective,queries}=JSON.parse(text);
console.log(JSON.stringify(queries.map(q=>books.filter(b=>passesQuery(b,parseQuery(q,BOOK_FIELDS),(b,t)=>matchBookTerm(b,effective[b.sid],t))).map(b=>b['书名']))));'''
        expected=json.loads(subprocess.run(['node','--input-type=module','-e',script],input=json.dumps({'books':books,'effective':effective,'queries':queries}),text=True,capture_output=True,check=True).stdout)
        for query,titles in zip(queries,expected):
            result=self.admin('records',kind='book',query=query)
            self.assertEqual(result.status_code,200,(query,result.text))
            self.assertEqual([item['data']['书名'] for item in result.json()['items']],titles,query)

    def test_gallery_lookup_is_consistent_in_public_and_admin_scopes(self):
        for query in ('123','https://exhentai.org/g/123/abcdef1234/','https://e-hentai.org/g/123/abcdef1234/?p=2'):
            public=self.client.get('/api/galleries',params={'q':query})
            admin=self.admin('records',kind='gallery',query=query)
            self.assertEqual(public.status_code,200,public.text)
            self.assertEqual([str(g['gid']) for g in public.json()['items']],['123'])
            self.assertEqual([item['id'] for item in admin.json()['items']],['123'])
