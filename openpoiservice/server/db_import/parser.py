# openpoiservice/server/parser.py
from flask_sqlalchemy import SQLAlchemy

from openpoiservice.server.db_import.models import POIs
from openpoiservice.server.db_import.parse_osm import OsmImporter
from openpoiservice.server.utils.decorators import timeit, processify
from openpoiservice.server import ops_settings
from imposm.parser import OSMParser
import logging
from pyroaring import BitMap

# from guppy import hpy
from collections import deque

# h = hpy()
logger = logging.getLogger(__name__)


# process this function to free memory after import of each osm file

def parse_import(osm_file, update_mode=False):
    logger.info('Starting to read {}'.format(osm_file))

    osm_importer = OsmImporter(update_mode=update_mode)

    logger.info('Parsing and importing nodes...')
    nodes = OSMParser(concurrency=ops_settings['concurrent_workers'], nodes_callback=osm_importer.parse_nodes)
    nodes.parse(osm_file)

    logger.info('Parsing relations...')
    relations = OSMParser(concurrency=ops_settings['concurrent_workers'],
                          relations_callback=osm_importer.parse_relations)
    relations.parse(osm_file)
    logger.info('Found {} ways in relations'.format(osm_importer.relations_cnt))

    logger.info('Parsing ways...')
    ways = OSMParser(concurrency=ops_settings['concurrent_workers'], ways_callback=osm_importer.parse_ways)
    ways.parse(osm_file)

    logger.info('Found {} ways'.format(osm_importer.ways_cnt))
    del osm_importer.relation_ways

    # Sort the ways by the first osm_id reference, saves memory for parsing coords
    osm_importer.process_ways.sort(key=lambda x: x.refs[0])
    # init self.process_ways_length before the first call of parse_coords function!
    osm_importer.process_ways_length = len(osm_importer.process_ways)

    # https://docs.python.org/3/library/collections.html#collections.deque
    osm_importer.process_ways = deque(osm_importer.process_ways)
    logger.info('Importing ways... (note this wont work concurrently)')

    coords = OSMParser(concurrency=1, coords_callback=osm_importer.parse_coords_for_ways)
    coords.parse(osm_file)

    logger.info('Storing remaining pois')
    osm_importer.save_buffer()

    logger.info('Found {} pois'.format(osm_importer.pois_count))

    logger.info('Finished import of {}'.format(osm_file))

    # logger.debug('Heap: {}'.format(h.heap()))

    # clear memory
    del osm_importer


@processify
def parse_file(osm_file, update_mode=False):
    parse_import(osm_file, update_mode=update_mode)


@timeit
def run_import(osm_files_to_import):
    update_mode = False
    separate_db_con = SQLAlchemy()
    prev_poi_count = len(separate_db_con.session.query(POIs).all())
    if prev_poi_count > 0:
        update_mode = True
        logger.info(f"Data import running in UPDATE MODE. Setting flags on {prev_poi_count} POIs.")
        separate_db_con.session.query(POIs).update({POIs.delete: True})
        separate_db_con.session.commit()
    separate_db_con.engine.dispose()

    for osm_file in osm_files_to_import:
        parse_file(osm_file, update_mode=update_mode)

    if update_mode:
        logger.info(f"Updates complete, now performing delete operations...")
        separate_db_con = SQLAlchemy()
        to_delete = len(separate_db_con.session.query(POIs).filter_by(delete=True).all())
        if to_delete > 0:
            logger.info(f"{to_delete} POIs in the database have been removed from the OSM data, deleting...")
            separate_db_con.session.query(POIs).filter_by(delete=True).delete()
            separate_db_con.session.commit()
        else:
            logger.info(f"No POIs marked for deletion, nothing to do.")
        separate_db_con.engine.dispose()

    logger.info(f"Import complete.")
