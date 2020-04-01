import logging

# silence shapely info that numpy is not present
logging.getLogger("shapely.speedups._speedups").setLevel(logging.WARNING)

# Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger('openpoiservice')