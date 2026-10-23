"""Response times of openpoiservice itself, without the API gateway in front of it.

Sends POI requests for about 100 places around the world (city centres, small towns, villages, places without any
POIs), several POI sets each (one category up to the 111-category shops group, and all categories), with three
geometries each: a 500 m and a 2000 m buffer around a point, and a 2 km x 2 km bbox.

Every request is sent twice in a row: `first` may find the database pages on disk, `repeat` finds them in memory. A
few `request=list` calls at the start measure the app's floor (no database). Requests go out one at a time, each on a
new connection, and are timed to the first byte and to the end of the body.

Only the Python standard library is needed, so it runs with the host's python3:
    python3 scripts/ops_local_bench.py                    # http://localhost:5005/pois
    python3 scripts/ops_local_bench.py --url http://localhost:5000/pois --sets banks,all --geometries buffer2000
    python3 scripts/ops_local_bench.py --summarise ops-bench-20261023-1700    # rebuild the summary only
A full run is about 3,200 requests per round. Ctrl-C stops it and still writes the summary of what ran. Results go to
<out>/results.jsonl and <out>/summary.md. For a URL behind the API gateway, put the key in $OPS_API_KEY; the gateway
allows only 50 /pois requests per day per key.
"""
import argparse
import http.client
import json
import math
import os
import socket
import statistics
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

