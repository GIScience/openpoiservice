# openpoiservice/server/parser.py

from openpoiservice.server.db_import.parse_osm import OsmImporter
from openpoiservice.server.utils.decorators import timeit
from imposm.parser import OSMParser
import logging

logger = logging.getLogger(__name__)


@timeit
def parse_file(osm_file):
    logger.info('Starting to read {}'.format(osm_file))

    osm_importer = OsmImporter()

    relations = OSMParser(concurrency=4, relations_callback=osm_importer.parse_relations)
    relations.parse(osm_file)
    logger.info('Found {} ways in relations'.format(osm_importer.relations_cnt))

    ways = OSMParser(concurrency=4, ways_callback=osm_importer.parse_ways)
    ways.parse(osm_file)
    logger.info('Found {} ways'.format(osm_importer.ways_cnt))

    nodes = OSMParser(concurrency=4, nodes_callback=osm_importer.parse_nodes)
    nodes.parse(osm_file)

    coords = OSMParser(concurrency=4, coords_callback=osm_importer.parse_coords)
    coords.parse(osm_file)

    osm_importer.parse_nodes_of_ways()
    logger.info('Found {} pois'.format(osm_importer.pois_cnt))

    logger.info('Finished import of {}'.format(osm_file))


def run_import(osm_files_to_import):
    for osm_file in osm_files_to_import:
        parse_file(osm_file)
