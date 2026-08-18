#!/usr/bin/env python3
"""
internal_link_audit.py — see where your internal authority actually flows.

Crawls a site from its sitemap (or a seed URL), builds the internal link graph,
runs PageRank over it, and reports:

  * ORPHANS         Pages in the sitemap that nothing links to. They exist, they
                    just don't inherit any authority.
  * AUTHORITY SINKS High-PageRank pages that link out to almost nothing. Their
                    equity dead-ends instead of feeding money pages.
  * UNDER-LINKED    Deep pages with few inbound internal links relative to their
                    crawl depth — the fix list for internal-link engineering.
  * DEPTH           Click depth from the homepage. Anything past 3 is a problem.

Authority should be directed, not left to accumulate in pagination and tag pages.

USAGE
    python internal_link_audit.py https://example.com/sitemap.xml
    python internal_link_audit.py https://example.com --crawl --max-pages 300
    python internal_link_audit.py https://example.com/sitemap.xml --out report.csv

REQUIREMENTS
    pip install requests beautifulsoup4

Be a good citizen: this respects a delay between requests and identifies itself.
Do not point it at sites you do not own or have permission to crawl.

Author: Mohsen Yahya — github.com/myfactfrontier
License: MIT
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("error: pip install requests beautifulsoup4")

UA = "Mozilla/5.0 (compatible; internal-link-audit/1.0; +https://github.com/myfactfrontier/seo-toolkit)"
SKIP_EXT = re.compile(r"\.(jpe?g|png|gif|webp|avif|svg|ico|css|js|pdf|zip|mp4|webm|woff2?|ttf)(\?|$)", re.I)


def normalize(url: str) -> str:
    """Strip fragments and trailing slashes so one page is one node."""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    netloc = parsed.netloc.lower()
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{netloc}{path}{query}"


def same_host(a: str, b: str) -> bool:
    ha = urlparse(a).netloc.lower().removeprefix("www.")
    hb = urlparse(b).netloc.lower().removeprefix("www.")
    return ha == hb


def fetch(session, url, timeout=15):
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True)
        return r if r.status_code == 200 else None
    except requests.RequestException:
        return None


def read_sitemap(session, url, seen=None, depth=0) -> list[str]:
    """Read a sitemap or sitemap index, recursing into nested indexes once."""
    seen = seen if seen is not None else set()
    if url in seen or depth > 3:
        return []
    seen.add(url)

    resp = fetch(session, url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.content, "xml")
    urls = []

    # Sitemap index -> recurse
    for loc in soup.select("sitemap > loc"):
        urls += read_sitemap(session, loc.get_text(strip=True), seen, depth + 1)

    # URL set
    for loc in soup.select("url > loc"):
        urls.append(normalize(loc.get_text(strip=True)))

    return urls


def crawl(session, urls, root, delay=0.4, max_pages=500, verbose=True):
    """Fetch each URL and record its internal outlinks. Returns (graph, meta)."""
    graph: dict[str, set[str]] = {}
    meta: dict[str, dict] = {}
    queue = deque(urls[:max_pages])
    known = set(queue)

    processed = 0
    while queue and processed < max_pages:
        url = queue.popleft()
        processed += 1
        if verbose:
            print(f"  [{processed:>4}/{min(len(known), max_pages)}] {url[:78]}", flush=True)

        resp = fetch(session, url)
        if not resp:
            graph[url] = set()
            meta[url] = {"status": "error", "title": "", "words": 0}
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()

        title = soup.title.get_text(strip=True) if soup.title else ""
        body = soup.get_text(" ", strip=True)

        outlinks = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            target = normalize(urljoin(url, href))
            if not same_host(target, root) or SKIP_EXT.search(target):
                continue
            if target != url:
                outlinks.add(target)
                if target not in known and len(known) < max_pages * 2:
                    known.add(target)

        graph[url] = outlinks
        meta[url] = {
            "status": "ok",
            "title": title,
            "words": len(body.split()),
            "nofollow": sum(1 for a in soup.find_all("a", rel=True)
                            if "nofollow" in " ".join(a.get("rel", []))),
        }
        time.sleep(delay)

    return graph, meta


def pagerank(graph, damping=0.85, iterations=40, tol=1e-7):
    nodes = set(graph) | {t for targets in graph.values() for t in targets}
    n = len(nodes)
    if n == 0:
        return {}
    rank = {node: 1.0 / n for node in nodes}
    inbound = defaultdict(set)
    for src, targets in graph.items():
        for t in targets:
            inbound[t].add(src)
    outdeg = {src: len(targets) for src, targets in graph.items()}
    dangling = [node for node in nodes if outdeg.get(node, 0) == 0]

    for _ in range(iterations):
        leaked = damping * sum(rank[node] for node in dangling) / n
        new = {}
        for node in nodes:
            total = sum(rank[src] / outdeg[src] for src in inbound[node] if outdeg.get(src))
            new[node] = (1 - damping) / n + damping * total + leaked
        delta = sum(abs(new[node] - rank[node]) for node in nodes)
        rank = new
        if delta < tol:
            break
    return rank


def compute_depth(graph, root):
    home = normalize(root)
    depth = {home: 0}
    queue = deque([home])
    while queue:
        node = queue.popleft()
        for target in graph.get(node, ()):
            if target not in depth:
                depth[target] = depth[node] + 1
                queue.append(target)
    return depth


def main():
    ap = argparse.ArgumentParser(description="Audit internal link structure and authority flow.")
    ap.add_argument("target", help="Sitemap URL or site root")
    ap.add_argument("--crawl", action="store_true",
                    help="Discover URLs by crawling instead of reading a sitemap")
    ap.add_argument("--max-pages", type=int, default=300)
    ap.add_argument("--delay", type=float, default=0.4, help="Seconds between requests")
    ap.add_argument("--out", type=Path, help="Write the full table to CSV")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = UA

    root = f"{urlparse(args.target).scheme}://{urlparse(args.target).netloc}"

    if args.crawl or not args.target.rstrip("/").endswith(".xml"):
        seeds = [normalize(args.target if not args.crawl else root)]
        print(f"Crawling from {seeds[0]} (max {args.max_pages} pages)\n")
    else:
        print(f"Reading sitemap: {args.target}")
        seeds = read_sitemap(session, args.target)
        if not seeds:
            sys.exit("error: no URLs found in sitemap")
        print(f"Found {len(seeds)} URLs. Crawling up to {args.max_pages}.\n")

    graph, meta = crawl(session, seeds, root, delay=args.delay,
                        max_pages=args.max_pages, verbose=not args.quiet)

    rank = pagerank(graph)
    depth = compute_depth(graph, root)
    inbound = defaultdict(int)
    for targets in graph.values():
        for t in targets:
            inbound[t] += 1

    crawled = sorted(graph, key=lambda u: rank.get(u, 0), reverse=True)
    sitemap_set = set(seeds)

    print("\n" + "=" * 78)
    print("  INTERNAL LINK AUDIT")
    print("=" * 78)
    print(f"  Pages crawled {len(graph)}   Edges "
          f"{sum(len(v) for v in graph.values())}   "
          f"Avg outlinks {sum(len(v) for v in graph.values())/max(len(graph),1):.1f}")

    orphans = [u for u in sitemap_set if inbound.get(u, 0) == 0 and u != normalize(root)]
    print("\n" + "-" * 78)
    print(f"  ORPHAN PAGES  ({len(orphans)})")
    print("-" * 78)
    if not orphans:
        print("  None. Every page in the sitemap has at least one internal link.")
    for u in orphans[:20]:
        print(f"  {u[:74]}")
    if orphans:
        print("\n  Fix: link these from a relevant hub page. A page nothing links to")
        print("       inherits no authority, however good the content is.")

    sinks = [(u, rank[u], len(graph[u])) for u in crawled[:40] if len(graph[u]) <= 3]
    print("\n" + "-" * 78)
    print(f"  AUTHORITY SINKS  ({len(sinks)} high-rank pages with <=3 outlinks)")
    print("-" * 78)
    if not sinks:
        print("  None. High-authority pages are passing equity onward.")
    for u, r, out in sinks[:12]:
        print(f"  PR {r:.5f}  out:{out:>2}  {u[:60]}")
    if sinks:
        print("\n  Fix: add contextual links from these to the revenue pages you")
        print("       actually want ranking. This is the cheapest authority you have.")

    deep = [(u, depth[u], inbound.get(u, 0)) for u in crawled
            if depth.get(u, 99) >= 4]
    deep.sort(key=lambda x: -x[1])
    print("\n" + "-" * 78)
    print(f"  DEEP PAGES  ({len(deep)} at click depth 4+)")
    print("-" * 78)
    if not deep:
        print("  Clean. Everything reachable within three clicks of the homepage.")
    for u, d, inb in deep[:15]:
        print(f"  depth {d}  in:{inb:>3}  {u[:60]}")
    if deep:
        print("\n  Fix: flatten the architecture or add hub-page links. Crawl budget and")
        print("       authority both decay with depth.")

    print("\n" + "-" * 78)
    print("  TOP PAGES BY INTERNAL PAGERANK")
    print("-" * 78)
    print(f"  {'PR':>9}  {'IN':>4} {'OUT':>4} {'D':>2}  URL")
    for u in crawled[:15]:
        print(f"  {rank.get(u,0):>9.5f}  {inbound.get(u,0):>4} "
              f"{len(graph[u]):>4} {depth.get(u,'-'):>2}  {u[:52]}")
    print("\n" + "=" * 78 + "\n")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["url", "pagerank", "inbound_links", "outbound_links",
                        "click_depth", "words", "title", "in_sitemap"])
            for u in crawled:
                m = meta.get(u, {})
                w.writerow([u, f"{rank.get(u,0):.8f}", inbound.get(u, 0),
                            len(graph[u]), depth.get(u, ""), m.get("words", ""),
                            m.get("title", ""), u in sitemap_set])
        print(f"wrote {args.out}\n")


if __name__ == "__main__":
    main()
