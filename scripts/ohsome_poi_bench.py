"""Response times of small POI requests: ohsome API v2 compared with openpoiservice (ops).

Each case is a small area (a city quarter, a small town) and a set of OSM tags, sent to both services:
- ohsome  `features`         POST /extraction/features.parquet, clip=true (what an ops facade would need)
- ohsome  `features_noclip`  the same with clip=false
- ohsome  `count`            POST /stats/features/count.json (same query, no geometries transferred)
- ops     `pois`             POST /pois with the matching ops category ids
Once per round, GET /metadata measures ohsome's floor (gateway + app + a trivial DB call).

Every request opens a new connection (both gateways answer with `Connection: close`) and is timed in phases: DNS,
TCP connect (about one round trip), TLS handshake, time to first byte after sending, and download. For ohsome the
`x-envoy-upstream-service-time` header gives the time spent behind its envoy proxy, so `ttfb - upstream` is roughly
the gateway and network share.

usage: python scripts/ohsome_poi_bench.py [--categories categories.yml] [--out DIR] [--rounds 3] [--cases a,b]
                                          [--variants a,b] [--dry-run] [--summarise DIR]

The API key (a key from account.heigit.org; it works for both services) comes from $HEIGIT_API_KEY, or from
~/.config/ors-secrets/heigit-api-key.env (ORS_API_KEY=...). Needs PyYAML; pyarrow is optional and only used to count
the features in the Parquet responses. A full run is 135 requests and takes about 12 minutes; 66 of them count
against the key's daily extraction quota (250 on 2026-10-23).

Without a Python environment on the host, run it in the image Docker Compose built for ops (no pyarrow there, so the
`results` column of the features variants stays empty):
    export HEIGIT_API_KEY=...
    docker run --rm --user "$(id -u)" -e HEIGIT_API_KEY -v "$PWD:/repo" -w /repo --entrypoint python ops-api \
        scripts/ohsome_poi_bench.py --out poi-bench-$(date +%Y%m%d-%H%M)
"""
import argparse
import http.client
import io
import json
import math
import os
import socket
import ssl
import statistics
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

import yaml

try:
    import pyarrow.parquet as pq
except ImportError:  # feature counts are left out
    pq = None

OHSOME_URL = "https://api.heigit.org/ohsome-api/v2-rc"
OPS_URL = "https://api.openrouteservice.org/pois"
# the categories production ops runs with
DEFAULT_CATEGORIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "categories_docker.yml")
# seconds between requests to the same host; ohsome's gateway allows 15 per minute
MIN_GAP = {"api.heigit.org": 4.5, "api.openrouteservice.org": 1.5}
OPS_LIMIT = 2000  # ops' maximum response size
# connection phases above these limits mark a request as disturbed by the client's network; it's left out of medians
MAX_DNS_MS, MAX_TCP_MS, MAX_TLS_MS = 200, 300, 500

# bbox = (min lon, min lat, max lon, max lat); buffer = (lon, lat, metres)
HD_ALTSTADT = (8.690, 49.408, 8.715, 49.415)  # Heidelberg old town, about 1.4 km²
SCHWETZINGEN = (8.555, 49.375, 8.585, 49.390)  # small town centre, about 3.7 km²
KREUZBERG = (13.410, 52.495, 13.445, 52.505)  # Berlin city quarter, about 2.6 km²
MUC_ALTSTADT = (11.565, 48.132, 11.585, 48.142)  # Munich old town, about 1.6 km²
VILLAGE = (8.790, 49.480, 8.810, 49.490)  # Odenwald village, few POIs, about 1.6 km²
BISMARCKPLATZ = (8.6935, 49.4097, 500)

