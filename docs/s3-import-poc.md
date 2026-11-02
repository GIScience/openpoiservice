# PoC: import and update POIs from the ohsome-planet Parquet dataset on S3

Status: plan, revised 2026-10-22 with the owner's decisions. Branch: `poc/s3-import`.

## Why

The ohsome team (HeiGIT) offered that openpoiservice could eventually be served from their data. Their stack works like
this: ohsome-planet turns OSM history into GeoParquet on S3 and appends minutely update files, a loader keeps a Citus
database (ohsomedb) current from those files, and the ohsome API queries that database. The API never reads Parquet
per request.

This PoC does the same at POI scale. It fills and updates the ops PostGIS database from the S3 Parquet instead of
Geofabrik PBFs. The API and the POI tables stay as they are. If it works, it replaces imposm.parser (a git fork
that has to be built from source), the Geofabrik file list, `osm/download.py` with pyosmium, the node store,
`src_index` ownership for overlapping extracts, and full rebuilds when the file list changes. Data would be minutes
old instead of days, worldwide.

Background and measurements: kb vault `synthesis/openpoiservice-on-ohsome-data.md`, `entities/ohsome-planet.md`,
`entities/ohsomedb.md`, `projects/openpoiservice/references/ohsome-api-v2-benchmark.md`.

## What we know about the dataset (checked 2026-10-21 and 2026-10-22)

- Endpoint `https://storage.heigit.org`, bucket `heigit-ohsome-planet`, path-style addressing, region `eu-central-1`.
  Authenticated access only.
- Snapshots under `data/v1/`: `global/2026-07-27`, `global/2026-10-05`, `germany/2026-07-24`,
  `karlsruhe-regbez/2025-12-07` (its `updates/` sits next to the snapshot folder, not inside it), `inf/2026-02-27`,
  `inf/2026-05-08`. Also `data/boundaries/` (country polygons).
- `global/2026-10-05/contributions/`: 434 files, 4.0 TB. `node-<n>-0-contribs.parquet` (100 files, 79 GB),
  `way-…` (100, 528 GB), `relation-…` (234, 3.4 TB, because member geometries are included). `state.txt` gives the
  snapshot's end: sequence `7315233`, `2026-10-04T23:59:55Z`. The snapshot was written on 2026-10-15.
- **Each snapshot file mixes all versions** (`status` = `latest`, `history`, `deleted`, `invalid`). There is no separate
  `latest/` folder, although the ohsome-planet docs describe one.
- Files are sorted by `osm_id`. Row groups (about 640k–890k rows, 72 MB) span the whole world, and `status` has no
  column statistics. **So no query can skip data by area or status.** An AOI limits the output, not the scan.
- Columns ops needs: `status`, `osm_type`, `osm_id`, `tags` (map), `centroid{x,y}`.
- **Updates continue the snapshot without a gap:** the first file is `updates/007/315/234.opc.parquet` (sequence
  7315234), uploaded together with the snapshot. Each OSM minute has `<seq>.opc.parquet` + `.state.txt`, where the
  path is the sequence split 3/3/3 (`7315234` → `007/315/234`). `updates/state.txt` names the newest. About 1.2 MB per
  minute (max seen 72 MB). On 2026-10-22 about 25,000 files were pending from the snapshot's end.
- **What an update file holds** (checked on 6 files, about 4,200 elements): for each changed element, exactly one row
  with status `latest`, `deleted` or `invalid`. That row is the element's state at the end of that minute. `history`
  rows appear only for intermediate versions when an element changed more than once in the minute. Several versions can
  share the same `valid_from` second, so ordering by `valid_from` can't find the newest one. The only `invalid` row seen
  had no centroid. Contributions with no tags before or after are left out.
- Measured from the dev machine (DuckDB 1.x, 16 threads): a full status scan of a 102M-row node file took 0.7 s, and
  the ops category filter on `latest` took 3–5 s per file, including the 147 GB relation file. **Extrapolated, not
  measured:** 20–40 min for the planet. It belongs on the server, whose connection to storage.heigit.org is different.
- Volume: node-0 has 44,705 current ops POIs, way-0 18,721, relation-72 5,686 multipolygons. In 100 minutes of
  updates, about 7,200 elements relevant to ops changed.

## Scope of the PoC

- **In scope:** an importer (full load from one snapshot, optionally limited to a bbox), an update command (applies
  up to a configured number of update files per run), a second PostGIS and API instance in Docker Compose, a
  comparison script against the production database, and a runbook with measurements.
- **Out of scope:** removing the PBF importer, scheduling inside the tool, switching snapshots automatically,
  production cut-over, and any change to the API.

## Design

### Configuration

