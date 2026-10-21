# openpoiservice/server/parser.py
import json
import logging
import os
import time
from collections import deque

import sqlalchemy
from flask_sqlalchemy import SQLAlchemy
from imposm.parser import OSMParser

from openpoiservice.server import db, ops_settings
from openpoiservice.server.db_import import staging
from openpoiservice.server.db_import.models import POIs
from openpoiservice.server.db_import.parse_osm import OsmImporter
from openpoiservice.server.db_import.progress import format_duration, format_size
from openpoiservice.server.utils.decorators import timeit, processify

logger = logging.getLogger(__name__)


# deprecated, remove later
@timeit
@processify
def parse_file(osm_file, osm_file_index=0):
    """
    Imports one osm file through the staging tables, merging it into the live tables in this process.

    :return: 0 if the import succeeded, 1 if it failed
    """
    db.engine.dispose(close=False)
    staging.create()
    succeeded = parse_file_into_staging(osm_file) == 0
    if succeeded:
        staging.merge(osm_file_index)
    staging.drop()
    return 0 if succeeded else 1


# deprecated, remove later
def parse_file_into_staging(osm_file):
    logger.info(f"Starting to read {osm_file}")
    workers = ops_settings["concurrent_workers"]
    osm_importer = OsmImporter()

    logger.info("Parsing and importing nodes...")
    OSMParser(concurrency=workers, nodes_callback=osm_importer.parse_nodes).parse(osm_file)
    if osm_importer.failed:
        logger.warning(f"Parsing {osm_file} failed due to an SQL error, likely caused by duplicate IDs. \n"
                       f"         The file has been marked to be imported later, run update after init completes.")
        del osm_importer
        return 1
    logger.info(f"Found {osm_importer.nodes_cnt} nodes")

    logger.info("Parsing relations...")
    OSMParser(concurrency=workers, relations_callback=osm_importer.parse_relations).parse(osm_file)

    logger.info(f"Found {osm_importer.relations_cnt} ways in relations")

    logger.info("Parsing ways...")
    OSMParser(concurrency=workers, ways_callback=osm_importer.parse_ways).parse(osm_file)
    logger.info(f"Found {osm_importer.ways_cnt} ways (including the ones found in relations)")

    # not needed any more after parsing ways
    del osm_importer.relation_ways

    # Sort the ways by the first osm_id reference, saves memory for parsing coordinates
    osm_importer.process_ways.sort(key=lambda x: x.refs[0])

    # speed optimization, see https://docs.python.org/3/library/collections.html#collections.deque
    osm_importer.process_ways = deque(osm_importer.process_ways)

    # note this will NOT work concurrently due to the algorithm for node id matching
    logger.info("Importing ways...")
    OSMParser(concurrency=1, coords_callback=osm_importer.parse_coords_for_ways).parse(osm_file)
    if osm_importer.failed:
        logger.warning(f"Parsing {osm_file} failed due to an SQL error, likely caused by duplicate IDs. \n"
                       f"         The file has been marked to be imported later, run update after init completes.")
        del osm_importer
        return 1

    if len(osm_importer.process_ways) > 0:
        logger.warning(f"{len(osm_importer.process_ways)} ways not processed due to missing coordinate information, "
                       f"possible pbf file corruption")

    # store remaining data in buffer
    osm_importer.save_buffer()

    logger.info(f"Found {osm_importer.pois_count} POIs")
    logger.info(f"Finished import of {osm_file}")
    del osm_importer
    return 0


@processify
def parse_file_new(osm_file, label=""):
    """
    Copies the POIs of one osm file to the staging tables, in five passes over the file.

    :param label: prefix of the progress log lines, e.g. "[3/12]"
    :return: 0 if the import succeeded, 1 if it failed
    """
    # this runs in a forked process: don't share the parent's pooled connections, a failed transaction here would
    # otherwise break the parent's cleanup after the import
    db.engine.dispose(close=False)

    osm_importer = OsmImporter(label=label)

    def run_pass(number, description, result, **callbacks):
        logger.info(f"{label} pass {number}/5: {description}")
        started = time.monotonic()
        OSMParser(concurrency=ops_settings["concurrent_workers"], **callbacks).parse(osm_file)
        logger.info(f"{label} pass {number}/5 done after {format_duration(time.monotonic() - started)}: {result()}")

    run_pass(1, "importing POIs from nodes", lambda: f"{osm_importer.nodes_cnt:,} POIs from nodes",
             nodes_callback=osm_importer.parse_nodes)
    if osm_importer.failed:
        logger.warning(f"{label} parsing {osm_file} failed, see the error above. The file has been marked to be "
                       f"imported later, run update after init completes.")
        return 1

    run_pass(2, "reading multipolygon relations",
             lambda: f"{osm_importer.relations_cnt:,} outer ways of multipolygons with a category",
             relations_callback=osm_importer.parse_relations)
    run_pass(3, "finding ways with a category", lambda: f"{osm_importer.ways_cnt:,} ways with a category",
             ways_callback=osm_importer.parse_ways_first)
    run_pass(4, "reading node coordinates of those ways",
             lambda: f"coordinates for {len(osm_importer.nodes_store):,} nodes",
             coords_callback=osm_importer.parse_coords_and_store)
    osm_importer.nodes_store.compact()
    run_pass(5, "importing POIs from ways",
             lambda: f"{osm_importer.pois_count - osm_importer.nodes_cnt:,} POIs from ways",
             ways_callback=osm_importer.parse_ways_second)
    if osm_importer.failed:
        logger.warning(f"{label} parsing {osm_file} failed, see the error above. The file has been marked to be "
                       f"imported later, run update after init completes.")
        return 1

    if len(osm_importer.process_ways_set) > 0:
        logger.warning(
            f"{label} {len(osm_importer.process_ways_set):,} ways not processed due to missing coordinate "
            f"information, possible pbf file corruption")

    # store remaining data in buffer
    osm_importer.save_buffer()

    logger.info(f"{label} {osm_importer.pois_count:,} POIs stored in total")
    return 0


