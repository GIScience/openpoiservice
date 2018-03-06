# openpoiservice/server/parser.py

from openpoiservice.server.db_import.parse_osm import OsmImporter
from openpoiservice.server.utils.decorators import timeit, profile, get_size
from openpoiservice.server import ops_settings
from imposm.parser import OSMParser
import logging
from guppy import hpy

h = hpy()

logger = logging.getLogger(__name__)


@timeit
def parse_file(osm_file):
    logger.info('Starting to read {}'.format(osm_file))

    osm_importer = OsmImporter()

    logger.info('Parsing relations...')
    relations = OSMParser(concurrency=ops_settings['concurrent_workers'],
                          relations_callback=osm_importer.parse_relations)
    relations.parse(osm_file)
    logger.info('Found {} ways in relations'.format(osm_importer.relations_cnt))

    logger.info('self.nodes dict size in mb is {}'.format(get_size(osm_importer.nodes) / 1024 / 1024))
    logger.info('self.process_ways size in mb is {}'.format(get_size(osm_importer.process_ways) / 1024 / 1024))
    logger.info('self.poi_objects size in mb is {}'.format(get_size(osm_importer.poi_objects) / 1024 / 1024))
    logger.info('self.tags_objects size in mb is {}'.format(get_size(osm_importer.tags_objects) / 1024 / 1024))

    logger.info('heap: {}'.format(h.heap()))

    logger.info('Parsing ways...')
    ways = OSMParser(concurrency=ops_settings['concurrent_workers'], ways_callback=osm_importer.parse_ways)
    ways.parse(osm_file)
    logger.info('Found {} ways'.format(osm_importer.ways_cnt))
    del osm_importer.relation_ways

    logger.info('self.nodes dict size in mb is {}'.format(get_size(osm_importer.nodes) / 1024 / 1024))
    logger.info('self.process_ways size in bytes is {}'.format(get_size(osm_importer.process_ways)))
    logger.info('self.poi_objects size in mb is {}'.format(get_size(osm_importer.poi_objects) / 1024 / 1024))
    logger.info('self.tags_objects size in mb is {}'.format(get_size(osm_importer.tags_objects) / 1024 / 1024))

    logger.info('heap: {}'.format(h.heap()))

    logger.info('Parsing and importing nodes...')
    nodes = OSMParser(concurrency=ops_settings['concurrent_workers'], nodes_callback=osm_importer.parse_nodes)
    nodes.parse(osm_file)

    logger.info('self.nodes dict size in mb is {}'.format(get_size(osm_importer.nodes) / 1024 / 1024))
    logger.info('self.process_ways size in bytes is {}'.format(get_size(osm_importer.process_ways)))
    logger.info('self.poi_objects size in mb is {}'.format(get_size(osm_importer.poi_objects) / 1024 / 1024))
    logger.info('self.tags_objects size in mb is {}'.format(get_size(osm_importer.tags_objects) / 1024 / 1024))

    logger.info('heap: {}'.format(h.heap()))

    logger.info('Parsing coords...')
    coords = OSMParser(concurrency=ops_settings['concurrent_workers'], coords_callback=osm_importer.parse_coords)
    coords.parse(osm_file)

    logger.info('self.nodes dict size in mb is {}'.format(get_size(osm_importer.nodes) / 1024 / 1024))
    logger.info('self.process_ways size in bytes is {}'.format(get_size(osm_importer.process_ways)))
    logger.info('self.poi_objects size in mb is {}'.format(get_size(osm_importer.poi_objects) / 1024 / 1024))
    logger.info('self.tags_objects size in mb is {}'.format(get_size(osm_importer.tags_objects) / 1024 / 1024))

    logger.info('Importing ways...')
    osm_importer.parse_nodes_of_ways()

    logger.info('Found {} pois'.format(osm_importer.pois_cnt))

    logger.info('Finished import of {}'.format(osm_file))

    logger.info('self.nodes dict size in mb is {}'.format(get_size(osm_importer.nodes) / 1024 / 1024))
    logger.info('self.process_ways size in bytes is {}'.format(get_size(osm_importer.process_ways)))
    logger.info('self.poi_objects size in mb is {}'.format(get_size(osm_importer.poi_objects) / 1024 / 1024))
    logger.info('self.tags_objects size in mb is {}'.format(get_size(osm_importer.tags_objects) / 1024 / 1024))

    logger.info('self size in bytes is {}'.format(get_size(osm_importer)))

    # clear memory
    del osm_importer
    logger.info('heap: {}'.format(h.heap()))


def run_import(osm_files_to_import):
    for osm_file in osm_files_to_import:
        parse_file(osm_file)