- **Credentials** live in their own env file, `ops_s3_credentials.env` (gitignored, mode 600; a committed
  `ops_s3_credentials.env.sample`), passed in by Compose with `env_file`. The names are the same as in the workspace's
  `heigit-s3.env`, so in the dev container the file can be a gitignored symlink to
  `~/.config/ors-secrets/heigit-s3.env`:

  ```sh
  S3_URL=https://storage.heigit.org
  S3_ACCESS_KEY=…
  S3_SECRET_KEY=…
  ```

- **Settings** are set in `docker-compose.yml` under `environment:`, with defaults. The admin overrides them in the
  checkout's `.env`, which Compose reads for variable substitution and which is gitignored:

  | Variable | Default | Meaning |
  |---|---|---|
  | `OPS_S3_BUCKET` | `heigit-ohsome-planet` | bucket |
  | `OPS_S3_REGION` | `eu-central-1` | region |
  | `OPS_S3_SNAPSHOT` | `data/v1/global/2026-10-05` | base path; `contributions/` and `updates/` below it |
  | `OPS_S3_UPDATES` | `$OPS_S3_SNAPSHOT/updates` | update path; differs for `karlsruhe-regbez` |
  | `OPS_S3_MAX_FILES` | `60` | update files per `s3-update` run (one file is one OSM minute) |
  | `OPS_S3_AOI` | empty | optional bbox `minx,miny,maxx,maxy` |
  | `OPS_S3_DUCKDB_MEMORY` | `8GB` | DuckDB memory limit |
  | `OPS_S3_DUCKDB_THREADS` | `8` | DuckDB threads |

  The memory limit, the thread count and the batch size are starting values, not measurements. The runbook measures
  them.
- Category filters come from the loaded `categories.yml`, through `CategoryTools`, and stored tags come from
  `column_mappings`, as in the PBF import. Nothing new in `ops_settings.yml` except the DB connection of the second
  instance.

### Modules

- `db_import/s3_source.py` opens DuckDB, loads `httpfs`, and creates the S3 secret from the environment. DuckDB wants
  the host without a scheme; the scheme decides `USE_SSL`. The source takes a base URL, so tests pass a local
  directory and need no S3. It builds the SQL:
  - **Category filter:** `tags['k'] IN (…) OR …`, generated from `categories_tools.category_index`.
  - **Rows:** `status = 'latest'` and `centroid IS NOT NULL`, because the staging `geom` is `NOT NULL`. For
    relations, also `tags['type'] = 'multipolygon'`, as the PBF import does.
  - **AOI:** a bbox check on `centroid.x` and `centroid.y` in plain SQL, so no spatial extension is needed.
  - **Output:** Arrow record batches (`fetch_record_batch`), never the whole result.
  - **Schema check:** at the start of every run, it checks that the columns it needs exist with the expected types,
    and fails otherwise. The ohsome-planet format can change between snapshots.
- `db_import/s3_import.py`:
  - **`load_snapshot()`:**
    1. Streams the batches into `PoiObject`, category and tag rows, reusing `get_category` and `column_mappings`.
    2. Calls `staging.copy()` every 10,000 POIs.
    3. Runs `staging.merge(src_index=0)` and writes the state (snapshot, the sequence from `contributions/state.txt`,
       its timestamp) in the same transaction.
    4. Calls `vacuum()`.
  - **`apply_updates(max_files)`:**
    1. Reads the state and refuses to run if there is none, or if it names a different snapshot than
       `OPS_S3_SNAPSHOT`. A forgotten reload then fails loudly instead of mixing two snapshots.
    2. Reads the newest sequence from `updates/state.txt`. The pending files are `state + 1` up to
       `min(newest, state + max_files)`. Their paths are computed from the sequence numbers, not listed. If the first
       one is missing, it fails: the updates were removed, and a new snapshot load is needed.
    3. Reads them with `read_parquet([files…], filename=true) WHERE status <> 'history'` and checks that each file has
       at most one row per `(osm_type, osm_id)`; otherwise it fails. It keeps the row from the highest sequence per
       element.
    4. If that row is `latest`, has a centroid, matches a category, lies in the AOI and (for a relation) is a
       multipolygon, it is staged as an upsert. Otherwise its key goes into a "removed" staging table. That covers
       deletion, `invalid` geometries, losing the POI tags, and moving out of the AOI.
    5. Runs `staging.merge_changes()` and writes the new state (sequence and timestamp of the last file) in the same
       transaction. Then it vacuums.
    6. Logs `applied <n> files up to <seq> (<timestamp>), <m> pending`.
