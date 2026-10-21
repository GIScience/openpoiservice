# PoC: import and update POIs from the ohsome-planet Parquet dataset on S3

Status: plan, 2026-10-21, owner decisions included. Branch: `poc/s3-import`.

## Why

The ohsome team (HeiGIT) offered that openpoiservice could eventually be served from their data. Their stack works like
this: ohsome-planet turns OSM history into GeoParquet on S3 and appends minutely update files, a loader keeps a Citus
database (ohsomedb) current from those files, and the ohsome API queries that database. The API never reads Parquet
per request.

This PoC does the same at POI scale. It fills and updates the ops PostGIS database from the S3 Parquet instead of
Geofabrik PBFs. The API and the database schema stay as they are. If it works, it replaces imposm.parser (a git fork
that has to be built from source), the Geofabrik file list, `osm/download.py` with pyosmium, the node store,
`src_index` ownership for overlapping extracts, and full rebuilds when the file list changes. Data would be minutes
old instead of days, worldwide.

Background and measurements: kb vault `synthesis/openpoiservice-on-ohsome-data.md`, `entities/ohsome-planet.md`,
`entities/ohsomedb.md`, `projects/openpoiservice/references/ohsome-api-v2-benchmark.md`.

## What we know about the dataset (checked 2026-10-21)

- Endpoint `https://storage.heigit.org`, bucket `heigit-ohsome-planet`, path-style addressing, region `eu-central-1`.
  Authenticated access only.
- Snapshots under `data/v1/`: `global/2026-07-27`, `global/2026-10-05`, `germany/2026-07-24`,
  `karlsruhe-regbez/2025-12-07` (its `updates/` sits next to the snapshot folder, not inside it), `inf/2026-02-27`,
  `inf/2026-05-08`. Also `data/boundaries/` (country polygons).
- `global/2026-10-05/contributions/`: 434 files, 4.0 TB. `node-<n>-0-contribs.parquet` (100 files, 79 GB),
  `way-…` (100, 528 GB), `relation-…` (234, 3.4 TB, because member geometries are included). `state.txt` gives the
  snapshot's end: sequence `7315233`, `2026-10-04T23:59:55Z`. The snapshot was written on 2026-10-15.
- **Each file mixes all versions** (`status` = `latest`, `history`, `deleted`, `invalid`). There is no separate `latest/`
  folder, although the ohsome-planet docs describe one.
- Files are sorted by `osm_id`. Row groups (about 640k–890k rows, 72 MB) span the whole world, and `status` has no
  column statistics. **So no query can skip data by area or status.** An AOI limits the output, not the scan.
- Columns ops needs: `status`, `osm_type`, `osm_id`, `tags` (map), `centroid{x,y}`, `geometry_type`. Others not
  needed: `valid_from`, `osm_version`, `countries`.
- `updates/007/338/593.opc.parquet` + `.state.txt` per OSM minute, `updates/state.txt` and `state.csv` point at the
  newest. About 1.2 MB per minute (max seen 34 MB). Rows are new current versions, the versions they replace, deletions,
  and ways or relations whose geometry changed because a member moved. Contributions with no tags before or after are
  left out.
- Measured from the dev machine (DuckDB 1.x, 16 threads): a full status scan of a 102M-row node file took 0.7 s, and
  the ops category filter on `latest` took 3–5 s per file, including the 147 GB relation file. That gives an estimate
  of 20–40 min for the planet. **Not measured: a full planet run.** It belongs on the server, whose connection to
  storage.heigit.org is different.
- Volume: node-0 has 44,705 current ops POIs, way-0 18,721, relation-72 5,686 multipolygons. In 100 minutes of
  updates, about 7,200 elements relevant to ops changed.

## Scope of the PoC

- **In scope:** an importer (full load from one snapshot, optionally limited to an AOI), an updater (applies update
  files from a stored sequence onwards), a second PostGIS and API instance in Docker Compose, a comparison script
  against the production database, and a runbook with measurements.
- **Out of scope:** removing the PBF importer, switching snapshots automatically, production cut-over, and any change
  to the API.

## Design

### Configuration

- `ops_s3.env` (gitignored; `ops_s3.env.sample` committed), passed in by Compose with `env_file`:

  ```sh
  S3_ENDPOINT=storage.heigit.org
  S3_ACCESS_KEY=…
  S3_SECRET_KEY=…
  S3_REGION=eu-central-1
  S3_BUCKET=heigit-ohsome-planet
  OPS_S3_SNAPSHOT=data/v1/global/2026-10-05      # base path: contributions/ and updates/ below it
  OPS_S3_UPDATES=                                # defaults to $OPS_S3_SNAPSHOT/updates (karlsruhe-regbez differs)
  OPS_S3_UPDATE_INTERVAL=3600                    # seconds between update batches; 60 gives minutely updates
  OPS_S3_AOI=8.57,49.35,8.80,49.47               # optional: bbox minx,miny,maxx,maxy or a path to a GeoJSON polygon
  OPS_S3_DUCKDB_MEMORY=8GB
  OPS_S3_DUCKDB_THREADS=8
  ```

