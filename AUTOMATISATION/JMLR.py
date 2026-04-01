#!/usr/bin/env python3

import requests, re
"""Récupération des derniers papiers de recherche sur JMLR"""

BASE_URL="https://jmlr.org/papers"

def main():
    print("[*] Fetching JMLR papers...")
    resp = requests.get(BASE_URL, timeout=10)

    # <a href="vXYZ"><font class="volume">Volume XYZ</font></a>
    match = re.search(r'<a href="v(\d+)">', resp.text)
    if not match:
        print("[!] Could not find volume")
        return

    volume = match.group(1)
    url = f"{BASE_URL}/v{volume}/"
    print(f"[+] Latest: Volume {volume}")

    print(f"[*] Fetching {url}")
    resp = requests.get(url, timeout=10)

    # <dt>Title</dt>...<a href="/papers/volumeXYZ/XX-YYYY/XX-YYYY.pdf">pdf</a>
    papers = re.findall(
        r'<dt>([^<]+)</dt>.*?<a[^>]*href=[\'"]([^\'"]*?\.pdf)[\'"]',
        resp.text,
        re.DOTALL
    )

    print(f"\n{'='*80}")
    print(f"Volume {volume} - {len(papers)} papers")
    print(f"{'='*80}\n")

    for i, (title, link) in enumerate(papers[-10:], 1):
        print(f"{i}. {title.strip()}")
        print(f"https://jmlr.org{link}\n")

if __name__ == "__main__":
    main()
