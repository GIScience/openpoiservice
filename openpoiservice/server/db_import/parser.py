# openpoiservice/server/parser.py
from flask_sqlalchemy import SQLAlchemy

from openpoiservice.server.db_import.models import POIs
from openpoiservice.server.db_import.parse_osm import OsmImporter
from openpoiservice.server.utils.decorators import timeit, processify
from openpoiservice.server import ops_settings, db
from imposm.parser import OSMParser
import logging
from collections import deque

logger = logging.getLogger(__name__)


# process this function to free memory after import of each osm file
@processify
def parse_import(osm_file, update_mode=False):
    logger.info(f"Starting to read {osm_file}")
    workers = ops_settings["concurrent_workers"]
    osm_importer = OsmImporter(update_mode=update_mode)

    logger.info("Parsing and importing nodes...")
    OSMParser(concurrency=workers, nodes_callback=osm_importer.parse_nodes).parse(osm_file)
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

    if len(osm_importer.process_ways) > 0:
        logger.warning(f"{len(osm_importer.process_ways)} ways not processed due to missing coordinate information, "
                       f"possible pbf file corruption")

    # store remaining data in buffer
    osm_importer.save_buffer()

    logger.info(f"Found {osm_importer.pois_count} POIs")
    logger.info(f"Finished import of {osm_file}")

    # clear memory
    del osm_importer


@timeit
def run_import(osm_files_to_import):
    update_mode = False
    # run query on separate database connection, will conflict otherwise since parse_import runs in separate process
    separate_db_con = SQLAlchemy()
    prev_poi_count = len(separate_db_con.session.query(POIs).all())
    if prev_poi_count > 0:
        update_mode = True
        logger.info(f"Data import running in UPDATE MODE. Setting flags on {prev_poi_count} POIs.")
        separate_db_con.session.query(POIs).update({POIs.delete: True})
        separate_db_con.session.commit()
    separate_db_con.engine.dispose()

    for osm_file in osm_files_to_import:
        parse_import(osm_file, update_mode=update_mode)

    if update_mode:
        logger.info(f"Updates complete, now performing delete operations...")
        to_delete = len(db.session.query(POIs).filter_by(delete=True).all())
        if to_delete > 0:
            logger.info(f"{to_delete} POIs in the database have been removed from the OSM data, deleting...")
            db.session.query(POIs).filter_by(delete=True).delete()
            db.session.commit()
        else:
            logger.info(f"No POIs marked for deletion, nothing to do.")

    logger.info(f"Import complete.")