- Category filters come from the loaded `categories.yml`, through `CategoryTools`, and stored tags come from
  `column_mappings`, as in the PBF import. Nothing new in `ops_settings.yml` except the DB connection of the second
  instance.

### Modules

- `db_import/s3_source.py`: opens DuckDB, loads `httpfs` and `spatial`, creates the S3 secret from the environment, and
  builds the SQL:
  - category filter: `tags['k'] IN (…) OR …` from `categories_tools.category_index`;
  - `status = 'latest'`, and for relations `tags['type'] = 'multipolygon'`, as the PBF import does;
  - AOI: a bbox check on `centroid`, or `ST_Within(ST_Point(centroid.x, centroid.y), <polygon>)`;
  - returns Arrow record batches (`fetch_record_batch`), never the whole result.
- `db_import/s3_import.py`:
  - `load_snapshot()`: stream the batches → `PoiObject` / category / tag rows (reusing `get_category` and
    `column_mappings`) → `staging.copy()` every 10,000 POIs → `staging.merge(src_index=0)` → `vacuum()`. Because the
    merge removes POIs of that `src_index` that aren't staged, a reload of the same or a newer snapshot cleans up
    anything that disappeared. It then writes the state.
  - `apply_updates(max_files)`: read the stored sequence and the remote `updates/state.txt`, then process the pending
    files in order and in batches (default 60). Per batch:
    1. `read_parquet([files…], filename=true)`. Keep the last row per `(osm_type, osm_id)`, ordered by file sequence,
       then `valid_from`, then `osm_minor_version`.
    2. If that row is `latest`, matches a category, lies in the AOI and (for a relation) is a multipolygon, stage it
       as an upsert. Otherwise put its key in a "removed" staging table. That covers deletion, losing the POI tags,
       and moving out of the AOI.
    3. `staging.merge_changes()` in one transaction, then advance the stored sequence. Applying a batch twice is
       harmless, because everything is keyed by `(osm_type, osm_id)`.
- `db_import/staging.py`: add the `<table>_staging_removed (osm_type, osm_id)` table and `merge_changes()`. It deletes
  the removed keys (categories and tags follow through `ON DELETE CASCADE`), then runs the existing `CHANGE_POIS` /
  `ADD_POIS` and the category and tag diffs. Those are already limited to staged POIs. `REMOVE_POIS` is left out,
  because an update batch holds only the changed elements.
- State: `s3-import-state.json` next to `import-log.json`, containing `{snapshot, sequence, timestamp}`. After a
  snapshot load, the sequence is the snapshot's `contributions/state.txt` value (7315233 for 2026-10-05).
- Mapping: `osm_type` node/way/relation → 1/2/3, `centroid` → `geom` (geography point), `src_index` = 0.
- `manage.py`: `s3-import` (full load), `s3-update [--max-files N] [--follow]`. Without `--follow` it applies the
  pending files once and exits, which suits cron. With `--follow` it repeats every `OPS_S3_UPDATE_INTERVAL` seconds.
- New snapshots: the admin changes `OPS_S3_SNAPSHOT` and runs `s3-init`. The importer refuses to apply updates when
  the stored state names a different snapshot than the configured one, so a forgotten reload fails loudly instead of
  mixing two snapshots.
- Mapping of multipolygons: `osm_type = 3` with the **relation ID** and the relation's centroid (decided 2026-10-21).

### Docker Compose (branch only)

- New services under the Compose profile `s3`, so `docker compose up` alone starts nothing new:
  - `db-s3`: `postgis/postgis:18-3.6`, volume `postgis-s3-data`, no host port, or `127.0.0.1:5433`;
  - `api-s3`: the same image, settings `ops_settings_docker_s3.yml` (host `db-s3`), host port `5001`;
  - `s3-init`: `S3_INIT_DB=1` → drop-db, create-db, s3-import;
  - `s3-update`: `S3_UPDATE_DB=1` → s3-update `--follow`, `restart: unless-stopped`. It runs one batch with every
    pending file every `OPS_S3_UPDATE_INTERVAL` seconds (default 3600).
- `run.sh`: add the modes `S3_INIT_DB` and `S3_UPDATE_DB`.
- `Dockerfile`: install the DuckDB extensions at build time (`INSTALL httpfs; INSTALL spatial;`), so the containers
  don't need extensions.duckdb.org at runtime.
