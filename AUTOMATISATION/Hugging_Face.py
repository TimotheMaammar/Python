#!/usr/bin/env python3
import requests, json, re, textwrap
"""Récupération des derniers papiers populaires sur Hugging Face"""

BASE_URL = "https://huggingface.co/papers"

def fetch_papers():
    print("[*] Fetching Hugging Face papers...")
    resp = requests.get(BASE_URL, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (compatible; HF-Scraper/1.0)"
    })
    resp.raise_for_status()

    match = re.search(
        r'data-target="DailyPapers"\s+data-props="([^"]+)"',
        resp.text
    )
    if not match:
        print("[!] Could not find papers")
        return []

    raw = match.group(1)
    raw = raw.replace("&quot;", '"').replace("&amp;", "&").replace("&#39;", "'")

    data = json.loads(raw)
    return data.get("dailyPapers", [])

def format_paper(i, entry):
    paper   = entry.get("paper", {})
    title   = paper.get("title") or entry.get("title", "N/A")
    summary = paper.get("summary") or entry.get("summary", "")
    upvotes = paper.get("upvotes", 0)
    pub_at  = paper.get("publishedAt", "")[:10]  # YYYY-MM-DD
    arxiv_id = paper.get("id", "")
    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
    hf_url    = f"https://huggingface.co/papers/{arxiv_id}" if arxiv_id else ""

    # Résumé tronqué à 500 caractères
    abstract = textwrap.fill(summary[:500].rstrip() + ("…" if len(summary) > 500 else ""),
                             width=78, initial_indent="   ", subsequent_indent="   ")

    lines = [
        f"{i:>2}. {title}",
        f"    Date     : {pub_at}   |   Upvotes : {upvotes}",
        f"    arXiv    : {arxiv_url}",
        f"    Page  : {hf_url}",
        f"    Abstract :",
        abstract,
    ]
    return "\n".join(lines)

def main():
    papers = fetch_papers()
    if not papers:
        return

    papers.sort(key=lambda e: e.get("paper", {}).get("upvotes", 0), reverse=True)

    date_str = papers[0].get("publishedAt", "")[:10] if papers else ""
    print(f"\n{'='*80}")
    print(f"  HuggingFace Daily Papers  —  {date_str}  —  {len(papers)} papiers")
    print(f"{'='*80}\n")

    for i, entry in enumerate(papers, 1):
        print(format_paper(i, entry))
        print()

if __name__ == "__main__":
    main()
