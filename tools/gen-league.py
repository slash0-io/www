#!/usr/bin/env python3
"""Generate the vendor allowlist report tables from the live feed.

Usage: python3 tools/gen-league.py [--index PATH_OR_URL]   (from the repo root)

Rewrites only the regions of vendor-ip-allowlists/index.html between the
GEN markers, so hand-written prose around them survives regeneration.
Rerun and commit when the catalog changes: a new service, a new
non-publisher, or a change to a vendor's publication practice in the feed's
sources.yaml. Range churn needs no regeneration.

Every scored input comes from the published feed. A service missing its
publication block is a hard error rather than a blank cell, because a blank
cell here would read as a claim about the vendor.
"""

import argparse
import html
import json
import os
import re
import urllib.request

# SLASH0_FEED overrides the feed root, matching gen-services.py, so a catalog
# change can be rendered from a local dist/v1 before it is published.
FEED = os.environ.get("SLASH0_FEED", "https://feed.slash0.io/v1/") + "index.json"
PAGE = "vendor-ip-allowlists/index.html"

FORMAT_LABEL = {"json": "JSON", "xml": "XML", "csv": "CSV", "text": "text",
                "html": "docs page"}
# Cells state what a vendor publishes or supports, never a characterisation of
# the vendor. Facts are defensible; adjectives get quoted.
POLL_LABEL = {"cond-get": "conditional GET", "hash": "full download",
              "docs-page": "page extraction"}


def label(table, key, table_name):
    """Look up a feed enum, failing with the fix rather than a bare KeyError.

    These tables mirror enums the feed repo owns, so a new document type or
    poll mode lands here as a crash during regeneration. Stopping is right:
    a missing label must never render as a blank cell, which would read as a
    claim that the vendor publishes nothing. Say which table to extend.
    """
    try:
        return table[key]
    except KeyError:
        raise SystemExit(
            f"gen-league: the feed carries {key!r}, which {table_name} in "
            f"tools/gen-league.py does not know. Add it there: the feed repo "
            f"has introduced a value this table has not learned yet."
        ) from None


def fetch(src):
    if src.startswith(("http://", "https://", "file://")):
        with urllib.request.urlopen(src) as r:
            return json.load(r)
    with open(src, encoding="utf-8") as f:
        return json.load(f)


def e(s):
    return html.escape(str(s), quote=True)


def cite(label, url, title):
    """Link a claim to the vendor page that states it. A claim with no
    evidence URL is a bug in the feed, not something to render bare."""
    if not url:
        raise SystemExit(f"claim {label!r} has no evidence URL in the feed")
    return f'<a href="{e(url)}" title="{e(title or "")}">{e(label)}</a>'


def score(svc):
    """Points out of five, plus the individual criteria, for one service."""
    pub = svc.get("publication")
    if not pub:
        raise SystemExit(
            f"{svc['slug']}: no publication block in the feed. The feed change "
            "adding it must be published before this page can be built.")
    signal = pub.get("changeSignal") or {}
    purposes = svc.get("purposes") or []
    got = {
        "machine-readable": pub["documentType"] != "html",
        "cheap polling": pub["pollMode"] == "cond-get",
        "purposes split": not (len(purposes) == 1 and purposes[0]["key"] == "all"),
        "advance notice": bool(pub.get("notice")),
        "change signal": signal.get("kind") == "vendor",
    }
    return sum(got.values()), got


def league_table(scored):
    rows = []
    for pts, svc in scored:
        pub = svc["publication"]
        purposes = svc["purposes"]
        signal = pub.get("changeSignal") or {}
        kind = signal.get("kind")
        sig = {"vendor": "vendor", "docs-repo": "docs repo"}.get(kind, "none")
        # Every claim about a vendor links to the vendor page that states it.
        if kind:
            sig = cite(sig, signal.get("evidence"), signal.get("detail"))
        notice = pub.get("notice")
        notice_cell = (cite(notice, pub.get("noticeEvidence"), "vendor documentation")
                       if notice else "none")
        one_set = len(purposes) == 1 and purposes[0]["key"] == "all"
        v6 = sum(p["ipv6Count"] for p in purposes)
        rows.append(
            f'      <tr><td><a href="/services/{e(svc["slug"])}/">{e(svc["name"])}</a></td>'
            f'<td class="lt-n">{pts}</td>'
            f'<td>{e(label(FORMAT_LABEL, pub["documentType"], "FORMAT_LABEL"))}</td>'
            f'<td>{e(label(POLL_LABEL, pub["pollMode"], "POLL_LABEL"))}</td>'
            f'<td>{"one set" if one_set else len(purposes)}</td>'
            f"<td>{notice_cell}</td>"
            f"<td>{sig}</td>"
            f'<td>{"yes" if v6 else "no"}</td></tr>')
    return ('<div class="lt-scroll">\n    <table>\n'
            "      <thead><tr><th>Service</th><th>Score</th><th>Source</th>"
            "<th>Change detection</th><th>Purposes</th><th>Advance notice</th>"
            "<th>Change signal</th><th>IPv6</th></tr></thead>\n"
            "      <tbody>\n" + "\n".join(rows) +
            "\n      </tbody>\n    </table>\n  </div>")


