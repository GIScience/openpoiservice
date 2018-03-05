# openpoiservice/server/parser.py

from openpoiservice.server.db_import.parse_osm import OsmImporter
from openpoiservice.server.utils.decorators import timeit
from imposm.parser import OSMParser
import logging
import sys
from openpoiservice.server import ops_settings

logger = logging.getLogger(__name__)


@timeit
def parse_file(osm_file):
    logger.info('Starting to read {}'.format(osm_file))

    osm_importer = OsmImporter()

    relations = OSMParser(concurrency=ops_settings['concurrent_workers'],
                          relations_callback=osm_importer.parse_relations)
    relations.parse(osm_file)
    logger.info('Found {} ways in relations'.format(osm_importer.relations_cnt))

    ways = OSMParser(concurrency=ops_settings['concurrent_workers'], ways_callback=osm_importer.parse_ways)
    ways.parse(osm_file)
    logger.info('Found {} ways'.format(osm_importer.ways_cnt))

    nodes = OSMParser(concurrency=ops_settings['concurrent_workers'], nodes_callback=osm_importer.parse_nodes)
    nodes.parse(osm_file)

    coords = OSMParser(concurrency=ops_settings['concurrent_workers'], coords_callback=osm_importer.parse_coords)
    coords.parse(osm_file)

    osm_importer.parse_nodes_of_ways()
    logger.info('Found {} pois'.format(osm_importer.pois_cnt))

    logger.info('Finished import of {}'.format(osm_file))

    # clear memory
    del osm_importer


def run_import(osm_files_to_import):
    for osm_file in osm_files_to_import:
        parse_file(osm_file)
