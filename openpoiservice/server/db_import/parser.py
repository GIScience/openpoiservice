# openpoiservice/server/parser.py
import json
import logging
import os
from collections import deque

import sqlalchemy
from flask_sqlalchemy import SQLAlchemy
from imposm.parser import OSMParser

from openpoiservice.server import db, ops_settings
from openpoiservice.server.db_import.models import POIs
from openpoiservice.server.db_import.parse_osm import OsmImporter
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


@timeit
@processify
def parse_file_new(osm_file, osm_file_index=0, update_mode=False):
    # this runs in a forked process: don't share the parent's pooled connections, a failed transaction here would
    # otherwise break the parent's cleanup after the import
    db.engine.dispose(close=False)

    logger.info(f"Starting to read {osm_file}")
    workers = ops_settings["concurrent_workers"]
    osm_importer = OsmImporter(osm_file_index, update_mode=update_mode)

    logger.info("Parsing and importing nodes...")
    OSMParser(concurrency=workers, nodes_callback=osm_importer.parse_nodes).parse(osm_file)
    if osm_importer.failed:
        logger.warning(f"Parsing {osm_file} failed, see the error above. \n"
                       f"         The file has been marked to be imported later, run update after init completes.")
        del osm_importer
        return 1
    logger.info(f"Found {osm_importer.nodes_cnt} nodes")

    logger.info("Parsing relations...")
    OSMParser(concurrency=workers, relations_callback=osm_importer.parse_relations).parse(osm_file)

    logger.info(f"Found {osm_importer.relations_cnt} ways in relations")

    logger.info("Parsing ways (1st pass)...")
    OSMParser(concurrency=workers, ways_callback=osm_importer.parse_ways_first).parse(osm_file)
    logger.info(f"Found {osm_importer.ways_cnt} ways (including the ones found in relations)")

    logger.info("Parsing coords ...")
    OSMParser(concurrency=workers, coords_callback=osm_importer.parse_coords_and_store).parse(osm_file)

    osm_importer.nodes_store.compact()

    logger.info("Parsing and importing ways (2nd pass)...")
    OSMParser(concurrency=workers, ways_callback=osm_importer.parse_ways_second).parse(osm_file)

    if osm_importer.failed:
        logger.warning(f"Parsing {osm_file} failed, see the error above. \n"
                       f"         The file has been marked to be imported later, run update after init completes.")
        del osm_importer
        return 1

    if len(osm_importer.process_ways_set) > 0:
        logger.warning(
            f"{len(osm_importer.process_ways_set)} ways not processed due to missing coordinate information, "
            f"possible pbf file corruption")

    # store remaining data in buffer
    osm_importer.save_buffer()

    logger.info(f"Found {osm_importer.pois_count} POIs")
    logger.info(f"Finished import of {osm_file}")
    del osm_importer
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
        delete_marked_entries(db_con)

    logger.info(f"Import complete.")


@timeit
def run_import_new(osm_files_to_import, import_log, logfile, db_con):
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

        if import_file(osm_file, osm_file_index, update_mode, db_con):
            import_log[osm_file] = os.path.getmtime(osm_file)
        else:
            import_log[osm_file] = 0  # import failed, this file has to be inserted in the next update

        with open(logfile, "w") as f:
            json.dump(import_log, f, indent=4, sort_keys=True)
            f.close()


    logger.info("Import complete.")


def import_file(osm_file, osm_file_index, update_mode, db_con):
    """
    Imports one osm file. In update mode, the POIs of the previous import of this file are only deleted if the
    import succeeded; on failure they are kept, so a failed update never removes data.

    :return: True if the import succeeded
    """
    if update_mode:
        prev_poi_count_file = db_con.session.query(POIs.osm_type, POIs.osm_id).filter_by(
            src_index=osm_file_index).count()
        logger.info(f"Setting flags on {prev_poi_count_file} POIs.")
        db_con.session.query(POIs).filter_by(src_index=osm_file_index).update({POIs.delflag: True})
        db_con.session.commit()

    try:
        succeeded = parse_file_new(osm_file, osm_file_index, update_mode=update_mode) == 0
    except RuntimeError:
        logger.exception(f"Import of {osm_file} crashed")
        succeeded = False

    if update_mode:
        if succeeded:
            delete_marked_entries(db_con, osm_file_index)
        else:
            unmark_entries(db_con, osm_file_index)

    return succeeded


def marked_entries(db_con, src_index=None):
    query = db_con.session.query(POIs).filter_by(delflag=True)
    if src_index is not None:
        query = query.filter_by(src_index=src_index)
    return query


@timeit
def delete_marked_entries(db_con, src_index=None):
    logger.info("Updates complete, now performing delete operations...")
    to_delete = marked_entries(db_con, src_index).count()
    if to_delete > 0:
        logger.info(f"{to_delete} POIs in the database have been removed from the OSM data, deleting...")
        marked_entries(db_con, src_index).delete()
        db_con.session.commit()
    else:
        logger.info("No POIs marked for deletion, nothing to do.")


def unmark_entries(db_con, src_index):
    to_keep = marked_entries(db_con, src_index).update({POIs.delflag: False})
    db_con.session.commit()
    logger.warning(f"Import failed, keeping {to_keep} POIs from the previous import of this file.")
