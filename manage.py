# manage.py

import unittest
from flask.cli import FlaskGroup
from openpoiservice.server import create_app, db
from openpoiservice.server.db_import import parser
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    osm_files = []
    osm_dir = os.getcwd() + '/osm'

    for dirName, subdirList, fileList in os.walk(osm_dir):
        print('Found directory: %s' % dirName)
        for fname in fileList:
            if fname.endswith('.osm.pbf') or fname.endswith('.osm'):
                osm_files.append(os.path.join(dirName, fname))

    logger.info("Starting to import OSM data...{}".format(osm_files))
    parser.run_import(osm_files)


if __name__ == '__main__':
    cli()
