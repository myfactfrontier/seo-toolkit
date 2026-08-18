#!/usr/bin/env python3
"""
gsc_analyzer.py — turn a Google Search Console export into an action list.

GSC tells you what happened. This tells you what to do next.

Three analyses, all driven off the standard GSC "Queries" and "Pages" exports:

  1. STRIKING DISTANCE   Queries ranking 8-20 with real impression volume.
                         These are the cheapest wins on the site — the page
                         already ranks, it just needs a push.

  2. CTR GAP             Queries whose CTR is materially below the expected
                         curve for their position. The ranking is fine; the
                         title and meta description are losing the click.

  3. CANNIBALIZATION     Queries where more than one URL competes. Splits link
                         equity and confuses intent matching. One primary
                         keyword per page — no exceptions.

USAGE
    # Single file (Queries export)
    python gsc_analyzer.py queries.csv

    # With the page-level export for cannibalization detection
    python gsc_analyzer.py queries.csv --pages pages.csv

    # Query+page export (Search Console API or "Pages" tab with query dimension)
    python gsc_analyzer.py combined.csv --out report/

EXPECTED COLUMNS (case-insensitive, GSC's own headers work as-is)
    Top queries | Query        -> query
    Landing page | Page | URL  -> page       (optional)
    Clicks                     -> clicks
    Impressions                -> impressions
    CTR                        -> ctr        (recomputed if missing)
    Position                   -> position

Author: Mohsen Yahya — github.com/myfactfrontier
License: MIT
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Expected CTR by position. Derived from aggregate industry curves; treat as a
# baseline, not gospel. Override with --ctr-curve if you have your own data.
# ---------------------------------------------------------------------------
DEFAULT_CTR_CURVE = {
    1: 0.271, 2: 0.157, 3: 0.110, 4: 0.080, 5: 0.061,
    6: 0.048, 7: 0.039, 8: 0.032, 9: 0.028, 10: 0.025,
    11: 0.022, 12: 0.019, 13: 0.017, 14: 0.015, 15: 0.014,
    16: 0.013, 17: 0.012, 18: 0.011, 19: 0.010, 20: 0.009,
}

COLUMN_ALIASES = {
    "query": {"query", "top queries", "search query", "keyword", "queries"},
    "page": {"page", "landing page", "url", "top pages", "address", "pages"},
    "clicks": {"clicks", "url clicks", "click"},
    "impressions": {"impressions", "impression", "impr", "impr."},
    "ctr": {"ctr", "click through rate", "click-through rate", "site ctr"},
    "position": {"position", "average position", "avg position", "avg. position", "pos"},
}


def _norm(s: str) -> str:
    return s.strip().lower().replace("_", " ")


def _to_float(raw) -> float:
    """GSC exports numbers as '1,234', '3.4%', '1 234' depending on locale."""
    if raw is None:
        return 0.0
    s = str(raw).strip().replace("%", "").replace(",", "").replace(" ", "").replace(" ", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_rows(path: Path) -> list[dict]:
    """Read a GSC export and normalise it to a common schema."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        raw_rows = list(reader)
        headers = reader.fieldnames or []

    if not raw_rows:
        return []

    # Map the file's headers onto our canonical field names.
    mapping: dict[str, str] = {}
    for header in headers:
        key = _norm(header)
        for canonical, aliases in COLUMN_ALIASES.items():
            if key in aliases and canonical not in mapping:
                mapping[canonical] = header
                break

    missing = {"clicks", "impressions", "position"} - mapping.keys()
    if missing:
        sys.exit(
            f"error: {path.name} is missing required column(s): {', '.join(sorted(missing))}\n"
            f"       found headers: {headers}"
        )

    rows = []
    for raw in raw_rows:
        impressions = _to_float(raw.get(mapping["impressions"]))
        clicks = _to_float(raw.get(mapping["clicks"]))
        ctr = _to_float(raw.get(mapping["ctr"])) if "ctr" in mapping else 0.0
        # GSC writes CTR as a percentage; the API writes a 0-1 ratio.
        if ctr > 1:
            ctr /= 100.0
        if not ctr and impressions:
            ctr = clicks / impressions

        rows.append({
            "query": (raw.get(mapping.get("query", ""), "") or "").strip(),
            "page": (raw.get(mapping.get("page", ""), "") or "").strip(),
            "clicks": clicks,
            "impressions": impressions,
            "ctr": ctr,
            "position": _to_float(raw.get(mapping["position"])),
        })
    return rows


