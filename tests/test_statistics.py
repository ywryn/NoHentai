"""Statistics correctness, invalidation, shared caching and snapshot consistency."""
import json
import subprocess
import sys
from datetime import date
from unittest.mock import patch
import test_backend as fixtures
from backend import db, stats
from backend.validation import merge


class StatisticsTests(fixtures.BackendTests):
    def test_sql_aggregates_match_previous_statistics_and_apply_overrides(self):
        source=[]
        for i in range(1,61):
            source.append(dict(fixtures.GALLERY,gid=i,category='Manga' if i%2 else 'Doujinshi',
                posted=['bad',None,'-1','0','1704067200','1.5'][i%6],
                favTime=f'2026-{(i%12)+1:02d}-{(i%27)+1:02d} 12:34',
                tags=[f'artist:a{i%25}',f'female:f{i%23}',f'male:m{i%3}','other:sample']))
        patches={'1':{'hidden':True},'2':{'category':'Western','tags':[]},'3':{'tags':['artist:manual','female:manual']}}
        dictionary={'data':[{'namespace':'artist','data':{'manual':{'name':'人工标签','intro':'介绍','links':'链接'}}}]}
        with db.connect() as con:
            db.replace_galleries(con,source)
            db.put_resource(con,'overrides',patches)
            db.put_snapshot(con,'translations',dictionary)
        expected=stats.generate(merge(source,patches),dictionary)
        with patch.object(db,'galleries',side_effect=AssertionError('must aggregate in SQL')):
            response=self.client.get('/api/stats')
        self.assertEqual(response.status_code,200,response.text)
        actual=response.json()
        for key in ('stats','tags','quarterly','heatmap'):self.assertEqual(actual[key],expected[key],key)
        self.assertEqual(actual['stats']['total_count'],59)
        self.assertIn('no-store',response.headers['cache-control'])

    def test_cached_statistics_invalidate_on_each_input_revision_but_not_noop_saves(self):
        with patch.object(stats,'aggregate',wraps=stats.aggregate) as aggregate:
            first=self.client.get('/api/stats').json()
            self.assertEqual(self.client.get('/api/stats').json(),first)
            self.assertEqual(self.client.get('/data/stats.json').json(),first)
            self.assertEqual(aggregate.call_count,1)
            with db.connect() as con:db.replace_galleries(con,[fixtures.GALLERY,dict(fixtures.GALLERY,gid=124)])
            updated=self.client.get('/api/stats').json()
            self.assertEqual(updated['stats']['total_count'],2)
            self.assertNotEqual(updated['revision'],first['revision'])
            self.save('overrides',{'123':{'hidden':True}})
            hidden=self.client.get('/api/stats').json()
            self.assertEqual(hidden['stats']['total_count'],1)
            with db.connect() as con:db.put_snapshot(con,'translations',{'data':[{'namespace':'artist','data':{'test':{'name':'新译名'}}}]})
            translated=self.client.get('/api/stats').json()
            self.assertEqual(translated['tags']['artist'][0]['tag_cn'],'新译名')
            record=self.admin('record',kind='gallery',id='123').json()
            self.assertTrue(self.admin('record-save',kind='gallery',id='123',version=record['version'],data=record['data']).json()['unchanged'])
            self.assertEqual(self.client.get('/api/stats').json(),translated)
            self.assertEqual(aggregate.call_count,4)

    def test_parallel_cache_misses_share_one_build_per_process(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier=Barrier(4)
        def request():
            barrier.wait()
            return stats.current()
        with patch.object(stats,'aggregate',wraps=stats.aggregate) as aggregate:
            with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:request(),range(4)))
            self.assertEqual(aggregate.call_count,1)
            self.assertTrue(all(item==results[0] for item in results))

    def test_cache_is_shared_with_another_process(self):
        first=stats.current()
        code="from backend import stats;stats.aggregate=lambda *a:(_ for _ in ()).throw(RuntimeError('cache miss'));print(stats.current()['generatedAt'])"
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout.strip(),first['generatedAt'])

    def test_day_rollover_updates_heatmap_and_cache_retention_is_bounded(self):
        with db.connect() as con:db.replace_galleries(con,[dict(fixtures.GALLERY,favTime='2028-02-29')])
        with patch.object(stats,'utc_today',return_value=date(2028,2,28)):before=stats.current()
        with patch.object(stats,'utc_today',return_value=date(2028,2,29)):after=stats.current()
        self.assertEqual(before['revision'],after['revision'])
        self.assertEqual(before['heatmap']['data'][-1]['d'],'2028-02-28')
        self.assertEqual(after['heatmap']['data'][-1]['d'],'2028-02-29')
        self.assertEqual(after['heatmap']['data'][-1]['v'],1)
        self.assertEqual(len(after['heatmap']['data']),len(before['heatmap']['data'])+1)
        for day in range(1,7):
            with patch.object(stats,'utc_today',return_value=date(2028,3,day)):stats.current()
        with db.connect() as con:
            count=con.execute('SELECT COUNT(*) FROM cache WHERE key LIKE ?',(stats.CACHE_PREFIX+'%',)).fetchone()[0]
        self.assertEqual(count,4)

    def test_aggregation_keeps_the_revision_and_data_in_one_read_snapshot(self):
        with db.connect() as con:revision=db.snapshot(con,'catalog-revision')
        original=stats.aggregate
        def concurrent_update(con,today):
            with db.connect() as writer:db.replace_galleries(writer,[fixtures.GALLERY,dict(fixtures.GALLERY,gid=124)])
            return original(con,today)
        with patch.object(stats,'aggregate',side_effect=concurrent_update):old=stats.current()
        self.assertEqual(old['revision'],revision)
        self.assertEqual(old['stats']['total_count'],1)
        latest=stats.current()
        self.assertNotEqual(latest['revision'],revision)
        self.assertEqual(latest['stats']['total_count'],2)


for name in list(fixtures.BackendTests.__dict__):
    if name.startswith('test_'):setattr(StatisticsTests,name,None)
