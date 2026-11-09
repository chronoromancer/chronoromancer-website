#!/usr/bin/env python3
"""Publish maintained bilingual wiki articles after a community-source import."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import argparse,html,json,re,shutil
from bs4 import BeautifulSoup

CATEGORIES_ZH={'Characters':'角色','Game Systems':'游戏系统','Walkthroughs':'流程攻略',
              'Reference':'参考资料','World & Reference':'世界与参考资料','Overview':'概览'}

def current_guide_copy(canonical,anchors,guide_directory=False):
    """Keep old addresses current, including incoming section links."""
    doc=BeautifulSoup(canonical.read_text(encoding='utf-8'),'html.parser')
    if guide_directory:
        for node in doc.select('a[href]'):
            value=node['href']
            if re.match(r'^[a-z0-9-]+\.html(?:[?#].*)?$',value):node['href']='../wiki/'+value
    known={node['id']for node in doc.select('[id]')}
    for identifier in anchors:
        if identifier in known:continue
        lang='zh'if identifier.startswith('zh-')else'en'
        panel=doc.select_one('.wiki-source-content[data-lang-panel='+lang+']')
        if not panel:continue
        destination=None
        for pattern,key in [(r'where|location|schedule|地点|位置|时间','location'),(r'quest|route|plot|story|任务|路线|事件','route'),(r'action|service|gift|skill|行动|技能|服务|礼物','activities'),(r'trouble|missing|问题','troubleshooting'),(r'related|相关','related')]:
            if re.search(pattern,identifier,re.I):destination=panel.find(id=lang+'-'+key);break
        destination=destination or panel.find('section')or panel
        marker=doc.new_tag('span',id=identifier,attrs={'class':'wiki-anchor-alias','aria-hidden':'true'})
        destination.insert(0,marker);known.add(identifier)
    return doc

def apply_parallel_guides(output,maintained,pages):
    path=maintained/'parallel-guides.json'
    if not path.is_file():return
    mapping=json.loads(path.read_text(encoding='utf-8'));by_slug={p['slug']:p for p in pages}
    for row in mapping['guides']:
        assert row['wiki_slug']in by_slug
        relative=Path(row['path']);assert len(relative.parts)==2 and relative.parts[0]=='guides'and relative.suffix=='.html'
        doc=current_guide_copy(output/'wiki'/(row['wiki_slug']+'.html'),row['anchors'],True)
        for credit in row.get('credits',[]):
            note=doc.new_tag('p',attrs={'class':'starter-credits'})
            for lang in ('en','zh'):
                span=doc.new_tag('span',attrs={'data-lang-panel':lang,'lang':'zh-CN'if lang=='zh'else'en'})
                if lang=='zh':span['hidden']=''
                span.string=credit[lang];note.append(span)
            doc.select_one('.wiki-article').append(note)
        target=output/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(str(doc),encoding='utf-8',newline='\n')
    library=output/'walkthroughs.html'
    if not library.is_file():return
    index=BeautifulSoup(library.read_text(encoding='utf-8'),'html.parser')
    for row in mapping['guides']:
        card=next((a.find_parent('article')for a in index.find_all('a',href=row['path'])if a.find_parent('article')),None)
        assert card,row['path'];meta=by_slug[row['wiki_slug']]
        for selector,field in [('h3','title'),('p','summary')]:
            node=card.select_one(selector);assert node
            for lang in ('en','zh'):node['data-copy-'+lang]=meta[field+'_'+lang]
            node.string=meta[field+'_en']
        card['data-search']=' '.join([meta['title_en'],meta['title_zh'],meta['summary_en'],meta['summary_zh']]+meta.get('search_terms',[])).lower()
        card['data-translated']='true'
        status=card.select_one('.translation-status')
        if status:
            status['class']=['translation-status','is-ready'];status['data-copy-en']='English / 简体中文';status['data-copy-zh']='中英文攻略';status.string='English / 简体中文'
    stats=index.select('.guide-library-stats strong')
    if len(stats)>1:stats[0].string=stats[1].string=str(len(mapping['guides']))
    for node in index.select('[data-copy-en]'):
        if node['data-copy-en'].startswith('English is the source of truth.'):
            node['data-copy-en']='Read the same current guide in English or Simplified Chinese, with game screenshots and practical instructions.'
            node['data-copy-zh']='中英文使用同一套当前攻略内容，配有游戏截图与实用步骤，可随时切换语言查阅。';node.string=node['data-copy-en']
    library.write_text(str(index),encoding='utf-8',newline='\n')
    data_path=output/'assets/data/walkthroughs.json'
    if data_path.is_file():
        data=json.loads(data_path.read_text(encoding='utf-8'));by_path={r['path']:r for r in mapping['guides']}
        for entry in data['guides']:
            meta=by_slug[by_path[entry['url']]['wiki_slug']]
            entry.update(titleEn=meta['title_en'],titleZh=meta['title_zh'],translated=True,translationState='ready')
        data['translated']=len(data['guides']);data['reviewed_game_version']='v1.0_BETAx'
        data_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def apply_character_index(index,profile_index):
    """Keep character names recognizable and alphabetized in every filter/language."""
    profiles=profile_index.get('profiles',{})
    cards=list(index.select('[data-wiki-card]'))
    characters=[card for card in cards if card.get('data-category')=='Characters']
    def display_name(card):
        heading=card.select_one('h2')
        return heading.get('data-copy-en',heading.get_text(' ',strip=True))
    ordered=iter(sorted(characters,key=lambda card:display_name(card).casefold()))
    arranged=[next(ordered) if card.get('data-category')=='Characters' else card for card in cards]
    for card in characters:
        heading=card.select_one('h2')
        link=card.select_one('a[href]')
        if heading is None or link is None:continue
        slug=Path(link['href'].split('?',1)[0]).stem
        profile=profiles.get(slug)
        if not profile:continue
        wrapper=card.select_one('.wiki-character-heading')
        if wrapper is None:
            wrapper=index.new_tag('a',href=link['href'],attrs={'class':'wiki-character-heading'})
            heading.wrap(wrapper)
        wrapper.name='a';wrapper['href']=link['href']
        for old in wrapper.select('.wiki-character-portrait'):old.decompose()
        image=index.new_tag('img',src=profile['src'],alt='',width='64',height='64',
            attrs={'class':'wiki-character-portrait','loading':'lazy','decoding':'async','aria-hidden':'true'})
        wrapper.insert(0,image)
    grid=index.select_one('.wiki-card-grid')
    for card in cards:card.extract()
    for card in arranged:grid.append(card)

def sync_character_gallery(output, pages, profile_index):
    """Render the main gallery from the same reviewed roster as the player wiki."""
    gallery_path=output/'characters.html'
    if not gallery_path.is_file()or not profile_index or not profile_index.get('gallery_sync'):
        return
    profiles=profile_index['profiles']
    labels={
        'present':{'en':'Present','zh':'现代','ru':'Современность'},
        'medieval':{'en':'Medieval','zh':'中世纪','ru':'Средневековье'},
        'future':{'en':'Future','zh':'未来','ru':'Будущее'}}
    people=sorted([p for p in pages if p['category']=='Characters'],key=lambda p:p['title_en'].casefold())
    assert {p['slug']for p in people}==set(profiles),'Gallery and wiki rosters differ'
    records=[]
    for person in people:
        slug=person['slug'];profile=profiles[slug]
        assert profile['gallery_era']in labels and profile['gallery_id']
        article=BeautifulSoup((output/'wiki'/(slug+'.html')).read_text(encoding='utf-8'),'html.parser')
        portrait=article.select_one('.wiki-source-content[data-lang-panel=en] figure.reviewed-screenshot img')
        assert portrait,(slug,'Missing reviewed portrait')
        source=portrait['src'];assert source.startswith('../assets/images/wiki/'),(slug,source)
        record={'id':profile['gallery_id'],'name':person['title_en'],'era':profile['gallery_era'],
                'descriptionEn':person['summary_en'],'descriptionZh':person['summary_zh'],'image':source[3:],'url':'wiki/'+slug+'.html'}
        if profile.get('gallery_description_ru'):record['descriptionRu']=profile['gallery_description_ru']
        records.append(record)
    assert len(records)==len({r['id']for r in records})==len({r['name']for r in records})
    assert not any(r['id']=='karens'for r in records),'Protected legacy identity cannot be a gallery search term'
    data_path=output/'assets/js/characters-data.js';data_path.parent.mkdir(parents=True,exist_ok=True)
    data_path.write_text('window.CHRONO_CHARACTERS = Object.freeze('+json.dumps(records,ensure_ascii=False,indent=2)+');\n',encoding='utf-8')
    doc=BeautifulSoup(gallery_path.read_text(encoding='utf-8'),'html.parser')
    def copy(tag,en,zh,ru=None):
        tag['data-copy-en']=en;tag['data-copy-zh']=zh;tag.string=en
        if ru is not None:tag['data-copy-ru']=ru
    total=len(records)
    hero=doc.select_one('.page-hero .page-hero-content');assert hero
    intro=hero.find_all('p',recursive=False)[-1]
    copy(intro,
        f'Browse the same {total} character entries as the Player Wiki. Match their game portraits, then search by name or English and Simplified Chinese keywords.',
        f'与玩家Wiki一致的{total}个角色条目。对照游戏头像确认人物，再用姓名或中英文关键词查找。',
        f'Те же {total} записей о персонажах, что и в Wiki. Ищите по имени и описанию.')
    description=doc.select_one('meta[name=description]');assert description
    description['content']=f'Browse all {total} characters from the Chronoromancer Player Wiki with game profile portraits and English and Simplified Chinese summaries.'
    note=doc.select_one('.character-directory-note');assert note
    copy(note,
        'Names, portraits and summaries match the Player Wiki. Era filters use each character’s main setting.',
        '姓名、头像与简介均与玩家Wiki保持一致；时代筛选按主要出场地点分类。',
        'Имена, портреты и описания совпадают с Wiki. Фильтры эпох указывают основное место появления.')
    counts=Counter(r['era']for r in records)
    for element in doc.select('[data-character-count]'):
        era=element['data-character-count'];element.string=str(total if era=='all'else counts[era])
    grid=doc.select_one('[data-character-grid]');assert grid;grid.clear()
    for record in records:
        card=doc.new_tag('article',attrs={'class':'character-card','data-character-card':'','data-era':record['era'],
            'data-search-en':' '.join([record['name'],record['id'],record['era'],record['descriptionEn']]),
            'data-search-zh':' '.join([record['name'],record['descriptionZh']])})
        image=doc.new_tag('img',src=record['image'],alt=record['name'],attrs={'loading':'lazy','decoding':'async'})
        text=doc.new_tag('div');tag=doc.new_tag('span',attrs={'class':'card-tag'})
        copy(tag,labels[record['era']]['en'],labels[record['era']]['zh'],labels[record['era']]['ru'])
        portrait_link=doc.new_tag('a',href=record['url'],attrs={'class':'character-portrait-link'});portrait_link.append(image)
        heading=doc.new_tag('h2');name_link=doc.new_tag('a',href=record['url']);name_link.string=record['name'];heading.append(name_link);summary=doc.new_tag('p')
        copy(summary,record['descriptionEn'],record['descriptionZh'],record.get('descriptionRu'))
        text.append(tag);text.append(heading);text.append(summary);card.append(portrait_link);card.append(text);grid.append(card)
    footer=doc.select_one('.split-feature-copy')
    if footer:
        paragraphs=footer.find_all('p',recursive=False)
        copy(paragraphs[-1],
             'This gallery and the Player Wiki share one reviewed character roster. Names retain their in-game spelling, and the portraits help you recognise each character. Use the Player Wiki for detailed routes, requirements and activities.',
             '这里与玩家Wiki使用同一份角色目录。人物名保留游戏中的拼写，并配有头像，方便对照；详细路线、条件与活动可在玩家Wiki中查阅。',
             'У галереи и Wiki единый проверенный список персонажей. Имена сохранены как в игре; портреты помогают узнать персонажа. Подробные маршруты и условия ищите в Wiki.')
    gallery_path.write_text(str(doc),encoding='utf-8',newline='\n')


def apply_editorial_wiki(output:Path,source:Path|None=None)->list[str]:
    source=(source or Path(__file__).resolve().parents[1]).resolve()
    output=output.resolve();maintained=source/'editorial/wiki'
    if not (maintained/'catalog.json').is_file():return []
    catalog=json.loads((maintained/'catalog.json').read_text(encoding='utf-8'))
    profile_path=maintained/'character-index.json'
    profile_index=json.loads(profile_path.read_text(encoding='utf-8')) if profile_path.is_file() else None
    pages=catalog['pages'];redirects=catalog.get('redirects',[]);aliases=catalog.get('aliases',[])
    excluded=set(catalog.get('excluded_slugs',[]))
    for slug in excluded:
        assert slug and all(c.isalnum()or c=='-'for c in slug)
        (output/'wiki'/(slug+'.html')).unlink(missing_ok=True)
    retired={r['slug'] for r in redirects+aliases}|excluded
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
    if aliases:manifest['aliases']=[{'slug':r['slug'],'target':r['target']}for r in aliases]
    manifest['editorial_updated_at']=max(p['reviewed_at'] for p in pages)
    (output/'wiki').mkdir(parents=True,exist_ok=True)
    asset_groups={'new-player'}
    if profile_index:asset_groups.add(profile_index['asset_directory'])
    for entry in pages:
        slug=entry['slug'];assert slug and all(c.isalnum() or c=='-' for c in slug)
        shutil.copy2(maintained/(slug+'.html.in'),output/'wiki'/(slug+'.html'))
        asset_groups.update(entry.get('asset_directories',[]))
    for entry in redirects:
        slug=entry['slug'];assert slug and all(c.isalnum() or c=='-' for c in slug)
        shutil.copy2(maintained/'redirects'/(slug+'.html.in'),output/'wiki'/(slug+'.html'))
    for entry in aliases:
        assert entry['target']in slugs and entry['slug']not in slugs
        doc=current_guide_copy(output/'wiki'/(entry['target']+'.html'),entry['anchors'])
        (output/'wiki'/(entry['slug']+'.html')).write_text(str(doc),encoding='utf-8',newline='\n')
    apply_parallel_guides(output,maintained,pages)
    css=output/'assets/css/wiki-starter.css';css.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(maintained/'wiki-starter.css',css)
    if profile_index:
        shutil.copy2(maintained/'wiki-character-index.css',output/'assets/css/wiki-character-index.css')
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
    labels={
      'Official mirror of community knowledge':('Chronoromancer Player Wiki','Chronoromancer 玩家攻略'),
      'live articles':('bilingual guides','篇双语指南'),
      'referenced images':('guide images','张指南图片')}
    for node in index.select('[data-copy-en]'):
        if node.get('data-copy-en')in labels:
            en,zh=labels[node['data-copy-en']];node['data-copy-en']=en;node['data-copy-zh']=zh;node.string=en
        elif 'living Chronoromancer wiki' in node.get('data-copy-en',''):
            node['data-copy-en']='Practical, illustrated guides to characters, systems, items, locations and the complete main story—in English and Simplified Chinese.'
            node['data-copy-zh']='角色路线、系统玩法、道具、地点与完整主线，配有实用图解，支持英文与简体中文。';node.string=node['data-copy-en']
    if not index.select_one('link[href="assets/css/wiki-starter.css"]'):
        index.head.append(index.new_tag('link',rel='stylesheet',href='assets/css/wiki-starter.css'))
    if profile_index and not index.select_one('link[href="assets/css/wiki-character-index.css"]'):
        index.head.append(index.new_tag('link',rel='stylesheet',href='assets/css/wiki-character-index.css'))
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
    if profile_index:apply_character_index(index,profile_index)
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
        for slug in excluded:
            url='https://chronoromancergame.com/wiki/'+slug+'.html'
            text=re.sub(r'\s*<url>\s*<loc>'+re.escape(url)+r'</loc>\s*</url>','',text)
        for entry in pages:
            url='https://chronoromancergame.com/wiki/'+entry['slug']+'.html'
            if url not in text:text=text.replace('</urlset>','  <url><loc>'+url+'</loc></url>\n</urlset>')
        path.write_text(text,encoding='utf-8',newline='\n')
    sync_character_gallery(output, pages, profile_index)
    return sorted(slugs)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--source',type=Path)
    a=p.parse_args();print('Maintained guides applied:',', '.join(apply_editorial_wiki(a.output,a.source)))