def nonpublisher_table(nps):
    rows = [f'      <tr><td>{e(np["name"])}</td><td>{e(np["vendorPosition"])}</td></tr>'
            for np in sorted(nps, key=lambda x: x["name"])]
    return ('<div class="lt-scroll">\n    <table>\n'
            "      <thead><tr><th>Service</th><th>Stated position</th></tr></thead>\n"
            "      <tbody>\n" + "\n".join(rows) +
            "\n      </tbody>\n    </table>\n  </div>")


def findings(scored, index):
    n = len(scored)
    pubs = [s["publication"] for _, s in scored]
    full = [s["name"] for pts, s in scored if pts == 5]
    notice = sorted(s["name"] for _, s in scored if s["publication"].get("notice"))
    vendor_sig = sorted(s["name"] for _, s in scored
                        if (s["publication"].get("changeSignal") or {}).get("kind") == "vendor")
    docs_repo = sum(1 for p in pubs
                    if (p.get("changeSignal") or {}).get("kind") == "docs-repo")
    scrape = sum(1 for p in pubs if p["documentType"] == "html")
    cond = sum(1 for p in pubs if p["pollMode"] == "cond-get")
    no_v6 = sum(1 for _, s in scored
                if sum(p["ipv6Count"] for p in s["purposes"]) == 0)
    one_set = sum(1 for _, s in scored
                  if len(s["purposes"]) == 1 and s["purposes"][0]["key"] == "all")
    total = sum(p["ipv4Count"] + p["ipv6Count"] for _, s in scored for p in s["purposes"])
    nps = len(index.get("nonPublishers") or [])

    def li(t):
        return f"    <li>{t}</li>"

    items = [
        li(f"<strong>{n} services publish official ranges. {nps} state that you "
           f"should not pin them at all.</strong> Between them the {n} publish "
           f"{total:,} CIDRs, rebuilt continuously and republished as a signed feed."),
        li(f"<strong>{len(full)} of {n} "
           f"{'scores' if len(full) == 1 else 'score'} five out of five.</strong> "
           + (f"Only {full[0]} does everything on this list." if len(full) == 1
              else f"They are {', '.join(full)}.")),
        li(f"<strong>{len(notice)} of {n} commit to any advance notice</strong> before "
           f"newly published ranges start carrying traffic: {', '.join(notice)}. "
           "For everyone else, a range can go live the moment it appears."),
        li(f"<strong>{len(vendor_sig)} of {n} operate a change signal you can "
           f"subscribe to</strong> ({', '.join(vendor_sig)}). Another {docs_repo} are "
           "trackable only because their documentation happens to live in a public "
           "git repository, so the commit feed stands in for a notification the "
           "vendor does not offer."),
        li(f"<strong>{scrape} of {n} have no machine-readable endpoint at all.</strong> "
           "Their ranges exist only inside a documentation page, so every consumer "
           "writes a scraper and every consumer breaks when the page is restyled."),
        li(f"<strong>{cond} of {n} honor conditional requests.</strong> The rest have "
           "no cache validators, so checking for a change means downloading the "
           "whole list again."),
        li(f"<strong>{one_set} of {n} publish one undifferentiated set.</strong> "
           "Allowlisting the API also allowlists everything else the vendor runs, "
           "including infrastructure that has nothing to do with your integration."),
        li(f"<strong>{no_v6} of {n} publish no IPv6 ranges.</strong> Reported in "
           "the table but left out of the score, since a vendor with no IPv6 "
           "footprint has nothing to publish."),
    ]
    return "  <ul>\n" + "\n".join(items) + "\n  </ul>"


def check_style(body, name):
    """Site copy rule: no em dashes, including in text carried in from the
    feed. Caught here rather than in review, since these strings are written
    in the feed's registry and only become site copy at generation time."""
    if "—" in body:
        bad = [ln for ln in body.split("\n") if "—" in ln]
        raise SystemExit(
            f"em dash in generated {name} block, restructure the source text "
            "in the feed's sources.yaml:\n  " + "\n  ".join(bad))


def replace_block(page, name, body):
    start, end = f"<!-- GEN:{name} -->", f"<!-- /GEN:{name} -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(page):
        raise SystemExit(f"{PAGE}: missing {start} ... {end} markers")
    check_style(body, name)
    return pattern.sub(f"{start}\n{body}\n  {end}", page, count=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=FEED,
                    help="feed index.json to build from (path or URL)")
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index = fetch(args.index)
    scored = [(score(s)[0], s) for s in index["services"]]
    # Best first; ties alphabetical, so the ordering is reproducible.
    scored.sort(key=lambda r: (-r[0], r[1]["name"].lower()))

    path = os.path.join(root, PAGE)
    with open(path, encoding="utf-8") as f:
        page = f.read()
    page = replace_block(page, "findings", findings(scored, index))
    page = replace_block(page, "table", "  " + league_table(scored))
    page = replace_block(page, "nonpublishers",
                         "  " + nonpublisher_table(index.get("nonPublishers") or []))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {PAGE}: {len(scored)} services, "
          f"{len(index.get('nonPublishers') or [])} non-publishers")


if __name__ == "__main__":
    main()