def expected_ctr(position: float, curve: dict[int, float]) -> float:
    """Interpolate the expected CTR for a fractional average position."""
    if position < 1:
        return curve.get(1, 0.271)
    lo = math.floor(position)
    hi = math.ceil(position)
    max_pos = max(curve)
    if lo >= max_pos:
        return curve[max_pos]
    lo_ctr = curve.get(lo, curve[max_pos])
    hi_ctr = curve.get(hi, curve[max_pos])
    if lo == hi:
        return lo_ctr
    weight = position - lo
    return lo_ctr + (hi_ctr - lo_ctr) * weight


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------

def striking_distance(rows, min_impressions=100, lo=7.5, hi=20.5):
    """Queries close enough to page one that a focused push pays off."""
    out = []
    for r in rows:
        if not (lo <= r["position"] <= hi):
            continue
        if r["impressions"] < min_impressions:
            continue
        # What we'd earn at position 5 — a realistic, not fantasy, target.
        target = expected_ctr(5, DEFAULT_CTR_CURVE)
        potential = r["impressions"] * target
        out.append({
            **r,
            "potential_clicks": round(potential),
            "clicks_gained": round(potential - r["clicks"]),
        })
    return sorted(out, key=lambda r: r["clicks_gained"], reverse=True)


def ctr_gaps(rows, min_impressions=200, max_position=15.0, threshold=0.5, curve=None):
    """Ranking well, converting badly — a title/meta problem, not a ranking one."""
    curve = curve or DEFAULT_CTR_CURVE
    out = []
    for r in rows:
        if r["impressions"] < min_impressions or r["position"] > max_position:
            continue
        exp = expected_ctr(r["position"], curve)
        if exp <= 0:
            continue
        ratio = r["ctr"] / exp
        if ratio >= threshold:
            continue
        out.append({
            **r,
            "expected_ctr": round(exp, 4),
            "ctr_ratio": round(ratio, 2),
            "clicks_left": round(r["impressions"] * (exp - r["ctr"])),
        })
    return sorted(out, key=lambda r: r["clicks_left"], reverse=True)


def cannibalization(rows, min_impressions=50):
    """One query, several URLs. Pick a winner and redirect or de-optimize the rest."""
    by_query: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["query"] and r["page"] and r["impressions"] >= min_impressions:
            by_query[r["query"].lower()].append(r)

    conflicts = []
    for query, group in by_query.items():
        pages = {r["page"] for r in group}
        if len(pages) < 2:
            continue
        group = sorted(group, key=lambda r: r["clicks"], reverse=True)
        winner = group[0]
        conflicts.append({
            "query": query,
            "url_count": len(pages),
            "total_impressions": round(sum(r["impressions"] for r in group)),
            "total_clicks": round(sum(r["clicks"] for r in group)),
            "primary_page": winner["page"],
            "primary_clicks": round(winner["clicks"]),
            "primary_position": round(winner["position"], 1),
            "competing": [
                {"page": r["page"], "clicks": round(r["clicks"]), "position": round(r["position"], 1)}
                for r in group[1:]
            ],
        })
    return sorted(conflicts, key=lambda c: c["total_impressions"], reverse=True)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _bar(value, peak, width=18):
    if peak <= 0:
        return ""
    return "█" * max(1, round(width * value / peak))


