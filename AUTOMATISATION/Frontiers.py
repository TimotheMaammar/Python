#!/usr/bin/env python3
import requests, re

URLS = [
    'https://www.frontiersin.org/articles?query="Artificial%20Intelligence"&sort=Most%20recent',
    'https://www.frontiersin.org/articles?query="Artificial%20Intelligence"&sort=Most%20recent&page=2',
]
MAX_PAPERS = 40

def fetch(url):
    resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    blocks = re.findall(r'<article class="CardArticle">.*?</article>', resp.text, re.DOTALL)
    papers = []
    for block in blocks:
        title_m   = re.search(r'href="([^"]+)"[^>]*class="CardArticle__wrapper"', block)
        type_m    = re.search(r'<p class="CardArticle__type">([^<]+)</p>', block)
        date_m    = re.search(r'<p class="CardArticle__date">\s*([^<]+?)\s*</p>', block)
        h2_m      = re.search(r'<h2 class="CardArticle__title">([^<]+)</h2>', block)
        section_m = re.search(r'<span>([^<]+)</span>', block)
        journal_m = re.search(r'<div class="CardArticle__journal__name">([^<]+)</div>', block)
        authors   = re.findall(r'<li>([^<]+)</li>', block)

        if not h2_m:
            continue
        papers.append({
            "title"  : h2_m.group(1).strip(),
            "url"    : title_m.group(1)          if title_m   else "?",
            "type"   : type_m.group(1).strip()   if type_m    else "?",
            "date"   : date_m.group(1).strip()   if date_m    else "?",
            "section": section_m.group(1).strip()if section_m else "?",
            "journal": journal_m.group(1).strip()if journal_m else "?",
            "authors": ", ".join(authors)         if authors   else "?",
        })
    return papers

def main():
    papers = []
    for url in URLS:
        papers += fetch(url)
        if len(papers) >= MAX_PAPERS:
            break
    papers = papers[:MAX_PAPERS]

    print(f"\n{'='*80}")
    print(f"Frontiers — {len(papers)} derniers articles (Artificial Intelligence)")
    print(f"{'='*80}\n")
    for i, p in enumerate(papers, 1):
        print(f"{i}. [{p['type']}] {p['title']}")
        print(f"   {p['authors']}")
        print(f"   {p['date']} | {p['journal']} > {p['section']}")
        print(f"   {p['url']}\n")

if __name__ == "__main__":
    main()
