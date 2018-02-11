# openpoiservice/server/config.py

import yaml
import os

"""load custom settings for openpoiservice"""
basedir = os.path.abspath(os.path.dirname(__file__))
ops_settings = yaml.safe_load(open(os.path.join(basedir, 'ops_settings.yml')))


class BaseConfig(object):
    """Base configuration."""

    # SECRET_KEY = 'my_precious'
    DEBUG = False
    WTF_CSRF_ENABLED = True
    DEBUG_TB_ENABLED = False
    DEBUG_TB_INTERCEPT_REDIRECTS = False


class ProductionConfig(BaseConfig):
    """Production configuration."""

    pg_settings = ops_settings['provider_parameters']
    # SECRET_KEY = 'my_precious'
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'postgresql://{}:{}@{}:{}/{}'.format(pg_settings['user_name'], pg_settings['password'],
                                                                   pg_settings['host'], pg_settings['port'],
                                                                   pg_settings['db_name'])
    DEBUG_TB_ENABLED = False


class DevelopmentConfig(BaseConfig):
    """Production configuration."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://gis_admin:admin@localhost:5433/gis'
    DEBUG_TB_ENABLED = True
