#!/usr/bin/env python3
"""Publish maintained bilingual wiki articles after a community-source import."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import argparse,html,json,shutil
from bs4 import BeautifulSoup

CATEGORIES_ZH={'Characters':'角色','Game Systems':'游戏系统','Walkthroughs':'流程攻略',
              'Reference':'参考资料','World & Reference':'世界与参考资料','Overview':'概览'}

def apply_editorial_wiki(output:Path,source:Path|None=None)->list[str]:
    source=(source or Path(__file__).resolve().parents[1]).resolve()
    output=output.resolve();maintained=source/'editorial/wiki'
    if not (maintained/'catalog.json').is_file():return []
    catalog=json.loads((maintained/'catalog.json').read_text(encoding='utf-8'))
    pages=catalog['pages'];redirects=catalog.get('redirects',[])
    retired={r['slug'] for r in redirects}
    manifest_path=output/'wiki-manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    original={p['slug']:p for p in manifest['pages']}
    slugs={p['slug'] for p in pages}
    merged=[]
    for entry in pages:
        record=dict(original.get(entry['slug'],{}));record.update(entry);merged.append(record)
    manifest['pages']=[p for p in manifest['pages'] if p['slug'] not in slugs|retired]+merged
    if redirects:
        manifest['redirects']=[r for r in manifest.get('redirects',[]) if r['slug'] not in retired]+redirects
    manifest['editorial_updated_at']=max(p['reviewed_at'] for p in pages)
    (output/'wiki').mkdir(parents=True,exist_ok=True)
    asset_groups={'new-player'}
    for entry in pages:
        slug=entry['slug'];assert slug and all(c.isalnum() or c=='-' for c in slug)
        shutil.copy2(maintained/(slug+'.html.in'),output/'wiki'/(slug+'.html'))
        asset_groups.update(entry.get('asset_directories',[]))
    for entry in redirects:
        slug=entry['slug'];assert slug and all(c.isalnum() or c=='-' for c in slug)
        shutil.copy2(maintained/'redirects'/(slug+'.html.in'),output/'wiki'/(slug+'.html'))
    css=output/'assets/css/wiki-starter.css';css.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(maintained/'wiki-starter.css',css)
    if source!=output:
        for group in asset_groups:
            assert group and all(c.isalnum() or c=='-' for c in group)
            src=source/'assets/images/wiki'/group
            if src.is_dir():shutil.copytree(src,output/'assets/images/wiki'/group,dirs_exist_ok=True)
    for old_slug in ('walkthrough-early-game','walkthrough-quickstart-guide-by-dancave'):
        path=output/'wiki'/(old_slug+'.html')
        if not path.is_file() or old_slug in slugs:continue
        old=BeautifulSoup(path.read_text(encoding='utf-8'),'html.parser')
        if not old.select_one('link[href="../assets/css/wiki-starter.css"]'):
            old.head.append(old.new_tag('link',rel='stylesheet',href='../assets/css/wiki-starter.css'))
        previous=old.select_one('.starter-guide-pointer')
        if previous:previous.decompose()
        pointer=BeautifulSoup('<div class="starter-guide-pointer"><a href="getting-started.html" data-copy-en="New player? Read the updated getting-started guide →" data-copy-zh="第一次玩？先看新版新手入门 →">New player? Read the updated getting-started guide →</a><p data-copy-en="Current controls, recovery, objectives, and saving, with Chinese game screenshots. This community guide remains available below." data-copy-zh="新版介绍当前界面、恢复、目标提示和存档，并配有中文游戏截图。下方保留社区原有攻略。">Current controls, recovery, objectives, and saving, with Chinese game screenshots. This community guide remains available below.</p></div>','html.parser')
        old.select_one('.wiki-article').insert(0,pointer)
        path.write_text(str(old),encoding='utf-8',newline='\n')
    index_path=output/'wiki.html'
    index=BeautifulSoup(index_path.read_text(encoding='utf-8'),'html.parser')
    if not index.select_one('link[href="assets/css/wiki-starter.css"]'):
        index.head.append(index.new_tag('link',rel='stylesheet',href='assets/css/wiki-starter.css'))
    if not index.select_one('.wiki-starter-hero-link'):
        index.select_one('.wiki-library-hero .eyebrow').insert_after(BeautifulSoup('<a class="wiki-starter-hero-link" href="wiki/getting-started.html" data-copy-en="First time playing? Start here →" data-copy-zh="第一次玩？先看新手入门 →">First time playing? Start here →</a>','html.parser'))
    for card in list(index.select('[data-wiki-card]')):
        link=card.select_one('a[href]')
        if link and Path(link['href'].split('?',1)[0]).stem in slugs|retired:card.decompose()
    grid=index.select_one('.wiki-card-grid')
    for entry in reversed(pages):
        esc=lambda v:html.escape(str(v),quote=True)
        category=entry['category']
        terms=entry.get('search_terms',[])
        if entry['slug']=='getting-started':
            terms=terms+['新手','入门','开局','教程','创建角色','属性','地图','时间','恢复','饥饿','吃饭','任务','保存','存档','读档','beginner','save','load']
        search=' '.join([entry['title'],entry['title_en'],entry['title_zh'],entry['summary_en'],entry['summary_zh'],category,CATEGORIES_ZH.get(category,category)]+terms).lower()
        number=entry.get('screenshot_count',entry['image_count'])
        image_en=f'{number} screenshot'+('s' if number!=1 else '')
        image_zh=f'{number} 张实用截图'
        if not number:
            image_en='Character guide' if category=='Characters' else 'Guide'
            image_zh='角色攻略' if category=='Characters' else '玩法指南'
        label_en='New player guide' if entry['slug']=='getting-started' else category
        label_zh='新玩家指南' if entry['slug']=='getting-started' else CATEGORIES_ZH.get(category,category)
        card=BeautifulSoup(f'<article class="wiki-card" data-wiki-card="" data-category="{esc(category)}" data-search="{esc(search)}"><div><span class="wiki-card-category" data-copy-en="{esc(label_en)}" data-copy-zh="{esc(label_zh)}">{esc(label_en)}</span><span class="wiki-card-images" data-copy-en="{esc(image_en)}" data-copy-zh="{esc(image_zh)}">{esc(image_en)}</span></div><h2 data-copy-en="{esc(entry["title_en"])}" data-copy-zh="{esc(entry["title_zh"])}">{esc(entry["title_en"])}</h2><p data-copy-en="{esc(entry["summary_en"])}" data-copy-zh="{esc(entry["summary_zh"])}">{esc(entry["summary_en"])}</p><a href="wiki/{esc(entry["slug"])}.html" data-copy-en="Read guide →" data-copy-zh="阅读攻略 →">Read guide →</a></article>','html.parser')
        grid.insert(0,card)
    previous=index.select_one('#wiki-starter-entry')
    if previous:previous.decompose()
    index.select_one('.wiki-browser').insert_before(BeautifulSoup('<section class="wiki-starter-entry" id="wiki-starter-entry"><div class="container"><div><h2 data-copy-en="New to Chronoromancer?" data-copy-zh="第一次玩？从新手入门开始。">New to Chronoromancer?</h2><p data-copy-en="Learn the interface, find your first objectives, and save your progress—with real Chinese game screenshots." data-copy-zh="从角色创建到第一次存档：看懂界面、找到目标、安排好恢复。配有简体中文游戏截图。">Learn the interface, find your first objectives, and save your progress—with real Chinese game screenshots.</p></div><a href="wiki/getting-started.html" data-copy-en="Read the beginner guide →" data-copy-zh="阅读新手入门 →">Read the beginner guide →</a></div></section>','html.parser'))
    counts=Counter(p['category'] for p in manifest['pages'])
    for button in index.select('[data-wiki-filter]'):
        spans=button.find_all('span',recursive=False)
        if len(spans)>1:spans[-1].string=str(len(manifest['pages']) if button['data-wiki-filter']=='all' else counts[button['data-wiki-filter']])
    total=index.select_one('[data-wiki-result-count]')
    if total:total.string=str(len(manifest['pages']))
    stats=index.select('.guide-library-stats strong')
    if stats:stats[0].string=str(len(manifest['pages']))
    if len(stats)>1:stats[1].string=str(sum(p.get('image_count',0) for p in manifest['pages']))
    index_path.write_text(str(index),encoding='utf-8',newline='\n')
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    path=output/'sitemap.xml'
    if path.is_file():
        text=path.read_text(encoding='utf-8')
        for entry in pages:
            url='https://chronoromancergame.com/wiki/'+entry['slug']+'.html'
            if url not in text:text=text.replace('</urlset>','  <url><loc>'+url+'</loc></url>\n</urlset>')
        path.write_text(text,encoding='utf-8',newline='\n')
    return sorted(slugs)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--source',type=Path)
    a=p.parse_args();print('Maintained guides applied:',', '.join(apply_editorial_wiki(a.output,a.source)))
