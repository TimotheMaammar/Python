"""Parsing of Firefox history + Chrome history (SQLite DBs) and extraction of visited domains.

Firefox: places.sqlite -> moz_places.url
Chrome : History       -> urls.url
The DB is copied to a temporary file first (it is locked while the browser runs) and opened read-only.
"""

import argparse
import csv
import glob
import os
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter
from urllib.parse import urlparse

FIREFOX_QUERY = "SELECT url FROM moz_places WHERE url IS NOT NULL"
CHROME_QUERY = "SELECT url FROM urls WHERE url IS NOT NULL"


def find_firefox_dbs():
    candidates = []
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        roots = [os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox", "Profiles")]
    elif sys.platform == "darwin":
        roots = [os.path.join(home, "Library", "Application Support", "Firefox", "Profiles")]
    else:
        roots = [
            os.path.join(home, ".mozilla", "firefox"),
            os.path.join(home, "snap", "firefox", "common", ".mozilla", "firefox"),
        ]
    for root in roots:
        if root and os.path.isdir(root):
            candidates.extend(glob.glob(os.path.join(root, "*", "places.sqlite")))
    return candidates


def find_chrome_dbs():
    candidates = []
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        roots = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")]
    elif sys.platform == "darwin":
        roots = [os.path.join(home, "Library", "Application Support", "Google", "Chrome")]
    else:
        roots = [
            os.path.join(home, ".config", "google-chrome"),
            os.path.join(home, ".config", "chromium"),
        ]
    for root in roots:
        if root and os.path.isdir(root):
            for profile in ("Default", "Profile *", "Guest Profile"):
                candidates.extend(glob.glob(os.path.join(root, profile, "History")))
    return candidates


def domain_of(url):
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return None
    if not host:
        return None
    if "@" in host:
        host = host.rsplit("@", 1)[1]
    if ":" in host:
        host = host.split(":", 1)[0]
    return host or None


def read_history(db_path, query):
    """Copy the (locked) DB to a temp file and run query read-only."""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(tmp_fd)
    try:
        shutil.copy2(db_path, tmp_path)
        uri = "file:{}?mode=ro".format(tmp_path.replace("?", "%3f"))
        conn = sqlite3.connect(uri, uri=True)
        try:
            return [row[0] for row in conn.execute(query)]
        finally:
            conn.close()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def collect_domains(db_paths, query, label):
    counts = Counter()
    for db_path in db_paths:
        try:
            for url in read_history(db_path, query):
                d = domain_of(url)
                if d:
                    counts[d] += 1
            print("[+] {}: parsed {}".format(label, db_path), file=sys.stderr)
        except (sqlite3.Error, OSError) as e:
            print("[-] {}: failed on {} ({})".format(label, db_path, e), file=sys.stderr)
    return counts


def load_domains(path):
    """Read domains from a txt (one per line) or the CSV (domain,count) produced here."""
    domains = []
    with open(path, "r", encoding="utf-8") as f:
        if path.lower().endswith(".csv"):
            reader = csv.reader(f)
            next(reader, None)  # header
            for row in reader:
                if row:
                    domains.append(row[0].strip())
        else:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    domains.append(line.split("\t")[0].split(",")[0].strip())
    seen, out = set(), []
    for d in domains:
        d = d.lower()
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def add_arguments(p):
    p.add_argument("--browser", choices=["firefox", "chrome", "both"], default="both",
                   help="Which browser history to parse (default: both).")
    p.add_argument("--db", action="append", default=[],
                   help="Explicit path to a history DB. Repeatable.")
    p.add_argument("--counts", action="store_true", help="Show visit counts next to each domain.")
    p.add_argument("--csv", metavar="FILE", help="Write results to a CSV file (domain,count).")
    return p


def run_cli(args):
    total = Counter()
    if args.db:
        for db_path in args.db:
            got = False
            for query, label in ((FIREFOX_QUERY, "firefox"), (CHROME_QUERY, "chrome")):
                try:
                    total.update(collect_domains([db_path], query, label))
                    got = True
                    break
                except sqlite3.Error:
                    continue
            if not got:
                print("[-] Could not read {} as Firefox or Chrome history".format(db_path), file=sys.stderr)
    else:
        if args.browser in ("firefox", "both"):
            dbs = find_firefox_dbs()
            if not dbs:
                print("[-] No Firefox history found.", file=sys.stderr)
            total.update(collect_domains(dbs, FIREFOX_QUERY, "firefox"))
        if args.browser in ("chrome", "both"):
            dbs = find_chrome_dbs()
            if not dbs:
                print("[-] No Chrome history found.", file=sys.stderr)
            total.update(collect_domains(dbs, CHROME_QUERY, "chrome"))

    if not total:
        print("[-] No domains extracted.", file=sys.stderr)
        return 1

    ordered = sorted(total.items(), key=lambda kv: (-kv[1], kv[0]))
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["domain", "count"])
            w.writerows(ordered)
        print("[+] Wrote {} domains to {}".format(len(ordered), args.csv), file=sys.stderr)
    else:
        for domain, count in ordered:
            print("{}\t{}".format(domain, count) if args.counts else domain)
    print("[+] {} unique domains total".format(len(ordered)), file=sys.stderr)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Isolate visited domains from Firefox history and Chrome history.")
    add_arguments(p)
    return run_cli(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
