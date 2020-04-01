# openpoiservice/server/tests/base.py

from flask_testing import TestCase
from pathlib import Path
from openpoiservice import db, create_app, config_map
from openpoiservice.utils import parser
import os

app = create_app('testing')


class BaseTestCase(TestCase):

    def create_app(self):
        app.config.from_object(config_map['testing'])

        return app

    def setUp(self):
        db.create_all()

        test_file = Path(os.path.join('tests', 'data', 'bremen-tests.osm.pbf'))

        parser.parse_import(test_file)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
