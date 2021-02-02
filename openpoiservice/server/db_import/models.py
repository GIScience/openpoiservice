# openpoiservice/server/models.py
from openpoiservice.server import db, ops_settings
from geoalchemy2 import Geography
import logging

logger = logging.getLogger(__name__)


class POIs(db.Model):
    __tablename__ = ops_settings['provider_parameters']['table_name']
    logger.info(f"Table name for POIs: {__tablename__}")

    osm_type = db.Column(db.Integer, primary_key=True)
    osm_id = db.Column(db.BigInteger, primary_key=True)
    geom = db.Column(Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False)
    delete = db.Column(db.Boolean, nullable=False, index=True)

    tags = db.relationship("Tags", backref=db.backref("POIs", cascade="delete"), lazy='dynamic')
    categories = db.relationship("Categories", backref=db.backref("POIs", cascade="delete"), lazy='dynamic')

    def __repr__(self):
        return '<osm id %r>' % self.osm_id


class Categories(db.Model):
    __tablename__ = ops_settings['provider_parameters']['table_name'] + "_categories"
    logger.info(f"Table name for categories: {__tablename__}")

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    osm_type = db.Column(db.Integer, nullable=False, index=True)
    osm_id = db.Column(db.BigInteger, nullable=False, index=True)
    category = db.Column(db.Integer, index=True, nullable=False)
    __table_args__ = (db.ForeignKeyConstraint([osm_type, osm_id], [POIs.osm_type, POIs.osm_id], ondelete="CASCADE"),)

    def __repr__(self):
        return '<category %r>' % self.category


class Tags(db.Model):
    __tablename__ = ops_settings['provider_parameters']['table_name'] + "_tags"
    logger.info(f"Table name for tags: {__tablename__}")

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    osm_type = db.Column(db.Integer, nullable=False, index=True)
    osm_id = db.Column(db.BigInteger, nullable=False, index=True)
    key = db.Column(db.Text, nullable=True, index=True)
    value = db.Column(db.Text, nullable=True, index=True)
    __table_args__ = (db.ForeignKeyConstraint([osm_type, osm_id], [POIs.osm_type, POIs.osm_id], ondelete="CASCADE"),)

    def __repr__(self):
        return '<osm id %r>' % self.osm_id
