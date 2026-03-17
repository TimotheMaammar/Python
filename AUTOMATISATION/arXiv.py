#!/usr/bin/env python3
import requests, re, textwrap
"""Récupération des derniers papiers de recherche sur arXiv"""

SEARCH_URL = "https://arxiv.org/search/cs?query=Abstract&searchtype=all&abstracts=show&order=-announced_date_first&size=50"

def fetch_html():
    print("[*] Fetching arXiv papers...")
    resp = requests.get(SEARCH_URL, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (compatible; arXiv-Scraper/1.0)"
    })
    resp.raise_for_status()
    return resp.text

def parse_papers(html):
    papers = []
    blocks = re.findall(
        r'<li class="arxiv-result">(.*?)</li>',
        html, re.DOTALL
    )
    for block in blocks:
        id_match = re.search(r'href="https://arxiv\.org/abs/([^"]+)"', block)
        arxiv_id = id_match.group(1) if id_match else "N/A"

        cats = re.findall(r'data-tooltip="([^"]+)"', block)

        title_match = re.search(
            r'<p class="title is-5 mathjax">\s*(.*?)\s*</p>',
            block, re.DOTALL
        )
        title = re.sub(r'\s+', ' ', title_match.group(1)).strip() if title_match else "N/A"

        abstract = ""
        full_match = re.search(
            r'<span class="abstract-full[^"]*"[^>]*>(.*?)</span>',
            block, re.DOTALL
        )
        if full_match:
            abstract = full_match.group(1)
        else:
            short_match = re.search(
                r'<span class="abstract-short[^"]*"[^>]*>(.*?)<a class',
                block, re.DOTALL
            )
            if short_match:
                abstract = short_match.group(1)

        # Nettoyage du HTML
        abstract = re.sub(r'<[^>]+>', '', abstract)
        abstract = re.sub(r'&hellip;', '...', abstract)
        abstract = re.sub(r'&[a-z]+;', ' ', abstract)
        abstract = re.sub(r'\s+', ' ', abstract).strip()

        date_match = re.search(
            r'<span class="has-text-black-bis has-text-weight-semibold">Submitted</span>\s*([^;.<]+)',
            block
        )
        date_str = date_match.group(1).strip() if date_match else "N/A"

        papers.append({
            "id":       arxiv_id,
            "url":      f"https://arxiv.org/abs/{arxiv_id}",
            "title":    title,
            "date":     date_str,
            "cats":     ", ".join(cats) if cats else "N/A",
            "abstract": abstract,
        })
    return papers

def format_paper(i, p):
    abstract_wrapped = textwrap.fill(
        p["abstract"][:320].rstrip() + ("..." if len(p["abstract"]) > 320 else ""),
        width=78, initial_indent="   ", subsequent_indent="   "
    )
    lines = [
        f"{i:>2}. {p['title']}",
        f"    Date     : {p['date']}   |   Categorie : {p['cats']}"
    ]
    lines += [f"    Abstract   :", abstract_wrapped]
    return "\n".join(lines)

def main():
    html   = fetch_html()
    papers = parse_papers(html)
    total  = len(papers)

    print(f"\n{'='*80}")
    print(f"  arXiv -- derniers papiers (triés par date d'annonce) -- {total} resultats")
    print(f"{'='*80}\n")

    for i, p in enumerate(papers, 1):
        print(format_paper(i, p))
        print()

if __name__ == "__main__":
    main()
