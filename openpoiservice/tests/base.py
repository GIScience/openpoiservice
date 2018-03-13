# openpoiservice/server/tests/base.py

from flask_testing import TestCase
from openpoiservice.server import db, create_app
from openpoiservice.server.db_import import parser
import os

app = create_app()


class BaseTestCase(TestCase):

    def create_app(self):
        app.config.from_object('openpoiservice.server.config.TestingConfig')

        return app

    def setUp(self):
        db.create_all()

        test_file = os.path.join(os.getcwd() + '/osm', 'bremen-tests.osm.pbf')

        parser.parse_import(test_file)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
