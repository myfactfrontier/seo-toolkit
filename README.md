# SEO Toolkit

Scripts and templates I actually use on client work — technical SEO, GEO/AEO,
and organic growth across MENA.

No dependencies you don't need, no dashboards, no signup. Point them at your
own data and read the output.

> Built by [Mohsen Yahya](https://github.com/myfactfrontier) — Senior SEO Specialist & Team Lead.
> [Portfolio](https://myfactfrontier.github.io) · [Case studies](https://github.com/myfactfrontier/seo-case-studies)

---

## Scripts

### `gsc_analyzer.py` — Search Console export → action list

GSC tells you what happened. This tells you what to do next.

```bash
python scripts/gsc_analyzer.py queries.csv
python scripts/gsc_analyzer.py queries.csv --pages pages.csv --out report/
```

Three analyses, no dependencies beyond the standard library:

| Analysis | What it finds | Why it matters |
|---|---|---|
| **Striking distance** | Queries in positions 8–20 with real impression volume | The page already ranks. It just needs a push — cheapest wins on the site. |
| **CTR gaps** | Queries converting well below the expected curve for their position | The ranking is fine. The title and meta description are losing the click. |
| **Cannibalization** | Queries where two or more URLs compete | Splits link equity, confuses intent matching. One primary keyword per page. |

Sample output:

```
  1. STRIKING DISTANCE  (8 queries in positions 8-20)
  QUERY                             POS      IMPR  +CLICKS
  clinic moving                     9.4    38,900    1,961 ██████████████████
  restaurant moving                10.2    29,400    1,475 ██████████████

  Total opportunity if each reached position 5: ~8,068 clicks/period

  3. CANNIBALIZATION  (2 queries with competing URLs)
  "restaurant moving"  —  2 URLs, 38,500 impr
    KEEP  https://example.com/restaurant-moving   318 clicks @ pos 10.2
    FIX   https://example.com/blog/guide           44 clicks @ pos 17.3
```

Accepts GSC's own export headers as-is, in any locale. Handles `1,234`, `3.4%`,
and API-style 0–1 ratios without configuration.

---

### `schema_generator.py` — interconnected JSON-LD, not isolated blobs

Most generators emit one disconnected object per page. Search engines build a
graph. This emits an `@graph` where Organization, WebSite, WebPage, Article,
BreadcrumbList and FAQPage all reference each other by `@id` — which is what
actually earns rich results and AI-engine citations.

```bash
python scripts/schema_generator.py article \
  --site https://example.com --org "Example Co" \
  --url https://example.com/blog/guide \
  --headline "The Complete Guide" \
  --description "Everything you need to know." \
  --image https://example.com/img/guide.jpg \
  --author "Mohsen Yahya" --published 2026-01-15 \
  --breadcrumb "Home=/" "Blog=/blog/" "Guide=/blog/guide" \
  --faq "What is it?=A guide." "How long?=Ten minutes." \
  --tag
```

Types: `article`, `product`, `localbusiness`, `faq`, `howto`.
Add `--tag` to wrap it in a `<script>` element ready to paste.

---

### `internal_link_audit.py` — where your authority actually flows

Crawls from your sitemap, builds the internal link graph, runs PageRank over it.

```bash
pip install requests beautifulsoup4
python scripts/internal_link_audit.py https://example.com/sitemap.xml --out links.csv
```

Reports:

- **Orphans** — sitemap pages nothing links to. They inherit no authority, however good the content.
- **Authority sinks** — high-PageRank pages linking out to almost nothing. Equity dead-ends instead of feeding money pages.
- **Deep pages** — click depth 4+ from the homepage. Crawl budget and authority both decay with depth.
- **Internal PageRank ranking** — which pages your own architecture is actually promoting.

Respects a configurable delay and identifies itself in the User-Agent.
Only point it at sites you own or have permission to crawl.

---

## Templates

| File | Use |
|---|---|
| [`templates/technical-audit-checklist.md`](templates/technical-audit-checklist.md) | Full technical audit, ordered by dependency: crawlability → indexation → rendering → CWV → schema → international → AI readiness → architecture |
| [`templates/content-brief.md`](templates/content-brief.md) | Entity-first content brief. Map the entity graph before the outline — coverage is what earns topical authority, not word count |

---

## Method notes

A few principles these tools encode, in case they're useful on their own:

**One primary keyword per page, never reused.** Cannibalization is the most
common self-inflicted wound in SEO. Two pages targeting one term means neither
ranks properly and link equity splits between them.

**Fix in dependency order.** Crawlability gates indexation, indexation gates
ranking. Rewriting content on a page Google can't crawl is wasted work.

**Answer-first structure wins AI citations.** AI Overviews and answer engines
extract self-contained blocks. A paragraph that needs the preceding three
paragraphs for context will not be quoted.

**Field data over lab data for Core Web Vitals.** Lighthouse is a diagnostic.
CrUX is the scoreboard.

---

## Requirements

- Python 3.9+
- `gsc_analyzer.py` and `schema_generator.py` — standard library only
- `internal_link_audit.py` — `requests`, `beautifulsoup4`, `lxml`

```bash
pip install -r requirements.txt
```

## License

MIT — use them, fork them, ship them.
