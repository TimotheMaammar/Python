#!/usr/bin/env python3
import requests, json, re, textwrap
from datetime import datetime
from mistralai import Mistral

API_KEY = "9py6neQGhqWwjlTYV9vCFuKOxMl6uIc6"
BASE_URL = "https://huggingface.co/papers"
MAX_PAPERS = 20

client = Mistral(api_key=API_KEY)

def fetch_papers():
    print("[*] Fetching HuggingFace papers...")
    resp = requests.get(BASE_URL, timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (compatible; HF-Scraper/1.0)"
    })
    resp.raise_for_status()
    match = re.search(
        r'data-target="DailyPapers"\s+data-props="([^"]+)"',
        resp.text
    )
    if not match:
        print("[!] Could not find data")
        return []
    raw = match.group(1)
    raw = raw.replace("&quot;", '"').replace("&amp;", "&").replace("&#39;", "'")
    data = json.loads(raw)
    return data.get("dailyPapers", [])

def summarize_abstract(title, abstract):
    """Demande à Mistral de résumer l'abstract"""
    if not abstract or abstract.strip() == "":
        return "(pas d'abstract trouvé)"
    
    try:
        r = client.chat.complete(
            model="mistral-small-latest",
            messages=[{
                "role": "user",
                "content": f"Résume cette étude en plusieurs phrases ou paragraphes : {title}\n\n{abstract}"
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
    filename = f"HuggingFace_{date_str}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Fichier sauvegardé: {filename}")
    return filename

def format_paper(index, entry, summary):
    paper = entry.get("paper", {})
    title = paper.get("title") or entry.get("title", "N/A")
    upvotes = paper.get("upvotes", 0)
    pub_at = paper.get("publishedAt", "")[:10]  # YYYY-MM-DD
    arxiv_id = paper.get("id", "")
    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
    hf_url = f"https://huggingface.co/papers/{arxiv_id}" if arxiv_id else ""
    
    lines = [
        f"{chr(97 + index)}) {title}",
        f"   Date: {pub_at} | Upvotes: {upvotes}",
        f"   Résumé: {summary}",
        f"   arXiv: {arxiv_url}",
        f"   HF Page: {hf_url}"
    ]
    return "\n".join(lines)

def main():
    try:
        date_str = get_date_str()
        
        # Récupération des papiers
        papers = fetch_papers()
        
        if not papers:
            print("❌ Aucun papier trouvé")
            return
        
        # Tri par upvotes (décroissant)
        papers.sort(key=lambda e: e.get("paper", {}).get("upvotes", 0), reverse=True)
        
        total = len(papers)
        papers_to_process = min(MAX_PAPERS, total)
        
        # Générer le contenu
        output_lines = []
        output_lines.append("=" * 80)
        output_lines.append(f"  HuggingFace daily dapers")
        output_lines.append(f"  Généré le {date_str}")
        output_lines.append("=" * 80)
        output_lines.append("")
        
        print(f"\n{'='*80}")
        print(f"  HuggingFace daily papers")
        print(f"{'='*80}\n")
        
        # Résumé de chaque papier
        for idx, entry in enumerate(papers[:MAX_PAPERS]):
            paper = entry.get("paper", {})
            full_abstract = paper.get("summary") or entry.get("summary", "")
            title = paper.get("title") or entry.get("title", "N/A")
            
            print(f"[{idx+1}/{papers_to_process}] Résumé de '{title[:50]}...'")
            summary = summarize_abstract(title, full_abstract)
            formatted = format_paper(idx, entry, summary)
            print(formatted)
            print()
            
            # Ajouter au contenu de sortie
            output_lines.append(formatted)
            output_lines.append("")
        
        output_lines.append("=" * 80)
        output_lines.append(f"  ✅ {papers_to_process} papiers traités")
        output_lines.append("=" * 80)
        
        # Joindre tout le contenu
        full_content = "\n".join(output_lines)
        
        # Sauvegarder
        save_to_txt(full_content, date_str)
        
        print(f"\n✨ Résultats sauvegardés dans HuggingFace_{date_str}.txt")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        raise

if __name__ == "__main__":
    main()
