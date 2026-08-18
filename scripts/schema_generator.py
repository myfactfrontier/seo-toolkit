#!/usr/bin/env python3
"""
schema_generator.py — build interconnected JSON-LD, not isolated blobs.

Most schema generators emit one disconnected object per page. Search engines
build a graph. This emits an @graph where every node references the others by
@id, so Organization, WebSite, WebPage, Article, Breadcrumb and FAQ all resolve
to a single connected entity — which is what actually earns rich results and
AI-engine citations.

USAGE
    # Article + breadcrumb + FAQ, fully wired
    python schema_generator.py article \\
        --site https://example.com \\
        --org "Example Co" \\
        --url https://example.com/blog/guide \\
        --headline "The Complete Guide" \\
        --description "Everything you need to know." \\
        --image https://example.com/img/guide.jpg \\
        --author "Mohsen Yahya" \\
        --published 2026-01-15 \\
        --breadcrumb "Home=/" "Blog=/blog/" "Guide=/blog/guide" \\
        --faq "What is it?=A guide." "How long?=Ten minutes."

    # Local business
    python schema_generator.py localbusiness \\
        --site https://example.com --org "Example Co" \\
        --phone "+201111793633" --street "12 Nile St" \\
        --city Cairo --country EG --lat 30.0444 --lng 31.2357

    # Product
    python schema_generator.py product \\
        --site https://example.com --org "Example Co" \\
        --url https://example.com/p/chair --headline "Office Chair" \\
        --description "Ergonomic mesh chair." --price 1299 --currency SAR

    # Wrap in a <script> tag ready to paste
    python schema_generator.py article ... --tag

Author: Mohsen Yahya — github.com/myfactfrontier
License: MIT
"""

from __future__ import annotations

import argparse
import json
import sys


def _id(site: str, fragment: str) -> str:
    return f"{site.rstrip('/')}/#{fragment}"


def _pairs(items, flag):
    """Parse 'Key=Value' arguments, tolerating '=' inside the value."""
    out = []
    for item in items or []:
        if "=" not in item:
            sys.exit(f"error: {flag} expects 'Key=Value', got: {item!r}")
        key, value = item.split("=", 1)
        out.append((key.strip(), value.strip()))
    return out


def organization(site, org, logo=None, sameas=None, phone=None, address=None):
    node = {
        "@type": "Organization",
        "@id": _id(site, "organization"),
        "name": org,
        "url": site.rstrip("/") + "/",
    }
    if logo:
        node["logo"] = {"@type": "ImageObject", "@id": _id(site, "logo"), "url": logo}
        node["image"] = {"@id": _id(site, "logo")}
    if sameas:
        node["sameAs"] = sameas
    if phone:
        node["contactPoint"] = {
            "@type": "ContactPoint", "telephone": phone, "contactType": "customer service"
        }
    if address:
        node["address"] = address
    return node


def website(site, org):
    return {
        "@type": "WebSite",
        "@id": _id(site, "website"),
        "url": site.rstrip("/") + "/",
        "name": org,
        "publisher": {"@id": _id(site, "organization")},
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": site.rstrip("/") + "/?s={search_term_string}",
            },
            "query-input": "required name=search_term_string",
        },
    }


def webpage(site, url, name, description, image=None, breadcrumb=False):
    node = {
        "@type": "WebPage",
        "@id": f"{url}#webpage",
        "url": url,
        "name": name,
        "isPartOf": {"@id": _id(site, "website")},
        "about": {"@id": _id(site, "organization")},
    }
    if description:
        node["description"] = description
    if image:
        node["primaryImageOfPage"] = {"@id": f"{url}#primaryimage"}
    if breadcrumb:
        node["breadcrumb"] = {"@id": f"{url}#breadcrumb"}
    return node


def image_object(url, image_url, caption=None):
    node = {
        "@type": "ImageObject",
        "@id": f"{url}#primaryimage",
        "url": image_url,
        "contentUrl": image_url,
    }
    if caption:
        node["caption"] = caption
    return node


def breadcrumb_list(site, url, crumbs):
    items = []
    for i, (name, path) in enumerate(crumbs, start=1):
        item_url = path if path.startswith("http") else site.rstrip("/") + "/" + path.lstrip("/")
        items.append({
            "@type": "ListItem",
            "position": i,
            "name": name,
            "item": item_url,
        })
    return {"@type": "BreadcrumbList", "@id": f"{url}#breadcrumb", "itemListElement": items}


def article(site, url, headline, description, author, published, modified=None, image=None):
    node = {
        "@type": "Article",
        "@id": f"{url}#article",
        "headline": headline[:110],
        "isPartOf": {"@id": f"{url}#webpage"},
        "mainEntityOfPage": {"@id": f"{url}#webpage"},
        "publisher": {"@id": _id(site, "organization")},
        "author": {"@type": "Person", "@id": f"{site.rstrip('/')}/#/schema/person/{author.lower().replace(' ', '-')}",
                   "name": author},
        "datePublished": published,
        "dateModified": modified or published,
    }
    if description:
        node["description"] = description
    if image:
        node["image"] = {"@id": f"{url}#primaryimage"}
    return node


def faq_page(url, qa_pairs):
    return {
        "@type": "FAQPage",
        "@id": f"{url}#faq",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in qa_pairs
        ],
    }


def how_to(url, name, steps):
    return {
        "@type": "HowTo",
        "@id": f"{url}#howto",
        "name": name,
        "step": [
            {"@type": "HowToStep", "position": i, "name": n, "text": t}
            for i, (n, t) in enumerate(steps, start=1)
        ],
    }


