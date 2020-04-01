# manage.py
from sqlalchemy import MetaData
from sqlalchemy.engine import Engine

import unittest
import os
import sys
from pathlib import Path

from openpoiservice import create_app, db

app = create_app()
app.app_context().push()

db_meta: MetaData = db.metadata
db_engine: Engine = db.engine

# Needs to be loaded after create_app() so that the app context can be built
from openpoiservice.utils import parser
from openpoiservice.logger import logger

logger.info(f"""The following database settings are active:
\tHost:     {db_engine.url.host}:{db_engine.url.port}
\tDatabase: {db_engine.url.database}
\tUser:     {db_engine.url.username}""")

@app.cli.command()
def test():
    """Runs the unit tests without test coverage."""

    tests = unittest.TestLoader().discover('tests', pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if not result.wasSuccessful():
        sys.exit(1)
    sys.exit(0)


@app.cli.command()
def create_db():
    """Creates the db tables."""
    db.create_all()
    logger.info("Created tables:\n\t{}".format("\n\t".join(db_meta.tables.keys())))


@app.cli.command()
def drop_db():
    """Drops the db tables."""
    db.drop_all()
    logger.info("Dropped tables:\n{}".format("\n".join(db_meta.tables.keys())))


@app.cli.command()
def import_data():
    """Imports osm pbf data to postgis."""

    osm_files = []
    osm_dir = os.path.join(os.getcwd(), 'osm')

    for dirName, subdirList, fileList in os.walk(osm_dir):
        for fname in fileList:
            if fname.endswith('.osm') or fname.endswith('.pbf') and not dirName.endswith('tests/data'):
                osm_files.append(Path(os.path.join(dirName, fname)))

    if not osm_files:
        logger.error(f"No OSM files found in {osm_dir}")
        sys.exit(1)

    logger.info('Starting to import OSM data from\n\t{}'.format("\n\t".join([str(p.resolve()) for p in osm_files])))
    parser.run_import(osm_files)
    sys.exit(0)

if __name__ == '__main__':
    app.cli()
