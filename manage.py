# manage.py

import unittest
from flask.cli import FlaskGroup
from openpoiservice.server import create_app, db, ops_settings
from openpoiservice.server.db_import.parse_pbf import PbfImporter
from imposm.parser import OSMParser
from timeit import Timer
import os

app = create_app()
cli = FlaskGroup(create_app=create_app)


@cli.command()
def test():
    """Runs the unit tests without test coverage."""

    tests = unittest.TestLoader().discover('openpoiservice/tests', pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if result.wasSuccessful():
        return 0
    return 1


@cli.command()
def create_db():
    """Creates the db tables."""

    db.create_all()


@cli.command()
def drop_db():
    """Drops the db tables."""

    db.drop_all()


@cli.command()
def import_data():

    """Imports osm pbf data to postgis."""

    pbf_importer = PbfImporter()

    script_dir = os.path.dirname(__file__)
    osm_file_path = os.path.join(script_dir, ops_settings['osm_file'])

    relations = OSMParser(concurrency=4, relations_callback=pbf_importer.parse_relations)
    t = Timer(lambda: relations.parse(osm_file_path))
    print 'Time passed: {}s'.format(t.timeit(number=1))
    print 'Found {} ways in relations'.format(pbf_importer.relations_cnt)

    ways = OSMParser(concurrency=4, ways_callback=pbf_importer.parse_ways)
    t = Timer(lambda: ways.parse(osm_file_path))
    print 'Time passed: {}s'.format(t.timeit(number=1))
    print 'Found {} ways'.format(pbf_importer.ways_cnt)

    nodes = OSMParser(concurrency=4, nodes_callback=pbf_importer.parse_nodes)
    t = Timer(lambda: nodes.parse(osm_file_path))
    print 'Time passed to parse nodes: {}s'.format(t.timeit(number=1))

    coords = OSMParser(concurrency=4, coords_callback=pbf_importer.parse_coords)
    t = Timer(lambda: coords.parse(osm_file_path))
    print 'Time passed to parse coords for nodes from ways: {}s'.format(t.timeit(number=1))

    t = Timer(lambda: pbf_importer.parse_nodes_of_ways())
    print 'Time passed total: {}s'.format(t.timeit(number=1))
    print 'Found {} pois'.format(pbf_importer.pois_cnt)


if __name__ == '__main__':
    print True
    cli()

