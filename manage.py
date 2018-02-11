# manage.py

import unittest
from flask_script import Manager
from openpoiservice.server import create_app, db
from openpoiservice.server.db_import.parse_pbf import PbfImporter
from imposm.parser import OSMParser
from timeit import Timer

# code coverage
# COV = coverage.coverage(
#    branch=True,
#    include='openpoiservice/*',
#    omit=[
#        'openpoiservice/tests/*',
#        'openpoiservice/server/config.py',
#        'openpoiservice/server/*/__init__.py'
#    ]
# )
# COV.start()

app = create_app()
manager = Manager(app)


@manager.command
def test():
    """Runs the unit tests without test coverage."""
    tests = unittest.TestLoader().discover('openpoiservice/tests', pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if result.wasSuccessful():
        return 0
    return 1


@manager.command
def cov():
    """Runs the unit tests with coverage."""
    tests = unittest.TestLoader().discover('openpoiservice/tests')
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if result.wasSuccessful():
        COV.stop()
        COV.save()
        print('Coverage Summary:')
        COV.report()
        COV.html_report()
        COV.erase()
        return 0
    return 1


@manager.command
def create_db():
    """Creates the db tables."""
    db.create_all()


@manager.command
def drop_db():
    """Drops the db tables."""
    db.drop_all()


@manager.command
def import_data():

    """Imports osm pbf data to postgis."""
    pbf_importer = PbfImporter()

    relations = OSMParser(concurrency=4, relations_callback=pbf_importer.parse_relations)
    t = Timer(lambda: relations.parse('/Users/neilmccauley/Workspaces/openpoiservice/bremen-latest.osm.pbf'))
    print 'Time passed: {}s'.format(t.timeit(number=1))
    print 'Found {} ways in relations'.format(pbf_importer.relations_cnt)

    ways = OSMParser(concurrency=4, ways_callback=pbf_importer.parse_ways)
    t = Timer(lambda: ways.parse('/Users/neilmccauley/Workspaces/openpoiservice/bremen-latest.osm.pbf'))
    print 'Time passed: {}s'.format(t.timeit(number=1))
    print 'Found {} ways'.format(pbf_importer.ways_cnt)

    nodes = OSMParser(concurrency=4, nodes_callback=pbf_importer.parse_nodes)
    t = Timer(lambda: nodes.parse('/Users/neilmccauley/Workspaces/openpoiservice/bremen-latest.osm.pbf'))
    print 'Time passed to parse nodes: {}s'.format(t.timeit(number=1))

    coords = OSMParser(concurrency=4, coords_callback=pbf_importer.parse_coords)
    t = Timer(lambda: coords.parse('/Users/neilmccauley/Workspaces/openpoiservice/bremen-latest.osm.pbf'))
    print 'Time passed to parse coords for nodes from ways: {}s'.format(t.timeit(number=1))

    t = Timer(lambda: pbf_importer.parse_nodes_of_ways())
    print 'Time passed total: {}s'.format(t.timeit(number=1))
    print 'Found {} pois'.format(pbf_importer.pois_cnt)


if __name__ == '__main__':
    manager.run()
