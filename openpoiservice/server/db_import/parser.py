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
from openpoiservice.server.db_import.models import POIs
from openpoiservice.server.db_import.parse_osm import OsmImporter
from openpoiservice.server.db_import.progress import format_duration, format_size
from openpoiservice.server.utils.decorators import timeit, processify

logger = logging.getLogger(__name__)


# deprecated, remove later
@timeit
@processify
def parse_file(osm_file, osm_file_index=0, update_mode=False):
    logger.info(f"Starting to read {osm_file}")
    workers = ops_settings["concurrent_workers"]
    osm_importer = OsmImporter(osm_file_index, update_mode=update_mode)

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
def parse_file_new(osm_file, osm_file_index=0, update_mode=False, label=""):
    """
    Imports the POIs of one osm file in five passes over the file.

    :param label: prefix of the progress log lines, e.g. "[3/12]"
    :return: 0 if the import succeeded, 1 if it failed
    """
    # this runs in a forked process: don't share the parent's pooled connections, a failed transaction here would
    # otherwise break the parent's cleanup after the import
    db.engine.dispose(close=False)

    osm_importer = OsmImporter(osm_file_index, update_mode=update_mode, label=label)

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
        update_mode = False
        prev_poi_count = db_con.session.query(POIs.osm_type, POIs.osm_id).count()
        if prev_poi_count > 0:
            update_mode = True
            logger.info("Data import running in UPDATE MODE")
    except sqlalchemy.exc.ProgrammingError:
        logger.error("Database has not been initialized! Existing.")
        return

    for osm_file_index, osm_file in enumerate(osm_files_to_import):
        if osm_file in import_log and import_log[osm_file] == os.path.getmtime(osm_file):
            logger.info(f"File {osm_file} has not changed since last update, skipping")
            continue

        if update_mode:
            prev_poi_count_file = db_con.session.query(POIs.osm_type, POIs.osm_id).filter_by(
                src_index=osm_file_index).count()
            logger.info(f"Setting flags on {prev_poi_count_file} POIs.")
            db_con.session.query(POIs).filter_by(src_index=osm_file_index).update({POIs.delflag: True})
            db_con.session.commit()

        if parse_file(osm_file, osm_file_index, update_mode=update_mode) == 0:
            import_log[osm_file] = os.path.getmtime(osm_file)
        else:
            import_log[osm_file] = 0  # import failed, this file has to be inserted in the next update

    if update_mode:
        deleted = delete_marked_entries(db_con)
        logger.info(f"{deleted} POIs removed from the OSM data deleted")

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

        if import_file(osm_file, osm_file_index, update_mode, db_con, label):
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

    logger.info(f"Import finished after {format_duration(time.monotonic() - started)}: "
                f"{len(changed_files) - failed_count} succeeded, {failed_count} failed, {unchanged_count} unchanged")


def import_file(osm_file, osm_file_index, update_mode, db_con, label=""):
    """
    Imports one osm file. In update mode, the POIs of the previous import of this file are only deleted if the
    import succeeded; on failure they are kept, so a failed update never removes data.

    :param label: prefix of the progress log lines, e.g. "[3/12]"
    :return: True if the import succeeded
    """
    if update_mode:
        flagged = db_con.session.query(POIs).filter_by(src_index=osm_file_index).update({POIs.delflag: True})
        db_con.session.commit()
        logger.info(f"{label} {flagged:,} POIs of the previous import flagged")

    try:
        succeeded = parse_file_new(osm_file, osm_file_index, update_mode=update_mode, label=label) == 0
    except RuntimeError:
        logger.exception(f"{label} import of {osm_file} crashed")
        succeeded = False

    if update_mode:
        if succeeded:
            deleted = delete_marked_entries(db_con, osm_file_index)
            logger.info(f"{label} {deleted:,} POIs removed from OSM deleted")
        else:
            kept = unmark_entries(db_con, osm_file_index)
            logger.warning(f"{label} import failed, keeping {kept:,} POIs from the previous import of this file")

    return succeeded


def marked_entries(db_con, src_index=None):
    query = db_con.session.query(POIs).filter_by(delflag=True)
    if src_index is not None:
        query = query.filter_by(src_index=src_index)
    return query


def delete_marked_entries(db_con, src_index=None):
    """
    Deletes the POIs still flagged after an import: they are no longer in the OSM data.

    :return: the number of deleted POIs
    """
    deleted = marked_entries(db_con, src_index).delete()
    db_con.session.commit()
    return deleted


def unmark_entries(db_con, src_index):
    """
    :return: the number of POIs unflagged
    """
    kept = marked_entries(db_con, src_index).update({POIs.delflag: False})
    db_con.session.commit()
    return kept
