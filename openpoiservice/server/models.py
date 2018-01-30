# openpoiservice/server/models.py

import datetime
from openpoiservice.server import db
from openpoiservice import ops_settings
from geoalchemy2 import Geometry, Geography


class Pois(db.Model):
    SRID = '4326'

    if 'table_name' in ops_settings['provider_parameters']:
        __table_name__ = ops_settings['provider_parameters']['table_name'];
    else:
        __table_name__ = 'ops_planet_pois'

    osm_id = db.Column(db.BigInteger, primary_key=True)
    osm_type = db.Column(db.SmallInteger, nullable=False)
    category = db.Column(db.Text, index=True, nullable=True)
    name = db.Column(db.Text, index=True, nullable=True, default=False)
    website = db.Column(db.Text, nullable=True, default=False)
    phone = db.Column(db.Text, nullable=True, default=False)
    opening_hours = db.Column(db.Text, nullable=True, default=False)
    wheelchair = db.Column(db.Text, nullable=True, default=False)
    smoking = db.Column(db.Text, nullable=True, default=False)
    fee = db.Column(db.Text, nullable=True, default=False)
    address = db.Column(db.Text, nullable=True, default=False)

    if SRID == 4326:
        geom = db.Column(Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False)
    else:
        geom = db.Column(Geometry(geometry_type="POINT", srid=SRID, spatial_index=True), nullable=False)
        location = db.Column(Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False)
