"""Copy the picked companies' cached reference bodies. Run with python3 -I."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "scratchpad/vendor-crawl/cache/2026-10-28"
DEST = Path("data/raw/vendor-surface/2026-10-28/kinds")
INDEX = ROOT / "docs/research/vendor-surface/kinds-index.json"


def catalog_patterns(site):
    # Read just these adjacent scalar fields from the catalog's fixed YAML layout.
    text = (ROOT / "docs/research/vendor-surface/catalog.yaml").read_text()
    section = text.split(f"\n{site}:\n" if site == "tijori" else "screener:\n", 1)[1]
    if site == "screener":
        section = section.split("\ntijori:\n", 1)[0]
    for identifier, pattern in re.findall(
        r"^  - id: (.+)\n    scope: company\n    url_pattern: (.+)$", section, re.M
    ):
        if "#" in pattern or " (" in pattern:
            continue
        path = pattern.split("?", 1)[0].replace("[", "").replace("]", "")
        regex = re.escape(path)
        for field in re.findall(r"\{([^}]+)\}", path):
            replacement = (
                "(?:" + "|".join(re.escape(v) for v in field.split("|")) + ")"
                if "|" in field and "..." not in field
                else f"(?P<{field}>[^/]+)"
                if field.isidentifier()
                else "[^/]+"
            )
            regex = regex.replace(re.escape("{" + field + "}"), replacement)
        if "[consolidated/]" in pattern:
            regex = regex.replace("consolidated/", "(?:consolidated/)?")
        yield identifier, re.compile(regex)


def main():
    if INDEX.exists():
        raise FileExistsError(f"Refusing to overwrite {INDEX.relative_to(ROOT)}")
    picks = json.loads((ROOT / "scratchpad/vendor-crawl/picks.json").read_text())
    rows, counts, skipped = [], Counter(), Counter()
    for site in ("screener", "tijori"):
        patterns = list(catalog_patterns(site))
        aliases, items = {}, {}
        for pick in picks:
            symbol = pick["symbol"]
            slug = urlsplit(pick["tijori_url"]).path.split("/")[2:3]
            # The replacement pick left its URLs blank in picks.json.
            slug = slug[0] if slug else "aurobindo-pharma-limited"
            aliases[symbol if site == "screener" else slug] = symbol
        cached = [(p, json.loads(p.read_text())) for p in sorted((CACHE / site).glob("*.json"))]
        for meta, row in cached:
            parts = urlsplit(row["url"]).path.strip("/").split("/")
            if len(parts) not in (2, 3) or parts[0] != "company" or parts[1] not in aliases:
                continue
            symbol = aliases[parts[1]]
            body = meta.with_suffix(".body").read_text()
            marker = (
                r'data-(?:company|warehouse)-id="(\d+)"'
                if site == "screener"
                else r"""company_id["']?\s*[:=]\s*["']?(\d+)"""
            )
            for identifier in re.findall(marker, body):
                aliases[identifier] = symbol
            for identifier in re.findall(
                r'<div[^>]*class="rmix_graph_block"[^>]*company-id="(\d+)"', body
            ):
                items[identifier] = symbol
        for meta, row in cached:
            url = urlsplit(row["url"])
            for candidate, regex in patterns:
                match = regex.fullmatch(unquote(url.path))
                if match:
                    identifier = candidate
                    break
            else:
                skipped[site] += 1
                continue
            fields = match.groupdict()
            query = parse_qs(url.query, keep_blank_values=True)
            identity = next(iter(fields.values()), query.get("company_id", [None])[0])
            symbol = (items if "item_id" in fields else aliases).get(identity)
            if symbol is None:
                skipped[site] += 1
                continue
            basis = "na"
            if site == "screener" and (
                "consolidated" in query or identifier in ("company-page", "related-party")
            ):
                basis = (
                    "consolidated"
                    if ("/consolidated/" in url.path or query.get("consolidated") == ["true"])
                    else "standalone"
                )
            selector = fields.get("column_selector", "")
            if "_c_" in selector or "_s_" in selector:
                basis = "consolidated" if "_c_" in selector else "standalone"
            key = hashlib.sha256(row["url"].encode()).hexdigest()
            ext = "json" if "json" in row["content_type"] else "html"
            path = DEST / site / symbol / f"{identifier}__{key[:12]}__{basis}.{ext}"
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(meta.with_suffix(".body").read_bytes())
            if hashlib.sha256(target.read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError(f"sha256 mismatch: {path}")
            rows.append(
                {
                    "symbol": symbol,
                    "site": site,
                    "id": identifier,
                    "url": row["url"],
                    "request_key": key,
                    "basis": basis,
                    "status": row["status"],
                    "sha256": row["sha256"],
                    "path": str(path),
                    "kind": "response",
                }
            )
            counts[site, symbol] += 1
    with INDEX.open("x") as output:
        output.write(json.dumps(rows, indent=2) + "\n")
    for site in ("screener", "tijori"):
        total = sum(counts[site, pick["symbol"]] for pick in picks)
        print(site, "copied", total, "skipped", skipped[site])
        for pick in picks:
            print(site, pick["symbol"], counts[site, pick["symbol"]])


if __name__ == "__main__":
    main()
