#!/usr/bin/env python3
import requests, re, textwrap
from datetime import datetime
from mistralai import Mistral

# Configuration
API_KEY = "XXX"
SEARCH_URL = "https://arxiv.org/search/cs?query=Abstract&searchtype=all&abstracts=show&order=-announced_date_first&size=50"
MAX_PAPERS = 20

client = Mistral(api_key=API_KEY)

def fetch_arxiv_html():
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
        # Extraction de l'ID arXiv
        id_match = re.search(r'href="https://arxiv\.org/abs/([^"]+)"', block)
        arxiv_id = id_match.group(1) if id_match else "N/A"
        
        # Extraction des catégories
        cats = re.findall(r'data-tooltip="([^"]+)"', block)
        
        # Extraction du titre
        title_match = re.search(
            r'<p class="title is-5 mathjax">\s*(.*?)\s*</p>',
            block, re.DOTALL
        )
        title = re.sub(r'\s+', ' ', title_match.group(1)).strip() if title_match else "N/A"
        
        # Extraction de l'abstract
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
        
        # Extraction de la date
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

def summarize_abstract(title, abstract):
    if not abstract or abstract.strip() == "":
        return "(pas d'abstract trouvé)"
    
    try:
        r = client.chat.complete(
            model="mistral-small-latest",
            messages=[{
                "role": "user",
                "content": f"Résume en quelques phrases ou paragraphes : {title}\n\n{abstract}"
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
    filename = f"arXiv_{date_str}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Fichier TXT sauvegardé: {filename}")
    return filename


def format_paper(index, paper, summary):
    lines = [
        f"{chr(97 + index)}) {paper['title']}",
        f"   Date: {paper['date']} | Catégorie: {paper['cats']}",
        f"   Résumé: {summary}",
        f"   🔗 {paper['url']}"
    ]
    return "\n".join(lines)

def main():
    try:
        date_str = get_date_str()
        
        # Récupération des papiers
        html = fetch_arxiv_html()
        papers = parse_papers(html)
        
        if not papers:
            print("❌ Aucun papier trouvé")
            return
        
        total = len(papers)
        
        # Générer le contenu
        output_lines = []
        output_lines.append("=" * 80)
        output_lines.append(f"  arXiv -- Derniers papiers (avec résumés Mistral) -- {min(MAX_PAPERS, total)} résultats")
        output_lines.append(f"  Généré le {date_str}")
        output_lines.append("=" * 80)
        output_lines.append("")
        
        print(f"\n{'='*80}")
        print(f"  arXiv -- Derniers papiers (avec résumés Mistral) -- {min(MAX_PAPERS, total)} résultats")
        print(f"{'='*80}\n")
        
        # Résumé de chaque papier (limité à MAX_PAPERS)
        for idx, paper in enumerate(papers[:MAX_PAPERS]):
            print(f"[{idx+1}/{min(MAX_PAPERS, total)}] Résumé de '{paper['title'][:50]}...'")
            summary = summarize_abstract(paper['title'], paper['abstract'])
            formatted = format_paper(idx, paper, summary)
            print(formatted)
            print()
            
            # Ajouter au contenu de sortie
            output_lines.append(formatted)
            output_lines.append("")
        
        output_lines.append("=" * 80)
        output_lines.append(f"  ✅ {min(MAX_PAPERS, total)} papiers traités")
        output_lines.append("=" * 80)
        
        # Joindre tout le contenu
        full_content = "\n".join(output_lines)
        
        # Sauvegarder en TXT
        save_to_txt(full_content, date_str)
        
        print(f"\n✨ Résultats sauvegardés dans arXiv_{date_str}.txt")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        raise

if __name__ == "__main__":
    main()
