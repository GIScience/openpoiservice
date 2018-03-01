# openpoiservice/server/tests/base.py

from flask_testing import TestCase
from openpoiservice.server import db, create_app
from openpoiservice.server.db_import import parser
from openpoiservice.server import ops_settings
import os

app = create_app()


class BaseTestCase(TestCase):

    def create_app(self):
        app.config.from_object('openpoiservice.server.config.TestingConfig')

        return app

    def setUp(self):
        db.create_all()

        test_files = [os.path.join(os.getcwd() + '/osm', osm_file) for osm_file in ops_settings['osm_file_tests']]

        parser.run_import(test_files)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
