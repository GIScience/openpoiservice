# openpoiservice/server/tests/base.py
import unittest
import os
from pathlib import Path

from openpoiservice import db, create_app
from openpoiservice.utils import parser
from openpoiservice.logger import logger

this_path = Path(os.path.dirname(__file__))

class BaseTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app = create_app('testing')
        app.app_context().push()
        cls.app = app

        cls.db = db
        cls.db.app = cls.app

        logger.info(f"""The following database settings are active:
\tHost:     {cls.db.engine.url.host}:{cls.db.engine.url.port}
\tDatabase: {cls.db.engine.url.database}
\tUser:     {cls.db.engine.url.username}""")

        cls.db.create_all()
        logger.info("Created tables:\n\t{}".format("\n\t".join(cls.db.metadata.tables.keys())))

        # Import test data
        test_file = Path(os.path.join(this_path, 'data', 'bremen-tests.osm.pbf'))
        parser.parse_import(test_file)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        db.drop_all()

    def setUp(self):
        super().setUp()
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        super().tearDown()
        self.app_context.pop()