SUSTENANCE5 = [("amenity", v) for v in ("restaurant", "cafe", "bar", "pub", "fast_food")]
# name: (area, tags); tags are (key, value) pairs, "group:<id>" for an ops category group, or "all"
CASES = {
    "hd_altstadt_banks": (HD_ALTSTADT, [("amenity", "bank")]),
    "hd_altstadt_bank_atm": (HD_ALTSTADT, [("amenity", "bank"), ("amenity", "atm")]),
    "hd_altstadt_sustenance5": (HD_ALTSTADT, SUSTENANCE5),
    "hd_altstadt_all": (HD_ALTSTADT, "all"),
    "hd_bismarckplatz_500m_restaurants": (BISMARCKPLATZ, [("amenity", "restaurant")]),
    "schwetzingen_shops": (SCHWETZINGEN, "group:420"),
    "schwetzingen_supermarket_bakery": (SCHWETZINGEN, [("shop", "supermarket"), ("shop", "bakery")]),
    "kreuzberg_pharmacies": (KREUZBERG, [("amenity", "pharmacy")]),
    "kreuzberg_supermarket_or_pharmacy": (KREUZBERG, [("shop", "supermarket"), ("amenity", "pharmacy")]),
    "muc_altstadt_school_kindergarten": (MUC_ALTSTADT, [("amenity", "school"), ("amenity", "kindergarten")]),
    "village_banks": (VILLAGE, [("amenity", "bank")]),
}
VARIANTS = ("features", "features_noclip", "count", "pois")


