# openpoiservice/server/models.py

from openpoiservice.server import db, ops_settings
from geoalchemy2 import Geography
import logging

logger = logging.getLogger(__name__)


class Pois(db.Model):
    __tablename__ = ops_settings['provider_parameters']['table_name']
    logger.info('table name for pois: {}'.format(__tablename__))

    uuid = db.Column(db.LargeBinary, primary_key=True)
    osm_id = db.Column(db.BigInteger, nullable=False, index=True)
    osm_type = db.Column(db.Integer, nullable=False)
    # address = db.Column(db.Text, nullable=True)
    geom = db.Column(Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False)

    tags = db.relationship("Tags", backref='{}'.format(ops_settings['provider_parameters']['table_name']),
                           lazy='dynamic')

    categories = db.relationship("Categories", backref='{}'.format(ops_settings['provider_parameters']['table_name']),
                                 lazy='dynamic')

    def __repr__(self):
        return '<osm id %r>' % self.osm_id


class Categories(db.Model):
    __tablename__ = ops_settings['provider_parameters']['table_name'] + "_categories"
    logger.info('Table name for categories: {}'.format(__tablename__))

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(db.LargeBinary, db.ForeignKey('{}.uuid'.format(ops_settings['provider_parameters']['table_name'])),
                     nullable=False, index=True)
    category = db.Column(db.Integer, index=True, nullable=False)

    def __repr__(self):
        return '<category %r>' % self.category


class Tags(db.Model):
    __tablename__ = ops_settings['provider_parameters']['table_name'] + "_tags"
    logger.info('Table name for tags: {}'.format(__tablename__))

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid = db.Column(db.LargeBinary, db.ForeignKey('{}.uuid'.format(ops_settings['provider_parameters']['table_name'])),
                     nullable=False, index=True)
    osm_id = db.Column(db.BigInteger, nullable=False)
    key = db.Column(db.Text, nullable=True, index=True)
    value = db.Column(db.Text, nullable=True, index=True)

    def __repr__(self):
        return '<osm id %r>' % self.osm_id