# (name, kind, lon, lat); kind groups the summary: city, town, rural, empty
LOCATIONS = [
    # Europe
    ("Berlin", "city", 13.4050, 52.5200), ("Paris", "city", 2.3522, 48.8566), ("London", "city", -0.1276, 51.5072),
    ("Madrid", "city", -3.7038, 40.4168), ("Rome", "city", 12.4964, 41.9028), ("Vienna", "city", 16.3738, 48.2082),
    ("Amsterdam", "city", 4.9041, 52.3676), ("Brussels", "city", 4.3517, 50.8503), ("Prague", "city", 14.4378, 50.0755),
    ("Warsaw", "city", 21.0122, 52.2297), ("Stockholm", "city", 18.0686, 59.3293), ("Oslo", "city", 10.7522, 59.9139),
    ("Helsinki", "city", 24.9384, 60.1699), ("Copenhagen", "city", 12.5683, 55.6761),
    ("Lisbon", "city", -9.1393, 38.7223), ("Athens", "city", 23.7275, 37.9838), ("Budapest", "city", 19.0402, 47.4979),
    ("Dublin", "city", -6.2603, 53.3498), ("Zurich", "city", 8.5417, 47.3769), ("Munich", "city", 11.5820, 48.1351),
    ("Hamburg", "city", 9.9937, 53.5511), ("Barcelona", "city", 2.1734, 41.3851), ("Milan", "city", 9.1900, 45.4642),
    ("Istanbul", "city", 28.9784, 41.0082), ("Moscow", "city", 37.6173, 55.7558), ("Kyiv", "city", 30.5234, 50.4501),
    ("Kraków", "city", 19.9450, 50.0647), ("Heidelberg", "city", 8.6935, 49.4097), ("Bremen", "city", 8.8017, 53.0793),
    ("Freiburg", "city", 7.8421, 47.9990), ("Reykjavik", "town", -21.9426, 64.1466),
    ("Tromsø", "town", 18.9553, 69.6492), ("Schwetzingen", "town", 8.5735, 49.3833),
    ("Wiesloch", "town", 8.6984, 49.2948), ("Hallstatt", "town", 13.6493, 47.5622),
    ("Odenwald village", "rural", 8.8000, 49.4850), ("Black Forest", "rural", 8.1000, 48.0500),
    # Americas
    ("New York Midtown", "city", -73.9857, 40.7484), ("San Francisco", "city", -122.4194, 37.7749),
    ("Los Angeles", "city", -118.2437, 34.0522), ("Chicago", "city", -87.6298, 41.8781),
    ("Toronto", "city", -79.3832, 43.6532), ("Montreal", "city", -73.5673, 45.5017),
    ("Mexico City", "city", -99.1332, 19.4326), ("São Paulo", "city", -46.6333, -23.5505),
    ("Rio de Janeiro", "city", -43.1729, -22.9068), ("Buenos Aires", "city", -58.3816, -34.6037),
    ("Santiago", "city", -70.6693, -33.4489), ("Lima", "city", -77.0428, -12.0464), ("Bogotá", "city", -74.0721, 4.7110),
    ("Vancouver", "city", -123.1207, 49.2827), ("Seattle", "city", -122.3321, 47.6062),
    ("Boston", "city", -71.0589, 42.3601), ("Washington", "city", -77.0369, 38.9072), ("Miami", "city", -80.1918, 25.7617),
    ("Havana", "city", -82.3666, 23.1136), ("Anchorage", "town", -149.9003, 61.2181),
    ("Bozeman", "town", -111.0429, 45.6770), ("Ushuaia", "town", -68.3030, -54.8019),
    ("Iowa farmland", "rural", -93.5000, 42.0000), ("Amazon rainforest", "empty", -63.0000, -5.0000),
    # Asia
    ("Tokyo", "city", 139.7671, 35.6812), ("Osaka", "city", 135.5023, 34.6937), ("Kyoto", "city", 135.7681, 35.0116),
    ("Seoul", "city", 126.9780, 37.5665), ("Beijing", "city", 116.4074, 39.9042), ("Shanghai", "city", 121.4737, 31.2304),
    ("Hong Kong", "city", 114.1694, 22.3193), ("Taipei", "city", 121.5654, 25.0330),
    ("Singapore", "city", 103.8519, 1.2903), ("Bangkok", "city", 100.5018, 13.7563),
    ("Kuala Lumpur", "city", 101.6869, 3.1390), ("Jakarta", "city", 106.8456, -6.2088),
    ("Manila", "city", 120.9842, 14.5995), ("Hanoi", "city", 105.8342, 21.0278), ("Delhi", "city", 77.2090, 28.6139),
    ("Mumbai", "city", 72.8777, 19.0760), ("Bangalore", "city", 77.5946, 12.9716),
    ("Kathmandu", "city", 85.3240, 27.7172), ("Dubai", "city", 55.2708, 25.2048), ("Tehran", "city", 51.3890, 35.6892),
    ("Tel Aviv", "city", 34.7818, 32.0853), ("Riyadh", "city", 46.6753, 24.7136), ("Almaty", "city", 76.8512, 43.2220),
    ("Ulaanbaatar", "city", 106.9057, 47.8864), ("Takayama", "town", 137.2522, 36.1461),
    ("Gobi desert", "empty", 105.0000, 43.0000),
    # Africa
    ("Cairo", "city", 31.2357, 30.0444), ("Lagos", "city", 3.3792, 6.5244), ("Nairobi", "city", 36.8219, -1.2921),
    ("Johannesburg", "city", 28.0473, -26.2041), ("Cape Town", "city", 18.4241, -33.9249),
    ("Casablanca", "city", -7.5898, 33.5731), ("Addis Ababa", "city", 38.7578, 8.9806), ("Accra", "city", -0.1870, 5.6037),
    ("Dakar", "city", -17.4677, 14.7167), ("Kinshasa", "city", 15.2663, -4.4419), ("Tunis", "city", 10.1815, 36.8065),
    ("Kampala", "city", 32.5825, 0.3476), ("Sahara", "empty", 2.0000, 23.0000),
    # Oceania
    ("Sydney", "city", 151.2093, -33.8688), ("Melbourne", "city", 144.9631, -37.8136),
    ("Auckland", "city", 174.7633, -36.8485), ("Perth", "city", 115.8605, -31.9505),
    ("Wellington", "city", 174.7762, -41.2865), ("Alice Springs", "town", 133.8807, -23.6980),
    ("Queenstown NZ", "town", 168.6626, -45.0312), ("Atlantic Ocean", "empty", -30.0000, 0.0000),
]

