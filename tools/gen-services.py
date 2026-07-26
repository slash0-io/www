#!/usr/bin/env python3
"""Generate the per-service IP-range pages from the live feed.

Usage: python3 tools/gen-services.py   (from the repo root)

Writes services/<slug>/index.html for every catalog service, the
services/index.html directory, and sitemap.xml. Static content only:
prose, purposes, provenance, and Terraform examples. The ranges and
counts render client-side from the feed (assets/live.js), so committed
pages never serve stale IPs. Rerun and commit when the catalog changes
(new service, new purpose, renames); range churn needs no regeneration.
"""

import html
import json
import os
import sys
import urllib.request

FEED = "https://feed.slash0.io/v1/"
SITE = "https://slash0.io"

CATEGORY_NAMES = {
    "ai": "AI",
    "business-saas": "Business SaaS",
    "cdn": "CDN",
    "cloud": "Cloud",
    "comms": "Communications",
    "data-platform": "Data platforms",
    "devtools": "Developer tools",
    "identity": "Identity",
    "observability": "Observability",
    "payments": "Payments",
    "security": "Security",
}

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' "
           "fill='%230b0f14'/%3E%3Ctext x='16' y='23' font-family='monospace' "
           "font-size='20' font-weight='700' fill='%2358d68d' "
           "text-anchor='middle'%3E/0%3C/text%3E%3C/svg%3E")


def fetch(path):
    with urllib.request.urlopen(FEED + path) as r:
        return json.load(r)


