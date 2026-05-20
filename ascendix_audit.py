import requests
import xml.etree.ElementTree as ET
import time
import sys
from datetime import date

SITEMAP_INDEX_URL = "https://ascendix.com/sitemap_index.xml"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
DELAY = 1  # seconds between requests


def fetch_xml(url):
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (audit-bot)"})
        resp.raise_for_status()
        return ET.fromstring(resp.content)
    except requests.HTTPError as e:
        print(f"HTTP error fetching {url}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None


def get_child_sitemap_urls(index_root):
    urls = []
    for loc in index_root.findall(".//sm:sitemap/sm:loc", NS):
        urls.append(loc.text.strip())
    return urls


def parse_urlset(root):
    entries = []
    for url_el in root.findall("sm:url", NS):
        loc = url_el.find("sm:loc", NS)
        lastmod = url_el.find("sm:lastmod", NS)
        if loc is None:
            continue
        url = loc.text.strip()
        mod = lastmod.text.strip() if lastmod is not None else None
        entries.append((url, mod))
    return entries


def classify(url):
    if "/blog/" in url:
        return "blog"
    if "/cases/" in url:
        return "cases"
    return "pages"


def sort_key(entry):
    _, mod = entry
    if mod is None:
        return "9999-99-99"
    return mod


def build_table(title, entries):
    rows = ""
    for url, mod in entries:
        display_mod = mod if mod else "unknown"
        rows += f"    <tr><td><a href=\"{url}\" target=\"_blank\">{url}</a></td><td>{display_mod}</td></tr>\n"
    return f"""
<h2>{title} ({len(entries)})</h2>
<table>
  <thead>
    <tr><th>URL</th><th>Last Modified Date</th></tr>
  </thead>
  <tbody>
{rows}  </tbody>
</table>
"""


def main():
    print("Fetching sitemap index...")
    index_root = fetch_xml(SITEMAP_INDEX_URL)
    if index_root is None:
        print("Failed to fetch sitemap index. Exiting.", file=sys.stderr)
        sys.exit(1)

    child_urls = get_child_sitemap_urls(index_root)
    print(f"Found {len(child_urls)} child sitemaps.")

    all_entries = []
    for child_url in child_urls:
        print(f"  Fetching: {child_url}")
        time.sleep(DELAY)
        child_root = fetch_xml(child_url)
        if child_root is None:
            continue
        entries = parse_urlset(child_root)
        print(f"    → {len(entries)} URLs")
        all_entries.extend(entries)

    # Filter out category/author URLs
    filtered = [(url, mod) for url, mod in all_entries
                if "category" not in url and "author" not in url]
    print(f"Total URLs after filtering: {len(filtered)}")

    blog, cases, pages = [], [], []
    for entry in filtered:
        t = classify(entry[0])
        if t == "blog":
            blog.append(entry)
        elif t == "cases":
            cases.append(entry)
        else:
            pages.append(entry)

    # Sort oldest → newest; unknown last
    blog.sort(key=sort_key)
    cases.sort(key=sort_key)
    pages.sort(key=sort_key)

    today = date.today().isoformat()
    filename = f"ascendix_audit_{today}.html"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ascendix Site Audit — {today}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2em; color: #222; }}
    h1 {{ color: #1a3c6e; }}
    h2 {{ color: #2c5f9e; margin-top: 2em; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 0.5em; }}
    th {{ background: #2c5f9e; color: #fff; padding: 8px 12px; text-align: left; }}
    td {{ padding: 6px 12px; border-bottom: 1px solid #ddd; word-break: break-all; }}
    tr:nth-child(even) td {{ background: #f4f7fc; }}
    a {{ color: #2c5f9e; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .summary {{ background: #eef2fa; padding: 1em 1.5em; border-radius: 6px; margin-bottom: 1em; }}
  </style>
</head>
<body>
  <h1>Ascendix Site Audit</h1>
  <div class="summary">
    <strong>Generated:</strong> {today}<br>
    <strong>Blog posts:</strong> {len(blog)} &nbsp;|&nbsp;
    <strong>Cases:</strong> {len(cases)} &nbsp;|&nbsp;
    <strong>Pages:</strong> {len(pages)} &nbsp;|&nbsp;
    <strong>Total:</strong> {len(blog) + len(cases) + len(pages)}
  </div>
{build_table("Blog Posts", blog)}
{build_table("Cases", cases)}
{build_table("Pages", pages)}
</body>
</html>
"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report saved: {filename}")


if __name__ == "__main__":
    main()
