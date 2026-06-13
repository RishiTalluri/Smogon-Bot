
import time, json, csv, re, random
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL="https://www.smogon.com/forums/"
USER_AGENT="UltimateCrawler/5.0"

DELAY_MIN=0.2
DELAY_MAX=0.5
MAX_WORKERS=5

TXT_FILE="smogon_full_text.txt"
JSON_FILE="smogon_threads.json"
CSV_FILE="smogon_threads.csv"

FORUMS=[
{"name":"SV","url":"https://www.smogon.com/forums/forums/smogon-metagames.725/"},
{"name":"Old Gen","url":"https://www.smogon.com/forums/forums/ruins-of-alph.31/"},
]

seen_forums=set()
seen_threads=set()

def build_session():
    s=requests.Session()
    s.headers.update({"User-Agent":USER_AGENT})
    return s

def polite_get(session,url):
    time.sleep(random.uniform(DELAY_MIN,DELAY_MAX))
    try:
        r=session.get(url,timeout=15)
        if r.status_code==200:
            return r
    except:
        return None
    return None

def extract_subforums(html):
    soup=BeautifulSoup(html,"html.parser")
    subs=[]
    for node in soup.select(".node.node--forum"):
        a=node.select_one(".node-title a")
        if not a:
            continue
        name=a.get_text(strip=True)
        url=urljoin(BASE_URL,a.get("href",""))
        subs.append({"name":name,"url":url})
    return subs

def parse_thread_list(html,forum):
    soup=BeautifulSoup(html,"html.parser")
    threads=[]
    for item in soup.select(".structItem--thread"):
        title_el=item.select_one(".structItem-title a[data-tp-primary]")
        if not title_el:
            continue

        title=title_el.get_text(strip=True)
        href=title_el.get("href","")

        if "/threads/" not in href:
            continue

        url=urljoin(BASE_URL,href)

        if url in seen_threads:
            continue
        seen_threads.add(url)

        threads.append({
            "title":title,
            "url":url,
            "forum":forum,
            "op_text":""
        })
    return threads

def fetch_pokepaste(session,url):
    r=polite_get(session,url)
    if not r:
        return ""
    soup=BeautifulSoup(r.text,"html.parser")
    pre=soup.select_one("pre")
    if not pre:
        return ""
    return pre.get_text("\n",strip=True)[:2000]

def parse_posts(html,session):
    soup=BeautifulSoup(html,"html.parser")
    posts=soup.select(".message--post")
    texts=[]

    for post in posts:
        content=post.select_one(".bbWrapper")
        if not content:
            continue

        for q in content.select(".bbCodeBlock--quote"):
            q.decompose()

        text=content.get_text(" ",strip=True)

        imgs=[]
        for img in content.select("img"):
            src=img.get("src","")
            if src:
                imgs.append(src.split("/")[-1])
        if imgs:
            text+="\n[IMAGES: "+", ".join(imgs)+"]"

        pokes=[]
        for a in content.select("a"):
            href=a.get("href","")
            if "pokepast.es" in href:
                ptxt=fetch_pokepaste(session,href)
                if ptxt:
                    pokes.append(ptxt)
        if pokes:
            text+="\n[POKEPASTE]\n"+"\n\n".join(pokes)

        text=re.sub(r"\s+"," ",text)

        if text:
            texts.append(text)

    return texts

def get_all_pages(session,url):
    pages=[url]
    r=polite_get(session,url)
    if not r:
        return pages

    soup=BeautifulSoup(r.text,"html.parser")
    last=soup.select_one(".pageNav-page--last")

    if last:
        try:
            total=int(last.get_text())
            for i in range(2,total+1):
                pages.append(f"{url}page-{i}")
        except:
            pass

    return pages

def append_txt(thread):
    if not thread["op_text"].strip():
        return
    with open(TXT_FILE,"a",encoding="utf-8") as f:
        f.write(f"\n=== {thread['title']} ===\n")
        f.write(thread["op_text"]+"\n")

def fetch_thread(session,thread,i,total):
    pages=get_all_pages(session,thread["url"])
    all_text=[]

    for p in pages:
        r=polite_get(session,p)
        if not r:
            continue

        posts=parse_posts(r.text,session)
        for idx,txt in enumerate(posts,1):
            all_text.append(f"POST {idx}:\n{txt}")

    thread["op_text"]="\n\n".join(all_text)

    append_txt(thread)
    print(f"[{i}/{total}] {thread['title'][:60]}")

    return thread

def crawl_forum_recursive(session,name,url,all_threads):
    if url in seen_forums:
        return
    seen_forums.add(url)

    print(f"\nVisiting: {name}")

    r=polite_get(session,url)
    if not r:
        return

    html=r.text

    threads=parse_thread_list(html,name)
    print(f"Threads: {len(threads)}")
    all_threads.extend(threads)

    subforums=extract_subforums(html)
    print(f"Subforums: {len(subforums)}")

    for sub in subforums:
        crawl_forum_recursive(session,sub["name"],sub["url"],all_threads)

def save_all(data):
    with open(JSON_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2,ensure_ascii=False)

    with open(CSV_FILE,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["title","forum","url","op_text"])
        w.writeheader()
        w.writerows(data)

def crawl():
    session=build_session()
    all_threads=[]

    for forum in FORUMS:
        crawl_forum_recursive(session,forum["name"],forum["url"],all_threads)

    total=len(all_threads)
    print(f"\nTotal threads: {total}\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures=[ex.submit(fetch_thread,session,t,i,total) for i,t in enumerate(all_threads,1)]
        for _ in as_completed(futures):
            pass

    save_all(all_threads)
    print("\nDONE")

def main():
    open(TXT_FILE,"w").close()
    start=datetime.now()
    crawl()
    print("Time:",(datetime.now()-start).seconds,"sec")

if __name__=="__main__":
    main()