# ops allows at most 5 category ids or group ids per request; ids from categories.yml
POI_SETS = {
    "banks": {"category_ids": [192]},
    "bank_atm": {"category_ids": [192, 191]},
    "pharmacies": {"category_ids": [208]},
    "restaurants": {"category_ids": [570]},
    "sustenance5": {"category_ids": [570, 564, 561, 569, 566]},  # restaurant, cafe, bar, pub, fast_food
    "supermarket_bakery": {"category_ids": [518, 426]},
    "school_kindergarten": {"category_ids": [156, 153]},
    "group_sustenance": {"category_group_ids": [560]},  # 10 categories
    "group_shops": {"category_group_ids": [420]},  # 111 categories
    "all": None,  # no filter: every category
}
GEOMETRIES = ("buffer500", "buffer2000", "bbox2km")
LIMIT = 2000  # ops' maximum response size
FLOOR_REQUESTS = 10


def main():
    args = parse_args()
    if args.summarise:
        rows = [json.loads(line) for line in open(os.path.join(args.summarise, "results.jsonl"))]
        write_summary(args.summarise, rows, args.summarise)
        return
    sets = args.sets or list(POI_SETS)
    geometries = args.geometries or list(GEOMETRIES)
    locations = LOCATIONS[:args.locations] if args.locations else LOCATIONS
    plan = [(location, poi_set, geometry) for location in locations for poi_set in sets for geometry in geometries]
    total = FLOOR_REQUESTS + len(plan) * (1 + args.repeats)
    print(f"{total} requests to {args.url}: {len(locations)} places x {len(sets)} POI sets x {len(geometries)} "
          f"geometries, each sent {1 + args.repeats} times", file=sys.stderr)
    if args.dry_run:
        return

    os.makedirs(args.out, exist_ok=True)
    client = Client(args.url, os.environ.get("OPS_API_KEY"))
    rows = []
    started = time.time()
    try:
        with open(os.path.join(args.out, "results.jsonl"), "w") as out:
            for i in range(FLOOR_REQUESTS):
                record(out, rows, client.post({"request": "list"}), place="-", kind="floor", poi_set="list",
                       geometry="-", attempt=i)
            for n, (location, poi_set, geometry) in enumerate(plan, 1):
                body = request_body(location, poi_set, geometry)
                for attempt in range(1 + args.repeats):
                    record(out, rows, client.post(body), place=location[0], kind=location[1], poi_set=poi_set,
                           geometry=geometry, attempt=attempt)
                if n % 50 == 0 or n == len(plan):
                    progress(n, len(plan), started, rows)
    except KeyboardInterrupt:
        print("\ninterrupted; summarising what ran", file=sys.stderr)
    write_summary(args.out, rows, args.url)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--url", default="http://localhost:5005/pois")
    p.add_argument("--out", default="ops-bench-" + datetime.now().strftime("%Y%m%d-%H%M"))
    p.add_argument("--sets", type=lambda s: s.split(","), help="subset of: " + ", ".join(POI_SETS))
    p.add_argument("--geometries", type=lambda s: s.split(","), help="subset of: " + ", ".join(GEOMETRIES))
    p.add_argument("--locations", type=int, help=f"only the first N of the {len(LOCATIONS)} places")
    p.add_argument("--repeats", type=int, default=1, help="extra sends of each request after the first (default 1)")
    p.add_argument("--dry-run", action="store_true", help="print the request count only")
    p.add_argument("--summarise", metavar="DIR", help="only rebuild DIR/summary.md from DIR/results.jsonl")
    args = p.parse_args()
    unknown = (set(args.sets or ()) - set(POI_SETS)) | (set(args.geometries or ()) - set(GEOMETRIES))
    if unknown:
        p.error("unknown POI sets or geometries: " + ", ".join(sorted(unknown)))
    return args


