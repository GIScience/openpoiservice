# openpoiservice/server/models.py

from openpoiservice.server import db, ops_settings
from geoalchemy2 import Geography


class Pois(db.Model):
    __tablename__ = ops_settings['provider_parameters']['table_name']
    print __tablename__
    osm_id = db.Column(db.BigInteger, primary_key=True)
    osm_type = db.Column(db.Integer, nullable=False)
    category = db.Column(db.Integer, index=True, nullable=False)
    #address = db.Column(db.Text, nullable=True)
    geom = db.Column(Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False)

    tags = db.relationship("Tags", backref='{}'.format(ops_settings['provider_parameters']['table_name']),
                           lazy='dynamic')

    def __repr__(self):
        return '<osm id %r>' % self.osm_id


class Tags(db.Model):
    __tablename__ = ops_settings['provider_parameters']['table_name'] + "_tags"
    print __tablename__

    id = db.Column(db.Integer, primary_key=True)
    osm_id = db.Column(db.BigInteger,
                       db.ForeignKey('{}.osm_id'.format(ops_settings['provider_parameters']['table_name'])),
                       nullable=False)
    key = db.Column(db.Text, nullable=True, index=True)
    value = db.Column(db.Text, nullable=True, index=True)

    def __repr__(self):
        return '<osm id %r>' % self.osm_id