- `db_import/staging.py` gets the `<table>_staging_removed (osm_type, osm_id)` table and `merge_changes()`:
  - It deletes the removed keys; categories and tags follow through `ON DELETE CASCADE`.
  - Then it runs the existing `CHANGE_POIS` and `ADD_POIS` and the category and tag diffs, which are already limited to
    staged POIs.
  - `REMOVE_POIS` is left out, because an update batch holds only the changed elements.
  - `merge()` and `merge_changes()` take the state write as part of their transaction instead of committing on their
    own.
- **State:** a one-row table `<table>_s3_state (snapshot, sequence, sequence_timestamp, updated_at)`, defined in
  `models.py`. `create-db` and `drop-db` handle it with the POI tables, and `TESTING` gives it the `_test` suffix.
  Because the state is written in the data's transaction, the two can't disagree after a crash.
- **Mapping:**
  - `osm_type` node/way/relation → 1/2/3, `centroid` → `geom` (geography point), `src_index` = 0.
  - Multipolygons get `osm_type = 3` with the **relation ID** and the relation's centroid (decided 2026-10-21).
- **`manage.py`:**
  - `s3-import`: full load into the existing tables.
  - `s3-update [--max-files N]` (default `OPS_S3_MAX_FILES`): applies at most N files, then exits.

  Exit codes: **0** caught up, **3** more files pending, **1** error. Scheduling happens outside the tool, for example
  with cron. A catch-up is a shell loop on exit code 3.
- **New snapshots:** the admin changes `OPS_S3_SNAPSHOT` and runs the `s3-init` service, which drops the tables and
  loads the snapshot.
- **Logged per run, to calibrate the defaults:** wall time per phase (DuckDB read, copy, merge, vacuum), rows read and
  POIs staged, removed and changed, and the process's peak memory (`resource.getrusage`, which includes DuckDB, since it
  runs in the process).

### Docker Compose (branch only)

- New services under the Compose profile `s3`, so `docker compose up` alone starts nothing new:
  - `db-s3`: `postgis/postgis:18-3.6`, volume `postgis-s3-data`, no host port;
  - `api-s3`: the same image, settings `ops_settings_docker_s3.yml` (host `db-s3`), host port `5001`;
  - `s3-init`: `S3_INIT_DB=1` → drop-db, create-db, s3-import;
  - `s3-update`: `S3_UPDATE_DB=1` → s3-update. It runs once per invocation, with no restart policy, and passes on the
    exit code.
- `run.sh`: add the modes `S3_INIT_DB` and `S3_UPDATE_DB`, ending with `exec` so the exit code reaches Compose.
- `Dockerfile`: install the `httpfs` extension at build time, so the containers don't need extensions.duckdb.org at
  runtime. Extensions are tied to the DuckDB version, so `duckdb` is pinned exactly.
- `.gitignore`: add `ops_s3_credentials.env`, and add `!ops_settings_docker_s3.yml`, because `ops_settings_docker*.yml`
  is ignored.
- **When running from a second checkout on the production server:** the compose file sets `name: ops`, so always pass
  `-p ops-s3`. Otherwise Compose would treat the production containers and the `postgis-data` volume as its own. Start
  only the `s3` services, so the ports of production's `db` and `api` (5432/5000) aren't requested a second time.

### Comparison with production

`scripts/compare_s3_pois.py <bbox>` connects to both databases (production read-only) and reports, per category: counts
in both, POIs only in one, and the distance distribution for matching `(osm_type, osm_id)`. Then it sends the same
`/pois` requests to `:5000` and `:5001` and compares results and latency.

Expected differences:
- **Multipolygons:** ops PBF stores `osm_type = 3` with the **first outer way's ID** and that way's centroid
  (`parse_osm.parse_ways_second`). The S3 import uses the relation ID and the relation's centroid.
- **Way positions:** ohsome uses the true centroid, ops PBF the mean of the way's nodes.
- **Only in S3:**
  - ways with 1000 or more nodes (the PBF import skips them silently)
  - multipolygons whose first member isn't `outer`
  - multipolygons whose first outer way has categories of its own (the PBF import keeps only the way)
- **Only in PBF:** elements whose geometry ohsome-planet couldn't build (`invalid`).
- **Freshness:** the S3 data is newer.

## Steps (one commit each)

0. Commit the plan on the branch. Done in `e447969`; this revision is its own commit.
1. Dependency and configuration: `duckdb` pinned in `requirements.txt` (resolved for Python 3.11 in the repo's
   image), `ops_s3_credentials.env.sample`, `.gitignore` entries, settings for the second instance.
2. `s3_source.py`: filter SQL, bbox, schema check, batch reader. Tests against small Parquet fixtures that the test
   writes with DuckDB (same schema subset), in a local directory laid out like the bucket, with no S3.
