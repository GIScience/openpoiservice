# openpoiservice/server/models.py

from openpoiservice.server import db, ops_settings
from geoalchemy2 import Geometry, Geography


class Pois(db.Model):
    if 'table_name' in ops_settings['provider_parameters']:
        __tablename__ = ops_settings['provider_parameters']['table_name']
    else:
        __tablename__ = "ops_planet_pois"

    osm_id = db.Column(db.BigInteger, primary_key=True)
    osm_type = db.Column(db.Integer, nullable=False)
    category = db.Column(db.Integer, index=True, nullable=False)
    geom = db.Column(Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False)

    tags = db.relationship("Tags", backref='{}'.format(ops_settings['provider_parameters']['table_name']), lazy='dynamic')

    def __repr__(self):
        return '<osm id %r>' % self.osm_id


class Tags(db.Model):
    if 'table_name' in ops_settings['provider_parameters']:
        __tablename__ = ops_settings['provider_parameters']['table_name'] + "_tags"
    else:
        __tablename__ = "ops_planet_pois_tags"

    id = db.Column(db.Integer, primary_key=True)
    osm_id = db.Column(db.BigInteger, db.ForeignKey('{}.osm_id'.format(ops_settings['provider_parameters']['table_name'])), nullable=False)
    key = db.Column(db.Text, nullable=True)
    value = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return '<osm id %r>' % self.osm_id