def main():
    args = parse_args()
    if args.summarise:
        write_summary(args.summarise, [json.loads(line) for line in open(os.path.join(args.summarise, "results.jsonl"))])
        return
    categories = Categories(args.categories)
    cases = {name: CASES[name] for name in (args.cases or CASES)}
    variants = args.variants or VARIANTS
    plan = [(name, variant) for name in cases for variant in variants]
    print(f"{len(plan) * args.rounds + args.rounds} requests in {args.rounds} rounds", file=sys.stderr)
    if args.dry_run:
        for name, (area, tags) in cases.items():
            print(f"{name}: ohsome filter {categories.ohsome_filter(tags)!r}, ops {categories.ops_filters(tags)}")
        return

    key = api_key()
    os.makedirs(args.out, exist_ok=True)
    client = Client(key)
    rows = []
    with open(os.path.join(args.out, "results.jsonl"), "w") as out:
        for round_no in range(args.rounds):
            for name, variant in [("metadata", "metadata")] + plan:
                try:
                    row = run(client, categories, name, variant, cases.get(name))
                except (OSError, http.client.HTTPException) as e:  # timeouts, resets: record and go on
                    row = {"status": 0, "total_ms": 0, "error": f"{type(e).__name__}: {e}",
                           "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                row.update(round=round_no, case=name, variant=variant)
                print(json.dumps(row), file=out, flush=True)
                print(f"round {round_no} {name:36} {variant:16} {row['status']} {row['total_ms']:7.0f} ms "
                      f"{row.get('results', '')}", file=sys.stderr)
                rows.append(row)
    write_summary(args.out, rows)


def write_summary(directory, rows):
    summary = summarise(rows)
    with open(os.path.join(directory, "summary.md"), "w") as f:
        f.write(summary)
    print(summary)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--categories", default=DEFAULT_CATEGORIES, help="ops categories.yml")
    p.add_argument("--out", default="poi-bench-" + datetime.now().strftime("%Y%m%d-%H%M"))
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--cases", type=lambda s: s.split(","), help=f"subset of: {', '.join(CASES)}")
    p.add_argument("--variants", type=lambda s: s.split(","), help=f"subset of: {', '.join(VARIANTS)}")
    p.add_argument("--dry-run", action="store_true", help="print the filters and the request count only")
    p.add_argument("--summarise", metavar="DIR", help="only rebuild DIR/summary.md from DIR/results.jsonl")
    args = p.parse_args()
    unknown = set(args.cases or ()) - set(CASES) | set(args.variants or ()) - set(VARIANTS)
    if unknown:
        p.error(f"unknown cases or variants: {', '.join(sorted(unknown))}")
    return args


def api_key():
    if os.environ.get("HEIGIT_API_KEY"):
        return os.environ["HEIGIT_API_KEY"]
    path = os.path.expanduser("~/.config/ors-secrets/heigit-api-key.env")
    if not os.path.exists(path):
        sys.exit("Set HEIGIT_API_KEY to an api.heigit.org / openrouteservice API key.")
    with open(path) as f:
        return next(line.split("=", 1)[1].strip().strip("\"'") for line in f if line.startswith("ORS_API_KEY="))


class Categories:
    """ops categories.yml: maps tags to ops category ids and builds the equivalent ohsome filter."""

    def __init__(self, path):
        self.ids = {}  # (key, value) -> category id
        self.groups = {}  # group id -> [(key, value)]
        for group in yaml.safe_load(open(path)).values():
            members = [(k, v) for k, values in group["children"].items() for v in values]
            self.groups[group["id"]] = members
            for k, values in group["children"].items():
                for v, category_id in values.items():
                    self.ids[(k, v)] = category_id

    def tags(self, tags):
        if tags == "all":
            return sorted(self.ids)
        if isinstance(tags, str) and tags.startswith("group:"):
            return self.groups[int(tags.split(":")[1])]
        return tags

    def ohsome_filter(self, tags):
        """one `key in (...)` term per key, or-ed, as an ops category filter would match"""
        by_key = {}
        for k, v in self.tags(tags):
            by_key.setdefault(k, []).append(v)
        return " or ".join(f"{quote(k)} in ({', '.join(quote(v) for v in vs)})" for k, vs in by_key.items())

    def ops_filters(self, tags):
        if tags == "all":
            return {}  # ops returns every category without a filter
        if isinstance(tags, str):
            return {"category_group_ids": [int(tags.split(":")[1])]}
        return {"category_ids": [self.ids[t] for t in tags]}


def quote(word):
    return word if word.replace("_", "").replace(":", "").isalnum() else '"%s"' % word


def run(client, categories, name, variant, case):
    if variant == "metadata":
        return without_body(client.request("GET", OHSOME_URL + "/metadata"))
    area, tags = case
    if variant == "pois":
        body = {"request": "pois", "geometry": ops_geometry(area), "limit": OPS_LIMIT}
        filters = categories.ops_filters(tags)
        if filters:
            body["filters"] = filters
        row = client.request("POST", OPS_URL, body)
        if row["status"] == 200:
            row["results"] = len(json.loads(row.pop("body"))["features"])
        return without_body(row)
    body = {"filter": categories.ohsome_filter(tags), "aoi": ohsome_aoi(area), "time": "latest"}
    if variant == "count":
        row = client.request("POST", OHSOME_URL + "/stats/features/count.json", body)
        if row["status"] == 200:
            row["results"] = json.loads(row["body"])["result"]["value"][0]
        return without_body(row)
    body["clip"] = variant == "features"
    row = client.request("POST", OHSOME_URL + "/extraction/features.parquet", body)
    if row["status"] == 200 and pq:
        row["results"] = pq.read_metadata(io.BytesIO(row["body"])).num_rows
    return without_body(row)


def without_body(row):
    body = row.pop("body", b"")
    if row["status"] != 200:
        row["error"] = body[:300].decode(errors="replace")
    return row


def ops_geometry(area):
    if len(area) == 3:
        lon, lat, metres = area
        return {"geojson": {"type": "Point", "coordinates": [lon, lat]}, "buffer": metres}
    return {"bbox": [[area[0], area[1]], [area[2], area[3]]]}


def ohsome_aoi(area):
    if len(area) == 3:
        return circle(*area)
    return list(area)


def circle(lon, lat, metres, points=32):
    """GeoJSON polygon approximating a buffer around a point; accurate enough for a few kilometres"""
    dlat = metres / 111320
    dlon = metres / (111320 * math.cos(math.radians(lat)))
    ring = [[round(lon + dlon * math.cos(a), 6), round(lat + dlat * math.sin(a), 6)]
            for a in (2 * math.pi * i / points for i in range(points))]
    return {"type": "Polygon", "coordinates": [ring + [ring[0]]]}


class Client:
    """HTTPS requests on a fresh connection each, timed per phase, with a minimum gap per host."""

    def __init__(self, key):
        self.key = key
        self.last_request = {}
        self.tls = ssl.create_default_context()

    def request(self, method, url, body=None):
        parts = urlsplit(url)
        host = parts.hostname
        self.wait_for(host)
        t = {"start": time.perf_counter()}
        address = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)[0][4]
        t["dns"] = time.perf_counter()
        raw = socket.create_connection(address[:2], timeout=300)
        t["tcp"] = time.perf_counter()
        sock = self.tls.wrap_socket(raw, server_hostname=host)
        t["tls"] = time.perf_counter()
        connection = http.client.HTTPSConnection(host, timeout=300)
        connection.sock = sock
        headers = {"Authorization": self.key, "Accept-Encoding": "identity"}
        payload = None
        if body is not None:
            payload = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        connection.request(method, parts.path, payload, headers)
        t["sent"] = time.perf_counter()
        response = connection.getresponse()
        t["headers"] = time.perf_counter()
        data = response.read()
        t["done"] = time.perf_counter()
        connection.close()
        self.last_request[host] = time.time()
        upstream = response.getheader("x-envoy-upstream-service-time")
        return {
            "status": response.status,
            "dns_ms": ms(t["start"], t["dns"]),
            "tcp_ms": ms(t["dns"], t["tcp"]),
            "tls_ms": ms(t["tcp"], t["tls"]),
            "ttfb_ms": ms(t["sent"], t["headers"]),
            "download_ms": ms(t["headers"], t["done"]),
            "total_ms": ms(t["start"], t["done"]),
            "upstream_ms": int(upstream) if upstream else None,
            "bytes": len(data),
            "request_bytes": len(payload or b""),
            "quota_left": response.getheader("x-ratelimit-remaining"),
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "body": data,
        }

    def wait_for(self, host):
        wait = self.last_request.get(host, 0) + MIN_GAP.get(host, 1.0) - time.time()
        if wait > 0:
            time.sleep(wait)