def local_business(site, org, phone, street, city, region, postal, country,
                   lat=None, lng=None, hours=None, price_range=None):
    node = {
        "@type": "LocalBusiness",
        "@id": _id(site, "localbusiness"),
        "name": org,
        "url": site.rstrip("/") + "/",
        "telephone": phone,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": street,
            "addressLocality": city,
            "addressRegion": region,
            "postalCode": postal,
            "addressCountry": country,
        },
        "parentOrganization": {"@id": _id(site, "organization")},
    }
    if lat is not None and lng is not None:
        node["geo"] = {"@type": "GeoCoordinates", "latitude": lat, "longitude": lng}
    if price_range:
        node["priceRange"] = price_range
    if hours:
        node["openingHoursSpecification"] = [
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": days.split("|"),
                "opens": opens,
                "closes": closes,
            }
            for days, opens, closes in hours
        ]
    return node


def product(site, url, name, description, price, currency, image=None,
            sku=None, brand=None, availability="InStock"):
    node = {
        "@type": "Product",
        "@id": f"{url}#product",
        "name": name,
        "description": description,
        "brand": {"@type": "Brand", "name": brand or ""},
        "offers": {
            "@type": "Offer",
            "url": url,
            "price": str(price),
            "priceCurrency": currency,
            "availability": f"https://schema.org/{availability}",
            "seller": {"@id": _id(site, "organization")},
        },
    }
    if sku:
        node["sku"] = sku
    if image:
        node["image"] = image
    if not brand:
        node.pop("brand")
    return node


def build(args):
    graph = [organization(args.site, args.org, logo=args.logo, sameas=args.sameas)]

    if args.type in {"article", "product", "faq", "howto"}:
        graph.append(website(args.site, args.org))

    crumbs = _pairs(args.breadcrumb, "--breadcrumb")
    faqs = _pairs(args.faq, "--faq")
    steps = _pairs(args.step, "--step")

    if args.type == "localbusiness":
        graph.append(local_business(
            args.site, args.org, args.phone, args.street, args.city,
            args.region, args.postal, args.country, args.lat, args.lng,
            price_range=args.price_range,
        ))
        return graph

    if not args.url:
        sys.exit(f"error: --url is required for type '{args.type}'")

    if args.type == "product":
        graph.append(webpage(args.site, args.url, args.headline, args.description,
                             image=args.image, breadcrumb=bool(crumbs)))
        graph.append(product(args.site, args.url, args.headline, args.description,
                             args.price, args.currency, image=args.image,
                             sku=args.sku, brand=args.brand))
    else:
        graph.append(webpage(args.site, args.url, args.headline, args.description,
                             image=args.image, breadcrumb=bool(crumbs)))
        if args.image:
            graph.append(image_object(args.url, args.image, args.headline))
        if args.type == "article":
            if not (args.author and args.published):
                sys.exit("error: --author and --published are required for type 'article'")
            graph.append(article(args.site, args.url, args.headline, args.description,
                                 args.author, args.published, args.modified, args.image))

    if crumbs:
        graph.append(breadcrumb_list(args.site, args.url, crumbs))
    if faqs:
        graph.append(faq_page(args.url, faqs))
    if steps:
        graph.append(how_to(args.url, args.headline, steps))

    return graph


def main():
    ap = argparse.ArgumentParser(
        description="Generate interconnected JSON-LD (@graph) for a page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("type", choices=["article", "product", "localbusiness", "faq", "howto"])
    ap.add_argument("--site", required=True, help="Site root, e.g. https://example.com")
    ap.add_argument("--org", required=True, help="Organization / brand name")
    ap.add_argument("--logo", help="Absolute URL of the organization logo")
    ap.add_argument("--sameas", nargs="*", help="Social / authority profile URLs")

    ap.add_argument("--url", help="Canonical URL of this page")
    ap.add_argument("--headline", default="", help="Page title / product name")
    ap.add_argument("--description", default="", help="Meta description")
    ap.add_argument("--image", help="Primary image URL")

    ap.add_argument("--author", help="Article author name")
    ap.add_argument("--published", help="ISO date, e.g. 2026-01-15")
    ap.add_argument("--modified", help="ISO date of last update")

    ap.add_argument("--price", help="Product price")
    ap.add_argument("--currency", default="USD", help="ISO currency code")
    ap.add_argument("--sku", help="Product SKU")
    ap.add_argument("--brand", help="Product brand")

    ap.add_argument("--phone", help="LocalBusiness telephone")
    ap.add_argument("--street", default="", help="Street address")
    ap.add_argument("--city", default="", help="City / locality")
    ap.add_argument("--region", default="", help="Region / state")
    ap.add_argument("--postal", default="", help="Postal code")
    ap.add_argument("--country", default="", help="ISO country code, e.g. EG")
    ap.add_argument("--lat", type=float, help="Latitude")
    ap.add_argument("--lng", type=float, help="Longitude")
    ap.add_argument("--price-range", help="e.g. $$")

    ap.add_argument("--breadcrumb", nargs="*", metavar="NAME=PATH",
                    help="Breadcrumb trail, in order")
    ap.add_argument("--faq", nargs="*", metavar="Q=A", help="FAQ question/answer pairs")
    ap.add_argument("--step", nargs="*", metavar="NAME=TEXT", help="HowTo steps")

    ap.add_argument("--tag", action="store_true", help="Wrap output in a <script> tag")
    ap.add_argument("--minify", action="store_true", help="Emit minified JSON")
    args = ap.parse_args()

    payload = {"@context": "https://schema.org", "@graph": build(args)}
    if args.minify:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    else:
        body = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.tag:
        print(f'<script type="application/ld+json">\n{body}\n</script>')
    else:
        print(body)


if __name__ == "__main__":
    main()
