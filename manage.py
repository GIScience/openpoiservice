# manage.py
from sqlalchemy import MetaData
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

import unittest
import os
import sys
from pathlib import Path
from openpoiservice.utils.env import is_testing
from openpoiservice import create_app, db
from sqlalchemy import text

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

    prewarm = app.config['POSTGRES_PREWARM']
    if not is_testing() and prewarm == True:
        tables = []
        for cls in db.Model._decl_class_registry.values():
            try:
                tables.append(cls.__tablename__)
            except:
                pass
        logger.info('Starting to prewarm tables {}'.format(", ".join(tables)))
        for tbl in tables:
            try:
                sql = text("select pg_prewarm('{}')".format(tbl))
                result = db.engine.execute(sql)
                for res in result:
                    logger.info('Prewarmed {} pages in {}'.format(res, tbl))
            except ProgrammingError as e:
               logger.info("pg_prewarm is set to {} but it seems not to be enabled in the database.\n Proceeding without.".format(prewarm))
               logger.debug(str(e.__dict__['orig']))

    sys.exit(0)

if __name__ == '__main__':
    app.cli()
