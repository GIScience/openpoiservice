# openpoiservice/server/parser.py

from openpoiservice.server.db_import.parse_osm import OsmImporter
from imposm.parser import OSMParser
from timeit import Timer
import logging

logger = logging.getLogger(__name__)


def run_import(osm_files_to_import):
    for osm_file in osm_files_to_import:
        logger.info("Importing OSM file... {}".format(osm_file))

        osm_importer = OsmImporter()

        relations = OSMParser(concurrency=4, relations_callback=osm_importer.parse_relations)
        t = Timer(lambda: relations.parse(osm_file))
        logger.info('Starting to read {}'.format(osm_file))

        logger.info('Time passed: {}s'.format(t.timeit(number=1)))
        logger.info('Found {} ways in relations'.format(osm_importer.relations_cnt))

        ways = OSMParser(concurrency=4, ways_callback=osm_importer.parse_ways)
        t = Timer(lambda: ways.parse(osm_file))
        logger.info('Time passed: {}s'.format(t.timeit(number=1)))
        logger.info('Found {} ways'.format(osm_importer.ways_cnt))

        nodes = OSMParser(concurrency=4, nodes_callback=osm_importer.parse_nodes)
        t = Timer(lambda: nodes.parse(osm_file))
        logger.info('Time passed to parse nodes: {}s'.format(t.timeit(number=1)))

        coords = OSMParser(concurrency=4, coords_callback=osm_importer.parse_coords)
        t = Timer(lambda: coords.parse(osm_file))
        logger.info('Time passed to parse coords for nodes from ways: {}s'.format(t.timeit(number=1)))

        t = Timer(lambda: osm_importer.parse_nodes_of_ways())
        logger.info('Time passed total: {}s to import {}'.format(t.timeit(number=1), osm_file))
        logger.info('Found {} pois'.format(osm_importer.pois_cnt))