def head(title, description, extra=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="icon" href="{FAVICON}">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="stylesheet" href="/assets/site.css">
{extra}</head>
<body>
<header><div class="wrap">
  <div class="logo"><a href="/" style="color:inherit;text-decoration:none"><b>/0</b> slash0</a></div>
  <nav><a href="/docs/">docs</a><a href="/services/">services</a><a href="https://feed.slash0.io/">catalog</a><a href="/#access">early access</a></nav>
</div></header>
"""


FOOTER = """<footer><div class="wrap">
  <div><a href="https://github.com/slash0-io">github</a><a href="/services/">services</a><a href="/vendor-ip-allowlists/">vendor report</a><a href="/calculator/">calculator</a><a href="/changelog/">changelog</a><a href="https://feed.slash0.io/">catalog</a><a href="https://registry.terraform.io/providers/slash0-io/egress/latest">terraform</a></div>
  <div>© 2026 slash0</div>
</div></footer>
</body>
</html>
"""

CLASSIFICATION_NOTES = {
    "mixed": ("The feed classifies this service as <strong>mixed</strong>: "
              "not every purpose runs on vendor-dedicated infrastructure. "
              "Review a purpose before treating its ranges as exclusively {name}."),
    "cdn-shared": ("The feed classifies this service as <strong>cdn-shared</strong>: "
                   "these are shared edge ranges, and allowlisting them admits "
                   "whatever runs behind the same edge, not only {name}."),
}


def tf_ident(slug, key):
    return (slug + "_" + key).replace("-", "_")


def tf_snippet(slug, key, direction, has_v6):
    ident = tf_ident(slug, key)
    rule_type = "ingress" if direction == "ingress" else "egress"
    v6line = ""
    if has_v6:
        v6line = f"\n  ipv6_cidr_blocks  = data.egress_ranges.{ident}.ipv6_cidrs"
    return f"""data "egress_ranges" "{ident}" {{
  service = "{slug}"
  purpose = "{key}"
}}

resource "aws_security_group_rule" "{ident}" {{
  type              = "{rule_type}"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = data.egress_ranges.{ident}.ipv4_cidrs{v6line}
  security_group_id = aws_security_group.app.id
}}"""


def direction_line(direction, name):
    if direction == "egress":
        return (f"Direction: egress. Ranges your workloads connect out to; "
                f"use them in security group egress rules.")
    if direction == "ingress":
        return (f"Direction: ingress. Ranges {name} connects from (webhook "
                f"delivery); use them in security group ingress rules on your "
                f"receiving endpoints.")
    return (f"Direction: both. {name} publishes these ranges for traffic in "
            f"either direction; use them in the rule direction your "
            f"integration needs. The example below shows egress.")


def service_page(entry, doc):
    slug, name = entry["slug"], entry["name"]
    purposes = entry["purposes"]
    keys = [p["key"] for p in purposes]
    title = f"{name} IP ranges ({', '.join(keys)}) · slash0"
    description = (f"Official {name} IP ranges for allowlisting: "
                   f"{', '.join(keys)}, IPv4 and IPv6, from the vendor's own "
                   f"publication. Live data, Terraform examples, AWS managed "
                   f"prefix lists.")

    out = [head(title, description, '<script src="/assets/live.js" defer></script>\n')]
    out.append(f'<div class="doc" id="service-page" data-slug="{html.escape(slug)}">\n')
    out.append(f'<span class="crumb"><a href="/services/">services</a> / {html.escape(slug)}</span>\n')
    out.append(f"<h1>{html.escape(name)} IP ranges</h1>\n")
    out.append(f'<p class="tagline">Official {html.escape(name)} ranges from the '
               f"vendor's publication, split by purpose: "
               f"{html.escape(', '.join(keys))}. The ranges below render live "
               f'from the <a href="https://feed.slash0.io/v1/services/{html.escape(slug)}.json">signed slash0 feed</a>'
               f'<span id="svc-updated" hidden>; last range change <b id="svc-updated-rel"></b></span>.</p>\n')

    note = CLASSIFICATION_NOTES.get(entry["classification"])
    if note:
        out.append(f'<p class="note">{note.format(name=html.escape(name))}</p>\n')

    out.append("<article>\n")
    out.append("<table><tr><th>purpose</th><th>direction</th><th>IPv4</th><th>IPv6</th></tr>\n")
    for p in purposes:
        k = html.escape(p["key"])
        out.append(f'<tr><td><a href="#{k}"><code>{html.escape(slug)}/{k}</code></a></td>'
                   f'<td>{html.escape(p["direction"])}</td>'
                   f'<td id="count4-{k}">·</td><td id="count6-{k}">·</td></tr>\n')
    out.append("</table>\n")

    for p in purposes:
        k = p["key"]
        ke = html.escape(k)
        out.append(f'<h2 id="{ke}">{html.escape(slug)}/{ke}</h2>\n')
        out.append(f"<p>{html.escape(direction_line(p['direction'], name))}</p>\n")
        out.append(f'<pre class="ranges" id="ranges-{ke}">loading ranges from the feed…</pre>\n')
        out.append(f'<p class="note" id="quota-{ke}" hidden>This purpose currently '
                   f"publishes more IPv4 ranges than the default rules-per-SG "
                   f"quota (60). Each CIDR consumes one rule; the hosted prefix "
                   f'list spends quota once per list instead. Details in the <a href="/docs/faq/">FAQ</a>.</p>\n')
        out.append("<h3>Terraform</h3>\n")
        out.append("<pre>" + html.escape(tf_snippet(slug, k, p["direction"], p["ipv6Count"] > 0)) + "</pre>\n")

    out.append("<h2>keep rules current automatically</h2>\n")
    out.append(f'<p>Terraform data sources refresh only when you run an apply. '
               f"The hosted tier publishes the same data via AWS managed prefix "
               f"lists (<code>egress.{html.escape(slug)}.{html.escape(keys[0])}.v4</code> and so on), "
               f"shared into your account via AWS RAM: rules reference one "
               f"<code>pl-…</code> id and update within a minute of a vendor "
               f'change, with removals held through a 72 hour grace window. '
               f'<a href="/#access">Request early access</a> or read '
               f'<a href="/docs/how-it-works/">how it works</a>.</p>\n')

    out.append("<h2>provenance</h2>\n")
    prov = doc.get("provenance", "")
    out.append(f'<p>Ranges come from {html.escape(name)}\'s official publication: '
               f'<a href="{html.escape(prov)}">{html.escape(prov)}</a>. Fetched sources:</p>\n<ul>\n')
    for src in doc.get("sources", []):
        u = html.escape(src["url"])
        out.append(f'<li><code><a href="{u}">{u}</a></code></li>\n')
    out.append("</ul>\n")
    out.append('<p>Every publish is signed (ECDSA P-256 over the feed index, '
               "each service document hash-chained to it) and every range "
               'change is recorded in the <a href="/changelog/">changelog</a>. '
               'Verification steps: <a href="/docs/security/">security</a>. '
               'Provider setup: <a href="/docs/quickstart/">quickstart</a>.</p>\n')
    out.append("</article>\n</div>\n")
    out.append(FOOTER)
    return "".join(out)


def directory_page(services):
    title = "SaaS and cloud service IP ranges · slash0"
    description = (f"Official IP ranges for {len(services)} SaaS and cloud "
                   f"services, per purpose, IPv4 and IPv6, rebuilt continuously "
                   f"from each vendor's own publication. Signed feed, Terraform "
                   f"provider, AWS managed prefix lists.")
    out = [head(title, description)]
    out.append('<div class="doc">\n<h1>service IP ranges</h1>\n')
    out.append(f'<p class="tagline">Official IP ranges for {len(services)} '
               f"services, one page per service, straight from each vendor's "
               f"own publication. Ranges render live from the "
               f'<a href="https://feed.slash0.io/v1/index.json">signed feed</a>; '
               f'changes land in the <a href="/changelog/">changelog</a>. '
               f'Services that do not publish ranges are listed in the '
               f'<a href="https://feed.slash0.io/">catalog</a>.</p>\n')
    out.append("<article>\n")
    by_cat = {}
    for s in services:
        by_cat.setdefault(s["category"], []).append(s)
    for cat in sorted(by_cat, key=lambda c: CATEGORY_NAMES.get(c, c)):
        out.append(f"<h2>{html.escape(CATEGORY_NAMES.get(cat, cat.title()))}</h2>\n")
        for s in sorted(by_cat[cat], key=lambda x: x["slug"]):
            keys = ", ".join(p["key"] for p in s["purposes"])
            out.append(f'<a class="cardlink" href="/services/{html.escape(s["slug"])}/">'
                       f'<b>{html.escape(s["name"])}</b>'
                       f'<span>{html.escape(keys)}</span></a>\n')
    out.append("</article>\n</div>\n")
    out.append(FOOTER)
    return "".join(out)


def sitemap(services):
    urls = ["/", "/changelog/", "/services/", "/calculator/",
            "/vendor-ip-allowlists/",
            "/docs/", "/docs/quickstart/", "/docs/how-it-works/",
            "/docs/security/", "/docs/faq/", "/docs/contact/",
            "/docs/onboarding/"]
    urls += [f"/services/{s['slug']}/" for s in sorted(services, key=lambda x: x["slug"])]
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n']
    for u in urls:
        out.append(f"  <url><loc>{SITE}{u}</loc></url>\n")
    out.append("</urlset>\n")
    return "".join(out)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index = fetch("index.json")
    services = sorted(index["services"], key=lambda s: s["slug"])

    for entry in services:
        doc = fetch(entry["path"])
        d = os.path.join(root, "services", entry["slug"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write(service_page(entry, doc))

    with open(os.path.join(root, "services", "index.html"), "w") as f:
        f.write(directory_page(services))
    with open(os.path.join(root, "sitemap.xml"), "w") as f:
        f.write(sitemap(services))
    print(f"wrote {len(services)} service pages + directory + sitemap.xml")


if __name__ == "__main__":
    sys.exit(main())