def request_body(location, poi_set, geometry):
    _, _, lon, lat = location
    body = {"request": "pois", "geometry": geometry_of(lon, lat, geometry), "limit": LIMIT}
    if POI_SETS[poi_set]:
        body["filters"] = POI_SETS[poi_set]
    return body


def geometry_of(lon, lat, geometry):
    if geometry.startswith("buffer"):
        return {"geojson": {"type": "Point", "coordinates": [lon, lat]}, "buffer": int(geometry[len("buffer"):])}
    half = 1000  # metres: a 2 km x 2 km box
    dlat = half / 111320
    dlon = half / (111320 * math.cos(math.radians(lat)))
    return {"bbox": [[round(lon - dlon, 6), round(lat - dlat, 6)], [round(lon + dlon, 6), round(lat + dlat, 6)]]}


class Client:
    """POSTs JSON on a new connection per request, timed to the first byte and to the end of the body."""

    def __init__(self, url, key=None):
        parts = urlsplit(url)
        self.https = parts.scheme == "https"
        self.host = parts.hostname
        self.port = parts.port or (443 if self.https else 80)
        self.path = parts.path or "/"
        self.headers = {"Content-Type": "application/json"}
        if key:
            self.headers["Authorization"] = key

    def post(self, body):
        payload = json.dumps(body).encode()
        connection_class = http.client.HTTPSConnection if self.https else http.client.HTTPConnection
        start = time.perf_counter()
        try:
            connection = connection_class(self.host, self.port, timeout=300)
            connection.request("POST", self.path, payload, self.headers)
            response = connection.getresponse()
            first_byte = time.perf_counter()
            data = response.read()
            end = time.perf_counter()
            connection.close()
        except (OSError, http.client.HTTPException) as e:
            return {"status": 0, "error": f"{type(e).__name__}: {e}", "total_ms": ms(start, time.perf_counter())}
        row = {"status": response.status, "ttfb_ms": ms(start, first_byte), "total_ms": ms(start, end),
               "bytes": len(data)}
        if response.status == 200 and body["request"] == "pois":
            row["features"] = len(json.loads(data).get("features", []))
        elif response.status != 200:
            row["error"] = data[:300].decode(errors="replace")
        return row


