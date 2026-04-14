#!/usr/bin/env python3
import requests, re
from datetime import datetime
from mistralai import Mistral

API_KEY = "XXX"
URLS = [
    'https://www.frontiersin.org/articles?query="Artificial%20Intelligence"&sort=Most%20recent',
    'https://www.frontiersin.org/articles?query="Artificial%20Intelligence"&sort=Most%20recent&page=2',
]
MAX_PAPERS = 20

client = Mistral(api_key=API_KEY)

def fetch_papers(urls):
    print("[*] Fetching Frontiers articles...")
    papers = []
    for url in urls:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        blocks = re.findall(r'<article class="CardArticle">.*?</article>', resp.text, re.DOTALL)
        
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
            
            if len(papers) >= MAX_PAPERS:
                break
        
        if len(papers) >= MAX_PAPERS:
            break
    
    return papers[:MAX_PAPERS]

def fetch_article_content(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        abstract_match = re.search(
            r'<section[^>]*class="[^"]*abstract[^"]*"[^>]*>.*?<p>([^<]+)</p>',
            resp.text, re.DOTALL
        )
        if abstract_match:
            return abstract_match.group(1).strip()
        return ""
    except:
        return ""

def summarize_article(title, authors, content=""):
    if not content:
        content = f"Titre: {title}\nAuteurs: {authors}"
    
    try:
        r = client.chat.complete(
            model="mistral-small-latest",
            messages=[{
                "role": "user",
                "content": f"Résume cet article scientifique en plusieurs phrases ou paragraphes : {content[:1000]}"
            }]
        )
        return r.choices[0].message.content
    except Exception as e:
        print(f"  ⚠️ Erreur Mistral: {e}")
        return "(erreur lors du résumé)"

def get_date_str():
    now = datetime.now()
    return now.strftime("%d-%m-%Y")

def save_to_txt(content, date_str):
    filename = f"Frontiers_{date_str}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Fichier sauvegardé: {filename}")
    return filename

def format_paper(index, paper, summary):
    lines = [
        f"  {paper['title']}",
        f"   Auteurs: {paper['authors']}",
        f"   Date: {paper['date']} | Journal: {paper['journal']} > {paper['section']}",
        f"   Résumé: {summary}",
        f"   🔗 {paper['url']}"
    ]
    return "\n".join(lines)

def main():
    try:
        date_str = get_date_str()
        papers = fetch_papers(URLS)
        
        if not papers:
            print("❌ Aucun article trouvé")
            return
        
        total = len(papers)
        
        output_lines = []
        output_lines.append("=" * 80)
        output_lines.append(f"  Frontiers -- {total} résultats")
        output_lines.append(f"  Artificial Intelligence | Généré le {date_str}")
        output_lines.append("=" * 80)
        output_lines.append("")
        
        print(f"\n{'='*80}")
        print(f"  Frontiers -- {total} résultats")
        print(f"{'='*80}\n")
        
        for idx, paper in enumerate(papers):
            print(f"[{idx+1}/{total}] Résumé de '{paper['title'][:50]}...'")
            
            article_content = fetch_article_content(paper['url'])
            summary = summarize_article(paper['title'], paper['authors'], article_content)
            
            formatted = format_paper(idx, paper, summary)
            print(formatted)
            print()
            
            # Ajouter au contenu de sortie
            output_lines.append(formatted)
            output_lines.append("")
        
        output_lines.append("=" * 80)
        output_lines.append(f"  ✅ {total} articles traités")
        output_lines.append("=" * 80)
        
        # Joindre tout le contenu
        full_content = "\n".join(output_lines)
        save_to_txt(full_content, date_str)
        
        print(f"\n✨ Résultats sauvegardés dans Frontiers_{date_str}.txt")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        raise

if __name__ == "__main__":
    main()