- **When running from a second checkout on the production server:** the compose file sets `name: ops`, so always pass
  `-p ops-s3`. Otherwise Compose would treat the production containers and the `postgis-data` volume as its own. Start
  only the `s3` services, so the ports of production's `db`/`api` (5432/5000) aren't requested a second time.

### Comparison with production

`scripts/compare_s3_pois.py <aoi>` connects to both databases (production read-only) and reports, per category: counts
in both, POIs only in one, and the distance distribution for matching `(osm_type, osm_id)`. Then it sends the same
`/pois` requests to `:5000` and `:5001` and compares results and latency. Expected differences:
- **Multipolygons:** ops PBF stores `osm_type = 3` with the **first outer way's ID** and that way's centroid
  (`parse_osm.parse_ways_second`). The S3 import uses the relation ID and the relation's centroid.
- **Way positions:** ohsome uses the true centroid, ops PBF the mean of the way's nodes.
- **Freshness:** the S3 data is newer.

## Steps (one commit each)

0. Commit this plan on the branch.
1. Dependency and configuration: `duckdb` pinned in `requirements.txt` (resolved in a clean venv),
   `ops_s3.env.sample`, `.gitignore` entries, settings for the second instance.
2. `s3_source.py`: filter SQL, AOI, batch reader. Tests against a small Parquet fixture written by DuckDB in the test
   (same schema subset), with no S3.
3. `load_snapshot()` and `manage.py s3-import`, tested with the fixture against PostGIS.
4. `merge_changes()`, `apply_updates()`, `manage.py s3-update`. Tests: create, change tags, lose the category, delete,
   move out of the AOI, a geometry-only change, applying a batch twice.
5. Compose services, `run.sh` modes, preinstalled DuckDB extensions in the Dockerfile.
6. Comparison script and a README section.

Tests run with `TESTING=True` in the repo's Docker image against PostGIS, with coverage of the new code reported
(`/workspaces/ops/.claude/scripts/ops-test.sh --build`).

## Runbook on the server (production or a production-like server)

```sh
git clone -b poc/s3-import git@github.com:GIScience/openpoiservice.git ops-s3 && cd ops-s3
cp ops_s3.env.sample ops_s3.env && chmod 600 ops_s3.env   # fill in the key
docker compose -p ops-s3 --profile s3 build
docker compose -p ops-s3 --profile s3 up -d db-s3
docker compose -p ops-s3 --profile s3 run --rm s3-init     # first with a small AOI or karlsruhe-regbez
docker compose -p ops-s3 --profile s3 up -d api-s3 s3-update
```

Measure and write down, in this order:
1. Network: throughput from the server to storage.heigit.org (a single large GET with curl, and DuckDB on one node file).
2. `karlsruhe-regbez` with its own updates: load time, row counts, `s3-update` catching up.
3. `global/2026-10-05` with the Heidelberg AOI. The scan costs the same as the planet, so this measures the scan and
   the comparison tooling.
4. `global/2026-10-05` without an AOI: wall time, peak memory (DuckDB and Python), bytes read, DB size, and the
   duration of merge and vacuum.
5. Updates: catch-up rate in files per minute from the snapshot end to now, then steady-state lag.
6. Comparison against the production database for a few AOIs (Heidelberg, Berlin Mitte, London), and API latency for the
   requests in the benchmark.

## Decisions (owner, 2026-10-21)

- **Multipolygons use the relation ID** and the relation's centroid. Nobody knows why the PBF import used the outer
  way's ID.
- **Read-only S3 key:** the owner creates one (planned for 2026-10-22). It goes only into `ops_s3.env` on the server.
- **Update interval:** configurable (`OPS_S3_UPDATE_INTERVAL`), default an hourly batch.
- **New snapshots:** the base path is configuration (`OPS_S3_SNAPSHOT`). An admin changes it when a new snapshot
  should be used, then runs `s3-init`. No automatic detection.

## Still open

- Agreement with the ohsome team on the format (`v1`) and how long old snapshots and their updates stay.
- Querying ohsomedb directly (no ops DB at all) remains an alternative to discuss with them.

## Risks

- The full scan still reads the needed columns of all 4 TB of files on every snapshot load. The transfer volume is
  unknown, so measure it in runbook step 4.
- Regional snapshots don't share a layout (`karlsruhe-regbez/updates/` sits outside the snapshot folder), so
  `OPS_S3_UPDATES` can be set separately.
- Hourly batches hold about 60 files (roughly 70 MB) and up to a few thousand changed POIs, which is well within one
  merge transaction.
- DuckDB memory under the 28 GB Compose limit: cap it with `OPS_S3_DUCKDB_MEMORY` and stream batches.
- The ohsome-planet format can change between snapshots, so check the schema at the start of every load.
