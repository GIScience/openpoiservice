from flask import current_app as app

import os
from geoalchemy2 import Geography
import logging

from openpoiservice import db

is_testing = os.getenv('TESTING')
poi_table_name = 'ops_pois' if not is_testing else 'ops_pois_test'
cat_table_name = 'ops_categories' if not is_testing else 'ops_categories_test'
tag_table_name = 'ops_tags' if not is_testing else 'ops_tags_test'

logger = logging.getLogger(__name__)


class Pois(db.Model):
    __tablename__ = poi_table_name

    logger.info('table name for pois: {}'.format(poi_table_name))

    uuid = db.Column(db.LargeBinary, primary_key=True)
    osm_id = db.Column(db.BigInteger, nullable=False, index=True)
    osm_type = db.Column(db.Integer, nullable=False)
    # address = db.Column(db.Text, nullable=True)
    geom = db.Column(Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False)

    tags = db.relationship("Tags", backref='{}'.format(poi_table_name),
                           lazy='dynamic')

    categories = db.relationship("Categories", backref='{}'.format(poi_table_name),
                                 lazy='dynamic')

    def __repr__(self):
        return '<osm id %r>' % self.osm_id


class Categories(db.Model):
    __tablename__ = cat_table_name

    logger.info('Table name for categories: {}'.format(cat_table_name))

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(db.LargeBinary, db.ForeignKey('{}.uuid'.format(poi_table_name)),
                     nullable=False, index=True)
    category = db.Column(db.Integer, index=True, nullable=False)

    def __repr__(self):
        return '<category %r>' % self.category


class Tags(db.Model):
    __tablename__ = tag_table_name

    logger.info('Table name for tags: {}'.format(tag_table_name))

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(db.LargeBinary, db.ForeignKey('{}.uuid'.format(poi_table_name)),
                     nullable=False, index=True)
    osm_id = db.Column(db.BigInteger, nullable=False)
    key = db.Column(db.Text, nullable=True, index=True)
    value = db.Column(db.Text, nullable=True, index=True)

    def __repr__(self):
        return '<osm id %r>' % self.osm_id