def ms(start, end):
    return round((end - start) * 1000, 1)


def summarise(rows):
    answered = [r for r in rows if r["status"] == 200]
    ok = [r for r in answered if not disturbed(r)]
    failed = len(rows) - len(answered)
    rounds = len({r["round"] for r in rows})
    lines = [
        "# POI response times: ohsome API v2 vs openpoiservice",
        "",
        f"Run {rows[0]['at']} to {rows[-1]['at']} from {socket.gethostname()}, {rounds} rounds, one new connection "
        "per request. "
        f"{len(rows)} requests, {failed} failed, {len(answered) - len(ok)} answered but left out because the "
        f"client's connection was disturbed (DNS > {MAX_DNS_MS} ms, TCP > {MAX_TCP_MS} ms or TLS > {MAX_TLS_MS} ms). "
        "Medians in ms over the rest; `first` is the total of round 0, `min` the fastest total. `upstream` is "
        "ohsome's `x-envoy-upstream-service-time`, the time behind its envoy proxy.",
        "",
        "| case | variant | results | first | min | total | tcp | tls | ttfb | upstream | download | KB |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    keys = list(dict.fromkeys((r["case"], r["variant"]) for r in rows))
    for case, variant in keys:
        group = [r for r in ok if r["case"] == case and r["variant"] == variant]
        if not group:
            lines.append(f"| {case} | {variant} | failed | | | | | | | | | |")
            continue
        first = next((r["total_ms"] for r in group if r["round"] == 0), None)
        lines.append("| " + " | ".join([
            case, variant, str(group[-1].get("results", "")), fmt(first), fmt(min(r["total_ms"] for r in group)),
            *(fmt(median(group, field)) for field in ("total_ms", "tcp_ms", "tls_ms", "ttfb_ms", "upstream_ms",
                                                      "download_ms")),
            f"{median(group, 'bytes') / 1024:.0f}",
        ]) + " |")
    errors = [r for r in rows if r["status"] != 200]
    if errors:
        lines += ["", "Errors:", ""] + [f"- {r['at']} {r['case']} {r['variant']} round {r['round']}: {r['status']} "
                                         f"{r.get('error', '')[:150]}" for r in errors]
    return "\n".join(lines) + "\n"


def disturbed(row):
    """slow name resolution or connection setup means the client's network, not the service, was the problem"""
    return row["dns_ms"] > MAX_DNS_MS or row["tcp_ms"] > MAX_TCP_MS or row["tls_ms"] > MAX_TLS_MS


def median(rows, field):
    values = [r[field] for r in rows if r.get(field) is not None]
    return statistics.median(values) if values else None


def fmt(value):
    return "" if value is None else f"{value:.0f}"


if __name__ == "__main__":
    main()
