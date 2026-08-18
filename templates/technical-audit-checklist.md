# Technical SEO Audit Checklist

The order matters. Crawlability gates indexation, indexation gates ranking,
ranking gates everything else. Fixing content on a page Google can't crawl is
wasted work.

---

## 1. Crawlability — can the bot reach it?

- [ ] `robots.txt` — no blanket disallows on JS/CSS; sitemap declared
- [ ] Server response times under 600ms TTFB at p75
- [ ] No crawl traps: infinite pagination, faceted-navigation URL explosion, session IDs
- [ ] Internal links use `<a href>` — not JS `onclick` handlers
- [ ] Log-file analysis: what is Googlebot actually spending crawl budget on?
- [ ] Redirect chains ≤ 1 hop; no redirect loops
- [ ] 4xx/5xx audit on internally-linked URLs

## 2. Indexation — is the right set of pages in the index?

- [ ] `site:` count vs. sitemap count vs. GSC "Indexed" count — reconcile the three
- [ ] Canonical tags: self-referencing on canonical pages, correct target elsewhere
- [ ] No conflicting signals (canonical to A + noindex on A)
- [ ] Thin/duplicate pages: tags, archives, filters — noindex or consolidate
- [ ] Pagination handled with self-canonical + proper internal linking
- [ ] XML sitemap: only indexable 200-status canonical URLs, under 50k per file
- [ ] `lastmod` reflects real content changes, not build timestamps

## 3. Rendering — does Google see what users see?

- [ ] Compare rendered HTML vs. raw HTML for critical content
- [ ] URL Inspection "Live test" on templates, not just one page
- [ ] Critical content and internal links present in server-rendered HTML
- [ ] No client-side-only routing for indexable pages
- [ ] Lazy-loaded content above the fold is not lazy-loaded

## 4. Core Web Vitals — field data, not lab data

- [ ] LCP ≤ 2.5s at p75 (CrUX, not Lighthouse)
- [ ] INP ≤ 200ms at p75
- [ ] CLS ≤ 0.1 at p75
- [ ] LCP element identified per template — is it an image, a font, or a hydration block?
- [ ] `fetchpriority="high"` on the LCP image; preload the LCP resource
- [ ] `font-display: swap` + subset fonts; self-host where possible
- [ ] Explicit `width`/`height` on all images to reserve layout space

## 5. Structured data — connected, not scattered

- [ ] `@graph` with `@id` cross-references, not isolated objects
- [ ] Organization + WebSite on every page
- [ ] Page-type schema matches page intent (Article / Product / LocalBusiness / FAQ)
- [ ] BreadcrumbList matches the visible breadcrumb
- [ ] Validated in Rich Results Test **and** Schema.org validator
- [ ] No schema for content not visible on the page

## 6. International & local

- [ ] `hreflang` reciprocal on every variant, including `x-default`
- [ ] Language/region codes valid (`ar-SA`, not `ar-KSA`)
- [ ] hreflang points to canonical URLs only
- [ ] Google Business Profile: categories, hours, service areas, photos current
- [ ] NAP consistency across site, GBP, and major citations

## 7. AI search readiness (GEO / AEO)

- [ ] Answer-first structure: the direct answer within the first 2 sentences under each H2
- [ ] Atomic, quotable blocks — extractable without surrounding context
- [ ] Entity coverage matches the topic's semantic neighborhood
- [ ] Author and organization E-E-A-T signals present and marked up
- [ ] Content accessible to AI crawlers (check `robots.txt` for GPTBot, PerplexityBot, ClaudeBot,
      Google-Extended — decide deliberately whether to allow, don't block by accident)
- [ ] Citation footprint tracked: which pages get cited, for which prompts

## 8. Architecture

- [ ] Click depth ≤ 3 for revenue pages
- [ ] One primary keyword per page — no two pages targeting the same term
- [ ] Hub-and-spoke clusters with descriptive, varied anchor text
- [ ] Internal PageRank flowing to money pages, not pagination and tags
- [ ] Orphan pages: zero

---

## Prioritization

Score each finding and work top-down. Effort is a tiebreaker, never the driver.

| Impact | Meaning |
|---|---|
| **Critical** | Blocks indexation or crawling of revenue pages |
| **High** | Measurably suppresses ranking or CTR on commercial terms |
| **Medium** | Degrades efficiency or user experience |
| **Low** | Hygiene — fix in the next sprint |