def print_report(rows, sd, gaps, cann, top=15):
    total_clicks = sum(r["clicks"] for r in rows)
    total_impr = sum(r["impressions"] for r in rows)
    site_ctr = (total_clicks / total_impr) if total_impr else 0

    print("\n" + "=" * 78)
    print("  GSC ANALYSIS")
    print("=" * 78)
    print(f"  Rows {len(rows):,}   Clicks {total_clicks:,.0f}   "
          f"Impressions {total_impr:,.0f}   CTR {site_ctr:.2%}")

    print("\n" + "-" * 78)
    print(f"  1. STRIKING DISTANCE  ({len(sd)} queries in positions 8-20)")
    print("-" * 78)
    if not sd:
        print("  Nothing in range. Either you're winning, or volume is too low.")
    else:
        peak = sd[0]["clicks_gained"]
        print(f"  {'QUERY':<40} {'POS':>5} {'IMPR':>9} {'+CLICKS':>8}")
        for r in sd[:top]:
            q = r["query"][:38] or "(no query column)"
            print(f"  {q:<40} {r['position']:>5.1f} {r['impressions']:>9,.0f} "
                  f"{r['clicks_gained']:>8,} {_bar(r['clicks_gained'], peak)}")
        gained = sum(r["clicks_gained"] for r in sd)
        print(f"\n  Total opportunity if each reached position 5: ~{gained:,} clicks/period")

    print("\n" + "-" * 78)
    print(f"  2. CTR GAPS  ({len(gaps)} queries underperforming their position)")
    print("-" * 78)
    if not gaps:
        print("  No material gaps. Titles and descriptions are pulling their weight.")
    else:
        print(f"  {'QUERY':<38} {'POS':>5} {'CTR':>7} {'EXP':>7} {'LOST':>7}")
        for r in gaps[:top]:
            q = r["query"][:36] or "(no query column)"
            print(f"  {q:<38} {r['position']:>5.1f} {r['ctr']:>6.1%} "
                  f"{r['expected_ctr']:>6.1%} {r['clicks_left']:>7,}")
        print("\n  Fix: rewrite title + meta description. Match the query's intent verbatim,")
        print("       lead with the differentiator, and keep the title under 60 characters.")

    print("\n" + "-" * 78)
    print(f"  3. CANNIBALIZATION  ({len(cann)} queries with competing URLs)")
    print("-" * 78)
    if not cann:
        print("  Clean. One primary keyword per page — keep it that way.")
    else:
        for c in cann[:top]:
            print(f"\n  \"{c['query']}\"  —  {c['url_count']} URLs, "
                  f"{c['total_impressions']:,} impr")
            print(f"    KEEP  {c['primary_page'][:66]}")
            print(f"          {c['primary_clicks']:,} clicks @ pos {c['primary_position']}")
            for other in c["competing"][:3]:
                print(f"    FIX   {other['page'][:66]}")
                print(f"          {other['clicks']:,} clicks @ pos {other['position']}")
        print("\n  Fix: pick the page that best matches intent. De-optimize, consolidate,")
        print("       or 301 the rest. Never let two pages target one primary keyword.")
    print("\n" + "=" * 78 + "\n")


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {path}  ({len(rows)} rows)")


def main():
    ap = argparse.ArgumentParser(
        description="Turn a Google Search Console export into an action list.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("csv", type=Path, help="GSC export (queries, pages, or query+page)")
    ap.add_argument("--pages", type=Path, help="Additional page-level export")
    ap.add_argument("--out", type=Path, help="Directory to write CSV reports into")
    ap.add_argument("--min-impressions", type=int, default=100,
                    help="Impression floor for striking distance (default: 100)")
    ap.add_argument("--ctr-threshold", type=float, default=0.5,
                    help="Flag CTR below this fraction of expected (default: 0.5)")
    ap.add_argument("--top", type=int, default=15, help="Rows to print per section")
    args = ap.parse_args()

    if not args.csv.exists():
        sys.exit(f"error: {args.csv} not found")

    rows = load_rows(args.csv)
    if args.pages and args.pages.exists():
        rows += load_rows(args.pages)
    if not rows:
        sys.exit("error: no data rows found")

    sd = striking_distance(rows, min_impressions=args.min_impressions)
    gaps = ctr_gaps(rows, threshold=args.ctr_threshold)
    cann = cannibalization(rows)

    print_report(rows, sd, gaps, cann, top=args.top)

    if args.out:
        print("Writing CSV reports:")
        write_csv(args.out / "striking_distance.csv", sd,
                  ["query", "page", "position", "impressions", "clicks",
                   "ctr", "potential_clicks", "clicks_gained"])
        write_csv(args.out / "ctr_gaps.csv", gaps,
                  ["query", "page", "position", "impressions", "clicks",
                   "ctr", "expected_ctr", "ctr_ratio", "clicks_left"])
        if cann:
            flat = [{
                "query": c["query"],
                "url_count": c["url_count"],
                "total_impressions": c["total_impressions"],
                "primary_page": c["primary_page"],
                "competing_pages": " | ".join(o["page"] for o in c["competing"]),
            } for c in cann]
            write_csv(args.out / "cannibalization.csv", flat,
                      ["query", "url_count", "total_impressions",
                       "primary_page", "competing_pages"])
        print()


if __name__ == "__main__":
    main()
