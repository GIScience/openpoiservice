# openpoiservice/server/config_flask.py

import os
from distutils.util import strtobool

class BaseConfig(object):
    """Base configuration."""

    # FLASK
    WTF_CSRF_ENABLED = True
    DEBUG_TB_ENABLED = False
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database
    POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
    POSTGRES_DBNAME = os.environ.get('POSTGRES_DBNAME', 'gis')
    POSTGRES_PORT = int(os.environ.get('POSTGRES_PORT', '5432'))
    POSTGRES_USER = os.environ.get('POSTGRES_USER', 'gis_admin')
    POSTGRES_PASS = os.environ.get('POSTGRES_PASS', 'admin')
    POSTGRES_PREWARM = bool(strtobool(os.environ.get('POSTGRES_PREWARM', 'false')))

    # API settings
    OPS_LOGGING = os.environ.get('OPS_LOGGING', 'info')
    OPS_OSMIUM = os.environ.get('OPS_OSMIUM', 'flex_mem')
    OPS_CONCURRENT_WORKERS = int(os.environ.get('OPS_CONCURRENT_WORKERS', str(os.cpu_count())))
    OPS_ATTRIBUTION = os.environ.get('OPS_ATTRIBUTION', "openrouteservice.org | OpenStreetMap contributors")
    OPS_MAX_POIS = int(os.environ.get('OPS_MAX_POIS', "2000"))
    OPS_MAX_CATEGORIES = int(os.environ.get('OPS_MAX_CATEGORIES', "5"))
    OPS_MAX_RADIUS_POINT = int(os.environ.get('OPS_MAX_RADIUS_POINT', "2000"))
    OPS_MAX_RADIUS_LINE = int(os.environ.get('OPS_MAX_RADIUS_LINE', "2000"))
    OPS_MAX_RADIUS_POLY = int(os.environ.get('OPS_MAX_RADIUS_POLY', "2000"))
    OPS_MAX_AREA = int(os.environ.get('OPS_MAX_AREA', "50000000"))
    OPS_MAX_LENGTH_LINE = int(os.environ.get('OPS_MAX_LENGTH_LINE', "500000"))

    OPS_ADDITIONAL_TAGS = os.environ.get('OPS_ADDITIONAL_TAGS', "name,wheelchair,smoking,fee,opening_hours,phone,website").split(',')

    SQLALCHEMY_DATABASE_URI = 'postgresql://{}:{}@{}:{}/{}'.format(POSTGRES_USER, POSTGRES_PASS,
                                                                   POSTGRES_HOST, POSTGRES_PORT,
                                                                   POSTGRES_DBNAME)


class ProductionConfig(BaseConfig):
    """Production configuration."""
    pass


class DevelopmentConfig(BaseConfig):
    """Production configuration."""

    DEBUG_TB_ENABLED = True
    OPS_LOGGING = 'debug'


class TestingConfig(BaseConfig):
    """Testing configuration."""
    TESTING = True

    OPS_LOGGING = 'info'
