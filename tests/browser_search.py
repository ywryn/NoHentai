"""Shared search and pagination behavior, using only mocked data and local built assets."""
import re
import threading
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass


def main():
    expect.set_options(timeout=15000)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT/'web-static/dist')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    galleries=[{'gid':i,'title':f'Fixture title {i}','category':'Manga','tags':['female:chinese dress'],'tagLabels':['中国服装'],'thumb':'','filecount':20} for i in range(1,66)]
    galleries[0]['tagLabels']=['汉语','翻译','原创','长标签显示测试','巨乳','已上传','汇编','完整展示']
    books=[{'ID':str(i),'书名':f'Book {i}','日文名':'日本語','sid':str(i),'备注':'','cover':'','收价':'','原价':''} for i in range(1,66)]
    books[0]['书名']='中國服裝'
    options=[{'tag':'female:chinese dress','namespace':'female','value':'chinese dress','tag_cn':'中国服装'},
             {'tag':'female:chinese','namespace':'female','value':'chinese','tag_cn':'中文'}]
    suggestion_requests=[]; queries=[]; pending=[]; hold={'value':False}
    def suggestions(route):
        token=parse_qs(urlsplit(route.request.url).query).get('token',[''])[0]
        suggestion_requests.append(token)
        if hold['value']: pending.append(route)
        else: route.fulfill(json={'items':options})
    def catalog(route):
        params=parse_qs(urlsplit(route.request.url).query);queries.append(params.get('q',[''])[0])
        page=int(params.get('page',['1'])[0])
        route.fulfill(json={'items':galleries[(page-1)*30:page*30],'total':65,'totalAll':65,'page':page,'perPage':30,'categoryCounts':{'Manga':65},'totalCategoryCounts':{'Manga':65}})
    def admin(route):
        body=route.request.post_data_json
        if body['action']=='records':
            if body['kind']=='book':
                rows=[{'id':'a'*32,'version':'v1','data':books[0],'gallery':galleries[0]}]
                route.fulfill(json={'items':rows,'total':1,'page':1,'pages':1})
            else:
                target=body.get('page',1)
                found=galleries[:1] if body.get('query')=='gid:1' else galleries
                rows=[{'id':str(g['gid']),'version':'0','data':{},'source':g,'effective':g} for g in found[(target-1)*30:target*30]]
                route.fulfill(json={'items':rows,'total':len(found),'page':target,'pages':(len(found)+29)//30})
        elif body['action']=='record': route.fulfill(json={'id':'1','version':'0','data':{},'source':galleries[0],'effective':galleries[0]})
        else: raise AssertionError('Unexpected admin operation: '+body['action'])
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(service_workers='block',viewport={'width':1440,'height':1000})
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/api/galleries?*',catalog)
            page.route('**/api/revision',lambda r:r.fulfill(json={'catalog':'v1'}))
            page.route('**/api/books',lambda r:r.fulfill(json={'items':[{'id':str(i),'book':b,'gallery':g} for i,(b,g) in enumerate(zip(books,galleries))],'translations':{'data':[]}}))
            page.route('**/api/daily',lambda r:r.fulfill(json={'groups':[{'name':'fixture','galleries':galleries}],'translations':{'data':[]}}))
            page.route('**/api/tags/suggestions?*',suggestions)
            page.route('**/api/admin/session',lambda r:r.fulfill(json={'session':{'csrf':'fixture'}}))
            page.route('**/api/admin',admin)
            pagination=[]
            for path,label in (('/printed','搜索书单'),('/','搜索画廊'),('/daily','搜索每日画廊')):
                page.goto(base+'/#'+path)
                expect(page.get_by_role('combobox',name=label,exact=True)).to_be_visible()
                expect(page.locator('.pagination-control')).to_have_count(2)
                for bar in page.locator('.pagination-control').all():
                    pagination.append(bar.evaluate("e=>{const s=getComputedStyle(e);return [s.borderBottomWidth,s.paddingTop,s.paddingBottom,s.paddingLeft,s.paddingRight]}"))
                search=page.get_by_role('combobox',name=label,exact=True)
                search.fill('f:chi')
                expect(page.locator('.search-control [role=option]').first).to_be_visible()
                search.press('ArrowUp')
                expect(page.locator('.search-control [role=option]').last).to_have_attribute('aria-selected','true')
                active=search.get_attribute('aria-activedescendant')
                assert page.locator('#'+active).count()==1
                search.press('Escape')
                expect(page.locator('.search-control [role=option]')).to_have_count(0)
                assert search.get_attribute('aria-activedescendant') is None
                search.fill('f:chinese')
                expect(page.locator('.search-control [role=option]').first).to_be_visible()
                search.press('ArrowDown');search.press('Enter')
                expect(search).to_have_value('female:"chinese dress$" ')
                page.get_by_role('button',name='清空'+label,exact=True).click()
                expect(search).to_have_value('')
                print('PASS: shared keyboard, clear and accessibility behavior on '+path)
            assert all(item==pagination[0] for item in pagination),pagination
            assert pagination[0]==['0px','3px','3px','8px','8px'],pagination
            print('PASS: all six pagination bars share spacing and have no divider')

            page.goto(base+'/#/')
            tags=page.locator('.gallery-row').first.locator('.gr-tag')
            expect(tags).to_have_count(8)
            tag_row=page.locator('.gallery-row').first.locator('.gr-tags')
            assert tag_row.get_attribute('title')==' · '.join(galleries[0]['tagLabels'])
            assert tag_row.evaluate('(e)=>getComputedStyle(e).flexWrap')=='nowrap'
            assert tag_row.evaluate('(e)=>getComputedStyle(e).maskImage')!='none'
            assert page.locator('.pagination-control .pag-btn').first.evaluate('(e)=>e.getBoundingClientRect().height')==36
            for width in (320,390,561,767):
                page.set_viewport_size({'width':width,'height':844})
                assert page.locator('.pagination-control .pag-btn').first.evaluate('(e)=>e.getBoundingClientRect().height')==44
                expect(page.locator('.pagination-control').first.get_by_role('button',name='最后一页')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),width
            page.set_viewport_size({'width':1440,'height':1000})
            page.locator('.pagination-control').first.get_by_role('button',name='最后一页').click()
            expect(page).to_have_url(re.compile('page=3'))
            page.locator('.pagination-control').first.get_by_role('button',name='第一页').click()
            expect(page).to_have_url(re.compile('/#/($|\\?)'))
            search=page.get_by_role('combobox',name='搜索画廊',exact=True)
            expect(search).to_be_visible()
            expect(page.locator('.pagination-control')).to_have_count(2)
            baseline=len(queries)
            baseline_suggestions=len(suggestion_requests)
            search.dispatch_event('compositionstart');search.fill('中文')
            page.wait_for_timeout(350)
            assert len(queries)==baseline,(queries,baseline)
            assert len(suggestion_requests)==baseline_suggestions
            search.press('Enter');assert len(queries)==baseline
            search.dispatch_event('compositionend')
            expect(page).to_have_url(re.compile('q='))
            page.wait_for_function("location.hash.includes('q=')")
            assert queries[-1]=='中文'
            print('PASS: IME composition does not submit intermediate input')

            hold['value']=True
            search.fill('first')
            for _ in range(100):
                if len(pending)>=1: break
                page.wait_for_timeout(50)
            search.fill('second')
            for _ in range(100):
                if len(pending)>=2: break
                page.wait_for_timeout(50)
            assert len(pending)==2,len(pending)
            pending[1].fulfill(json={'items':[options[1]]})
            expect(page.locator('.search-control [role=option]')).to_have_count(1)
            pending[0].fulfill(json={'items':[options[0]]})
            page.wait_for_timeout(100)
            expect(page.locator('.search-control [role=option]')).to_contain_text('female:"chinese$"')
            hold['value']=False
            print('PASS: old suggestion responses cannot overwrite the current query')

            page.goto(base+'/#/admin/printed')
            first=page.get_by_role('combobox',name='查找条目',exact=True)
            second=page.get_by_role('combobox',name='关联画廊',exact=True)
            expect(first).to_be_visible();expect(second).to_be_visible()
            assert first.get_attribute('aria-controls')!=second.get_attribute('aria-controls')
            first.fill('f:chi');expect(page.locator('.a-search-row .search-control [role=option]').first).to_be_visible()
            second.focus();expect(page.locator('.a-search-row .search-control [role=option]')).to_have_count(0)
            print('PASS: admin list and association use independent instances of the same component')
            title=page.get_by_role('textbox',name='中文书名',exact=True)
            title.fill('Unsaved draft')
            second.fill('Fixture');second.press('Enter')
            panel=page.locator('.ops-link-panel')
            expect(panel).to_contain_text('共 65 个候选画廊')
            expect(panel.locator('.ops-gallery-matches>button')).to_have_count(30)
            panel.get_by_role('button',name='下一页候选',exact=True).click()
            expect(panel.get_by_role('button',name='关联画廊 31',exact=True)).to_be_visible()
            expect(panel).to_contain_text('第 2 / 3 页')
            expect(title).to_have_value('Unsaved draft')
            second.fill('gid:1');second.press('Enter')
            expect(panel).to_contain_text('共 1 个候选画廊')
            expect(panel).to_contain_text('第 1 / 1 页')
            expect(panel.locator('.ops-match-pagination')).to_have_count(0)
            panel.get_by_role('button',name='关联画廊 1',exact=True).click()
            expect(second).to_have_value('')
            expect(title).to_have_value('Unsaved draft')
            print('PASS: association totals, pagination and query reset preserve unsaved book edits')
            page.get_by_role('button',name='放弃修改',exact=True).click()
            page.goto(base+'/#/printed')
            printed_search=page.get_by_role('combobox',name='搜索书单',exact=True)
            expect(printed_search).to_be_visible()
            printed_search.fill('中国服装');printed_search.press('Enter')
            expect(page.locator('.digi-container a[href*="/gallery/"]')).to_have_count(1)
            page.reload()
            expect(printed_search).to_have_value('中国服装')
            expect(page.locator('.digi-container a[href*="/gallery/"]')).to_have_count(1)
            print('PASS: Printed preserves simplified/traditional matching and URL query on reload')
            page.set_viewport_size({'width':390,'height':844})
            for path,label in (('/','搜索画廊'),('/printed','搜索书单'),('/daily','搜索每日画廊')):
                page.goto(base+'/#'+path)
                expect(page.get_by_role('combobox',name=label,exact=True)).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),path
            print('PASS: shared controls fit mobile layouts on all public pages')
            assert not errors,errors
            browser.close()
    finally:
        server.shutdown();server.server_close()


if __name__=='__main__':main()
