#!/usr/bin/env python3
import requests, re
from mistralai import Mistral

API_KEY = "XXX"
client  = Mistral(api_key=API_KEY)

def fetch_hf(url):
    resp = requests.get(url, timeout=10)
    title_m    = re.search(r'<h1[^>]*>([^<]+)</h1>', resp.text)
    abstract_m = re.search(r'<p class="text-gray-600">(.*?)</p>', resp.text, re.DOTALL)
    
    abstract = ""
    if abstract_m:
        abstract = re.sub(r'<!--.*?-->', '', abstract_m.group(1), flags=re.DOTALL)
        abstract = re.sub(r'<[^>]+>', '', abstract)
        abstract = re.sub(r'\s+', ' ', abstract).strip()

    return {
        "title"   : title_m.group(1).strip() if title_m else url,
        "abstract": abstract,
        "url"     : url
    }

def summarize(title, abstract):
    if not abstract:
        return "Pas d'abstract trouvé"
    r = client.chat.complete(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": f"Résume en 3 phrases : {title}\n\n{abstract}"}]
    )
    return r.choices[0].message.content

def main():
    with open("papers.txt") as f:
        urls = [l.split("Page  :")[-1].strip() for l in f if "Page  :" in l]

    for url in urls:
        p = fetch_hf(url)
        print(f"\n• {p['title']}")
        print(f"  {summarize(p['title'], p['abstract'])}")
        print(f"  {p['url']}")

    # Ligne à utiliser pour vider le fichier après utilisation : 
    # open("papers.txt", "w").close()


if __name__ == "__main__":
    main()
