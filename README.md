# slash0.io

The slash0 website: static HTML served by GitHub Pages (deploy from branch,
`main` / root) at https://slash0.io.

No build system on purpose. Edit the HTML, push, done. Pushing to `main`
publishes immediately.

## Layout

| Path | What it is |
|---|---|
| `index.html` | landing page |
| `docs/` | quickstart, how it works, security, FAQ, contact, onboarding |
| `services/` | one page per catalog service, plus the directory index |
| `vendor-ip-allowlists/` | the scored vendor publication report |
| `calculator/` | security-group quota estimator |
| `changelog/` | human-readable view of the feed changelog |
| `assets/` | CSS, JS, images |

## Generated pages

Two stdlib-only Python scripts, run from the repo root:

```sh
python3 tools/gen-services.py    # services/, services/index.html, sitemap.xml
python3 tools/gen-league.py      # the tables in vendor-ip-allowlists/index.html
```

Both read the live feed. Rerun and commit them when the **catalog** changes: a
new service, a new purpose, a rename, a new non-publisher, or a change to a
vendor's publication practice. Range churn needs no regeneration, because
counts and ranges render client-side from the feed via `assets/live.js`, so a
committed page can never serve stale IPs.

`gen-league.py` rewrites only the regions between the `GEN` markers, so
hand-written prose around them survives regeneration.