def record(out, rows, row, **fields):
    row.update(fields)
    row["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(json.dumps(row, ensure_ascii=False), file=out, flush=True)
    rows.append(row)


def progress(done, total, started, rows):
    elapsed = time.time() - started
    recent = [r["total_ms"] for r in rows[-100:] if r["status"] == 200]
    print(f"{done}/{total} done, {elapsed / 60:.1f} min, about {elapsed / done * (total - done) / 60:.0f} min left, "
          f"median of the last 100: {statistics.median(recent) if recent else 0:.0f} ms", file=sys.stderr)


def ms(start, end):
    return round((end - start) * 1000, 1)


def write_summary(directory, rows, target):
    summary = summarise(rows, target)
    with open(os.path.join(directory, "summary.md"), "w") as f:
        f.write(summary)
    print(summary)


def summarise(rows, target):
    ok = [r for r in rows if r["status"] == 200]
    pois = [r for r in ok if r["kind"] != "floor"]
    first = [r for r in pois if r["attempt"] == 0]
    repeat = [r for r in pois if r["attempt"] > 0]
    lines = [
        "# openpoiservice response times without the gateway",
        "",
        f"{target}, {rows[0]['at']} to {rows[-1]['at']}, from {socket.gethostname()}. {len(rows)} requests, "
        f"{len(rows) - len(ok)} failed. Times in ms. `first` is the first send of a request, `repeat` the sends "
        "right after it (database pages already in memory).",
        "",
        "## Overall",
        "",
        "| | n | median | p90 | p99 | max |",
        "|---|---:|---:|---:|---:|---:|",
        stats_row("floor (`request=list`, no database)", [r for r in ok if r["kind"] == "floor"]),
        stats_row("first", first),
        stats_row("repeat", repeat),
        "",
        "## By POI set and geometry (repeat sends)",
        "",
        "| POI set | geometry | n | median features | median | p90 | max | median first |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for poi_set in dict.fromkeys(r["poi_set"] for r in pois):
        for geometry in dict.fromkeys(r["geometry"] for r in pois):
            group = [r for r in repeat if r["poi_set"] == poi_set and r["geometry"] == geometry]
            firsts = [r for r in first if r["poi_set"] == poi_set and r["geometry"] == geometry]
            if group:
                lines.append(f"| {poi_set} | {geometry} | {len(group)} | {fmt(median(group, 'features'))} | "
                             f"{fmt(median(group, 'total_ms'))} | {fmt(percentile(group, 90))} | "
                             f"{fmt(max(r['total_ms'] for r in group))} | {fmt(median(firsts, 'total_ms'))} |")
    lines += [
        "",
        "## By number of POIs returned (repeat sends)",
        "",
        "| features | n | median | p90 | max |",
        "|---|---:|---:|---:|---:|",
    ]
    for low, high in ((0, 0), (1, 10), (11, 100), (101, 500), (501, 1999), (2000, 2000)):
        group = [r for r in repeat if low <= r.get("features", -1) <= high]
        label = str(low) if low == high else f"{low}–{high}"
        if group:
            lines.append(f"| {label} | {len(group)} | {fmt(median(group, 'total_ms'))} | "
                         f"{fmt(percentile(group, 90))} | {fmt(max(r['total_ms'] for r in group))} |")
    lines += ["", "## By kind of place (repeat sends)", "", "| kind | n | median | p90 | max |", "|---|---:|---:|---:|---:|"]
    for kind in ("city", "town", "rural", "empty"):
        group = [r for r in repeat if r["kind"] == kind]
        if group:
            lines.append(f"| {kind} | {len(group)} | {fmt(median(group, 'total_ms'))} | {fmt(percentile(group, 90))} | "
                         f"{fmt(max(r['total_ms'] for r in group))} |")
    lines += ["", "## Slowest 20 (any send)", "", "| place | POI set | geometry | send | features | ms |",
              "|---|---|---|---:|---:|---:|"]
    for r in sorted(pois, key=lambda r: -r["total_ms"])[:20]:
        lines.append(f"| {r['place']} | {r['poi_set']} | {r['geometry']} | {r['attempt']} | {r.get('features', '')} | "
                     f"{r['total_ms']:.0f} |")
    errors = [r for r in rows if r["status"] != 200]
    if errors:
        lines += ["", f"## Errors ({len(errors)}, first 20)", ""]
        lines += [f"- {r['at']} {r['place']} {r['poi_set']} {r['geometry']}: {r['status']} "
                  f"{r.get('error', '')[:150]}" for r in errors[:20]]
    return "\n".join(lines) + "\n"


def stats_row(label, rows):
    if not rows:
        return f"| {label} | 0 | | | | |"
    return (f"| {label} | {len(rows)} | {fmt(median(rows, 'total_ms'))} | {fmt(percentile(rows, 90))} | "
            f"{fmt(percentile(rows, 99))} | {fmt(max(r['total_ms'] for r in rows))} |")


def median(rows, field):
    values = [r[field] for r in rows if r.get(field) is not None]
    return statistics.median(values) if values else None


def percentile(rows, p):
    values = sorted(r["total_ms"] for r in rows)
    if len(values) < 2:
        return values[0] if values else None
    return statistics.quantiles(values, n=100, method="inclusive")[p - 1]


def fmt(value):
    return "" if value is None else f"{value:.0f}"


if __name__ == "__main__":
    main()