3. State table, `load_snapshot()` and `manage.py s3-import`, tested with the fixtures against PostGIS.
4. `merge_changes()`, `apply_updates()`, `manage.py s3-update` with its exit codes. Tests:
   - create, change tags, lose the category, delete, `invalid`, move out of the bbox, a geometry-only change
   - several versions of one element across files, and a file with `history` rows
   - the `--max-files` limit and the pending count
   - a missing update file, a missing state, and a snapshot mismatch
   - applying the same files twice
5. Compose services, `run.sh` modes, the preinstalled DuckDB extension in the Dockerfile.
6. Comparison script and a README section.

Tests run with `TESTING=True` in the repo's Docker image against PostGIS, with coverage of the new code reported
(`/workspaces/ors/.claude/scripts/ops-test.sh --build`).

## Runbook on the server (production or a production-like server)

```sh
git clone -b poc/s3-import git@github.com:GIScience/openpoiservice.git ops-s3 && cd ops-s3
cp ops_s3_credentials.env.sample ops_s3_credentials.env && chmod 600 ops_s3_credentials.env   # fill in the key
echo 'OPS_S3_AOI=8.57,49.35,8.80,49.47' > .env       # settings; first with a small bbox or karlsruhe-regbez
docker compose -p ops-s3 --profile s3 build
docker compose -p ops-s3 --profile s3 up -d db-s3
docker compose -p ops-s3 --profile s3 run --rm s3-init
docker compose -p ops-s3 --profile s3 up -d api-s3

# catch up: repeat while files are pending (exit code 3)
while docker compose -p ops-s3 --profile s3 run --rm s3-update; [ $? -eq 3 ]; do :; done

# then keep it current, e.g. hourly from the host's crontab
7 * * * * cd /path/to/ops-s3 && docker compose -p ops-s3 --profile s3 run --rm s3-update
```

Measure and write down, in this order:
1. Network: throughput from the server to storage.heigit.org (a single large GET with curl, and DuckDB on one node file).
2. `karlsruhe-regbez` with its own updates: load time, row counts, `s3-update` catching up.
3. `global/2026-10-05` with the Heidelberg bbox. The scan costs the same as the planet, so this measures the scan and
   the comparison tooling.
4. `global/2026-10-05` without a bbox: wall time, peak memory, bytes read (container network I/O, `docker stats`), DB
   size, and the duration of merge and vacuum.
5. Updates: catch-up rate in files per minute from the snapshot end to now, then the lag with hourly runs. Adjust
   `OPS_S3_MAX_FILES` from the measured time per file.
6. Comparison against the production database for a few bboxes (Heidelberg, Berlin Mitte, London), and API latency for
   the requests in the benchmark.

## Decisions (owner)

2026-10-21:
- **Multipolygons use the relation ID** and the relation's centroid. Nobody knows why the PBF import used the outer
  way's ID.
- **Read-only S3 key:** the owner creates one. It goes only into `ops_s3_credentials.env` on the server.
- **New snapshots:** the base path is configuration (`OPS_S3_SNAPSHOT`). An admin changes it when a new snapshot
  should be used, then runs `s3-init`. No automatic detection.

2026-10-22:
- **State in the database**, written in the same transaction as the data, instead of a JSON file.
- **Credentials apart from settings**, under the names of the workspace's `heigit-s3.env`.
- **Scheduling outside the tool.** `s3-update` applies at most `OPS_S3_MAX_FILES` update files per run and reports
  through its exit code whether more are pending. This replaces the configurable update interval and `--follow` from
  2026-10-21.
- **`invalid` elements are dropped**, like deletions.
- **AOI as a bbox only**, with no GeoJSON polygons and no DuckDB spatial extension.

## Still open

- Agreement with the ohsome team on the format (`v1`) and how long old snapshots and their updates stay.
- Querying ohsomedb directly (no ops DB at all) remains an alternative to discuss with them.

## Risks

- The full scan still reads the needed columns of all 4 TB of files on every snapshot load. The transfer volume is
  unknown, so measure it in runbook step 4.
- Regional snapshots don't share a layout (`karlsruhe-regbez/updates/` sits outside the snapshot folder), so
  `OPS_S3_UPDATES` can be set separately.
- A planet load merges all POIs in one transaction (extrapolated from the per-file counts: about 6–7 million POIs).
  While it runs, the staging tables take about as much disk as the live ones.
- An `s3-update` run of 60 files reads about 70 MB (extrapolated from the 1.2 MB median) and changes up to a few
  thousand POIs, which fits into one merge transaction.
- DuckDB memory under the 28 GB Compose limit: cap it with `OPS_S3_DUCKDB_MEMORY` and stream batches.
- The update rule relies on one non-`history` row per element per file. It was seen in 6 files; the importer checks
  it and fails if it doesn't hold.