# deprecated, remove later
@timeit
def run_import(osm_files_to_import, import_log, db_con):
    try:
        if db_con.session.query(POIs.osm_type, POIs.osm_id).count() > 0:
            logger.info("Data import running in UPDATE MODE")
    except sqlalchemy.exc.ProgrammingError:
        logger.error("Database has not been initialized! Existing.")
        return

    for osm_file_index, osm_file in enumerate(osm_files_to_import):
        if osm_file in import_log and import_log[osm_file] == os.path.getmtime(osm_file):
            logger.info(f"File {osm_file} has not changed since last update, skipping")
            continue

        if parse_file(osm_file, osm_file_index) == 0:
            import_log[osm_file] = os.path.getmtime(osm_file)
        else:
            import_log[osm_file] = 0  # import failed, this file has to be inserted in the next update

    logger.info(f"Import complete.")


def run_import_new(osm_files_to_import, import_log, logfile, db_con):
    try:
        update_mode = db_con.session.query(POIs.osm_type, POIs.osm_id).count() > 0
    except sqlalchemy.exc.ProgrammingError:
        logger.error("Database has not been initialized! Existing.")
        return

    changed_files = []
    for osm_file_index, osm_file in enumerate(osm_files_to_import):
        if osm_file in import_log and import_log[osm_file] == os.path.getmtime(osm_file):
            logger.debug(f"File {osm_file} has not changed since last update, skipping")
        else:
            changed_files.append((osm_file_index, osm_file))
    unchanged_count = len(osm_files_to_import) - len(changed_files)
    logger.info(f"Importing {len(changed_files)} of {len(osm_files_to_import)} files ({unchanged_count} unchanged "
                f"since the last import){', in update mode' if update_mode else ''}")

    started = time.monotonic()
    failed_count = 0
    for number, (osm_file_index, osm_file) in enumerate(changed_files, start=1):
        label = f"[{number}/{len(changed_files)}]"
        logger.info(f"{label} {os.path.relpath(osm_file)} ({format_size(os.path.getsize(osm_file))})")
        file_started = time.monotonic()

        if import_file(osm_file, osm_file_index, db_con, label):
            import_log[osm_file] = os.path.getmtime(osm_file)
            outcome = "succeeded"
        else:
            import_log[osm_file] = 0  # import failed, this file has to be inserted in the next update
            outcome = "failed"
            failed_count += 1

        with open(logfile, "w") as f:
            json.dump(import_log, f, indent=4, sort_keys=True)
            f.close()

        logger.log(logging.INFO if outcome == "succeeded" else logging.WARNING,
                   f"{label} {outcome} after {format_duration(time.monotonic() - file_started)} "
                   f"({format_duration(time.monotonic() - started)} since start)")

    if failed_count < len(changed_files):
        vacuum_started = time.monotonic()
        staging.vacuum()
        logger.info(f"Tables vacuumed and analysed after {format_duration(time.monotonic() - vacuum_started)}")

    logger.info(f"Import finished after {format_duration(time.monotonic() - started)}: "
                f"{len(changed_files) - failed_count} succeeded, {failed_count} failed, {unchanged_count} unchanged")


def import_file(osm_file, osm_file_index, db_con, label=""):
    """
    Imports one osm file. The parser copies its POIs to the staging tables, and only if that succeeded are they
    merged into the live tables, so a failed import never changes data.

    :param label: prefix of the progress log lines, e.g. "[3/12]"
    :return: True if the import succeeded
    """
    staging.create()
    try:
        succeeded = parse_file_new(osm_file, label=label) == 0
    except RuntimeError:
        logger.exception(f"{label} import of {osm_file} crashed")
        succeeded = False

    if succeeded:
        try:
            counts = staging.merge(osm_file_index)
            logger.info(f"{label} {counts.pois_added:,} POIs added, {counts.pois_changed:,} changed and "
                        f"{counts.pois_removed:,} removed; {counts.category_rows:,} category and "
                        f"{counts.tag_rows:,} tag rows changed")
        except sqlalchemy.exc.SQLAlchemyError:
            logger.exception(f"{label} merging {osm_file} into the POI tables failed")
            db_con.session.rollback()
            succeeded = False

    if not succeeded:
        logger.warning(f"{label} import failed, keeping the POIs from the previous import of this file")
    staging.drop()
    return succeeded
