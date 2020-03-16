# openpoiservice/server/parser.py
import logging
from pathlib import Path
import multiprocessing as mp

from .osm_reader import OsmReader
from openpoiservice.server import ops_settings
from openpoiservice.server.utils.decorators import timeit

# h = hpy()
logger = logging.getLogger(__name__)

def parse_import(osm_file):
    """
    Runs a process.

    :param osm_file: the OSM file path
    :type osm_file: Path
    """
    reader = OsmReader(osm_file.name)

    logger.info(f"Starting with file {osm_file.name}...")
    reader.apply_file(str(osm_file.resolve()), locations=True, idx='sparse_mmap_array')

    logger.info(f"{osm_file.name}: Found {reader.poi_count} POIs")

    # Save whatever's left in the object lists
    reader.save_objects()

    return reader.poi_count


@timeit
def run_import(osm_files_to_import):
    pool = mp.Pool(ops_settings['concurrent_workers'])
    poi_counts = pool.map(parse_import, osm_files_to_import)

    pool.close()
    pool.join()

    logger.info(f"Finished with total {sum(poi_counts)} POIs")
